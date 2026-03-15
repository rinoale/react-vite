import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from core.config import get_settings
from db.models import User
from auth.dependencies import get_current_user
from lib.utils.log import logger

router = APIRouter()


@router.post("/examine-item")
async def examine_item(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Upload image to storage and enqueue V3 pipeline job.

    Returns a job_id for SSE streaming via /examine-item/{job_id}/stream.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    job_id = str(uuid.uuid4())
    logger.info("examine-item  file=%s  size=%d  job=%s", file.filename, len(raw), job_id)

    # Upload raw bytes — worker handles decode and validation
    from lib.storage import get_storage
    storage = get_storage()
    storage.upload(f"examine_jobs/{job_id}/input", raw, file.content_type or "application/octet-stream")

    # Enqueue job via Redis broker
    from db.connector import SessionLocal
    from db.models import JobRun
    from jobs.connection import get_broker

    db = SessionLocal()
    try:
        run = JobRun(job_name="run_v3_pipeline", status="pending")
        db.add(run)
        db.commit()
        db.refresh(run)

        from jobs import get_queue
        from jobs.broker import NoWorkerError
        broker = get_broker()
        try:
            broker.enqueue(get_queue("run_v3_pipeline"), {
                "job_id": job_id,
                "job_name": "run_v3_pipeline",
                "run_id": str(run.id),
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "job_id": job_id,
                    "filename": file.filename,
                    "storage_backend": get_settings().storage_backend,
                },
            })
        except NoWorkerError:
            run.status = "failed"
            run.error = "No worker available for OCR pipeline"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(status_code=503, detail="No OCR worker available")
    finally:
        db.close()

    return {"job_id": job_id}


@router.get("/examine-item/{job_id}/stream")
async def examine_item_stream(job_id: str, current_user: User = Depends(get_current_user)):
    """SSE endpoint — subscribes to Redis pub/sub for pipeline progress and result."""

    async def event_generator():
        import redis as redis_lib

        settings = get_settings()
        r = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"examine:{job_id}"
        pubsub.subscribe(channel)

        try:
            while True:
                msg = pubsub.get_message(timeout=0.2)
                if msg is None or msg["type"] != "message":
                    await asyncio.sleep(0.1)
                    continue

                parsed = json.loads(msg["data"])
                event = parsed["event"]
                payload = json.dumps(parsed["data"], ensure_ascii=False)
                yield f"event: {event}\ndata: {payload}\n\n"

                if event in ("result", "error"):
                    break
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
            r.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
