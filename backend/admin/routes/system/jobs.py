from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.connector import get_db
from db.models import JobRun
from admin.schemas.jobs import JobOut, JobRunOut, PaginatedJobRunResponse
from jobs import REGISTRY, get_queue
from jobs.broker import NoWorkerError
from jobs.connection import get_broker

router = APIRouter()


def _last_run(db: Session, job_name: str) -> JobRunOut | None:
    row = (
        db.query(JobRun)
        .filter(JobRun.job_name == job_name)
        .order_by(JobRun.id.desc())
        .first()
    )
    return JobRunOut.model_validate(row) if row else None


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    broker = get_broker()
    return [
        JobOut(
            name=name,
            description=meta["description"],
            schedule_seconds=meta.get("schedule_seconds"),
            queue=meta.get("queue", "default"),
            workers=broker.worker_count(meta.get("queue", "default")),
            last_run=_last_run(db, name),
        )
        for name, meta in REGISTRY.items()
    ]


@router.post("/jobs/{job_name}/run")
def trigger_job(
    job_name: str,
    db: Session = Depends(get_db),
) -> JobRunOut:
    if job_name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")

    run = JobRun(job_name=job_name, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    broker = get_broker()
    try:
        broker.enqueue(get_queue(job_name), {
            "job_id": str(uuid4()),
            "job_name": job_name,
            "run_id": str(run.id),
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "payload": {},
        })
    except NoWorkerError as e:
        run.status = "failed"
        run.error = str(e)
        db.commit()
        raise HTTPException(status_code=503, detail=str(e))
    return JobRunOut.model_validate(run)


@router.get("/jobs/history")
def job_history(
    job_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> PaginatedJobRunResponse:
    q = db.query(JobRun)
    if job_name:
        q = q.filter(JobRun.job_name == job_name)
    rows = q.order_by(JobRun.id.desc()).limit(limit).offset(offset).all()
    return PaginatedJobRunResponse(limit=limit, offset=offset, rows=rows)
