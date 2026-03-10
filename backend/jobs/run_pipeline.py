"""Background job: run V3 OCR pipeline.

Downloads input image from file storage, runs the pipeline,
uploads crops to file storage, publishes result via Redis pub/sub.
"""

import json

import cv2
import numpy as np
import redis

from core.config import get_settings
from lib.storage import get_storage
from lib.pipeline.v3 import init_pipeline, run_v3_pipeline, prepare_sections_for_response
from lib.utils.log import logger
from trade.schemas import ExamineItemResponse


def _get_pubsub_redis():
    """Get a Redis client for pub/sub (separate from the broker client)."""
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _publish(r, job_id: str, event: str, data: dict):
    """Publish an SSE-shaped event to the job's Redis channel."""
    r.publish(f"examine:{job_id}", json.dumps(
        {"event": event, "data": data}, ensure_ascii=False,
    ))


def _save_crops_to_storage(sections, session_id, img_bgr, storage):
    """Upload per-line crops and ocr_results.json to file storage."""
    originals = []
    prefix = f"ocr_crops/{session_id}"

    # Upload original image
    _, buf = cv2.imencode('.png', img_bgr)
    storage.upload(f"{prefix}/original.png", buf.tobytes(), "image/png")

    for sec_key, sec_data in sections.items():
        lines = sec_data.get('lines') or []
        for line in lines:
            li = line.get('line_index')
            if li is None:
                continue
            crop = line.pop('_crop', None)
            if crop is not None:
                _, crop_buf = cv2.imencode('.png', crop)
                storage.upload(
                    f"{prefix}/{sec_key}/{li:03d}.png",
                    crop_buf.tobytes(),
                    "image/png",
                )

            orig = {
                'section': sec_key,
                'line_index': li,
                'text': line.get('text', ''),
                'raw_text': line.get('raw_text', line.get('text', '')),
                'confidence': float(line.get('confidence', 0)),
                'ocr_model': line.get('ocr_model', ''),
                'fm_applied': bool(line.get('fm_applied', False)),
            }
            if line.get('_is_stitched'):
                orig['_is_stitched'] = True
            originals.append(orig)

    storage.upload(
        f"{prefix}/ocr_results.json",
        json.dumps(originals, ensure_ascii=False, indent=2).encode('utf-8'),
        "application/json",
    )
    logger.info("v3 crops  session=%s  %d lines uploaded to storage", session_id, len(originals))


def run_v3_pipeline_job(db, *, payload: dict | None = None):
    """Job entry point. Called by worker.execute_job().

    payload:
        job_id: str — used for Redis pub/sub channel and storage key
        filename: str — original upload filename
    """
    if not payload:
        return "no payload"

    job_id = payload["job_id"]
    filename = payload.get("filename", "unknown.png")
    storage = get_storage(payload.get("storage_backend"))
    r = _get_pubsub_redis()

    try:
        # Download image from storage
        image_key = f"examine_jobs/{job_id}/input"
        raw = storage.download(image_key)
        arr = np.frombuffer(raw, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            _publish(r, job_id, "error", {"message": "Could not decode image"})
            return "decode failed"

        def on_progress(step):
            _publish(r, job_id, "progress", {"step": step})

        # Initialize pipeline if not already done (worker process)
        init_pipeline()

        result = run_v3_pipeline(img_bgr, save_crops=True, on_progress=on_progress)

        sections = result.get('sections', {})
        session_id = result.get('session_id', '')

        # Upload crops to file storage
        _save_crops_to_storage(sections, session_id, img_bgr, storage)

        logger.info(
            "examine-item  session=%s  sections=%s",
            session_id, list(sections.keys()),
        )

        response = {
            "filename": filename,
            "sections": prepare_sections_for_response(sections),
            "abbreviated": result.get('abbreviated', True),
        }
        if session_id:
            response["session_id"] = session_id

        validated = ExamineItemResponse(**response).model_dump(exclude_none=True)
        _publish(r, job_id, "result", validated)

        # Clean up input image from storage
        storage.delete(image_key)

        return f"session={session_id} sections={len(sections)}"

    except Exception as e:
        logger.exception("examine-item job %s failed", job_id)
        _publish(r, job_id, "error", {"message": str(e)})
        return f"failed: {e}"
    finally:
        r.close()
