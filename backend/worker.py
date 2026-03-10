"""
Standalone job worker. Runs separately from the web server.

Usage:
    python worker.py                         # local dev
    APP_ENV=staging python worker.py         # staging
    REDIS_HOST=64.110.116.116 python worker.py  # remote worker (e.g., local PC with GPU)
"""

import json
import logging
import signal
import socket
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from core.config import get_settings
from db.connector import SessionLocal
from db.models import JobRun
from jobs import REGISTRY
from jobs.broker import JobMessage
from jobs.connection import get_broker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("worker")

QUEUE = "default"
WORKER_ID = socket.gethostname()

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = threading.Event()


def _handle_signal(signum, _frame):
    logger.info("Received signal %d, shutting down...", signum)
    _shutdown.set()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------


def execute_job(message: JobMessage) -> None:
    broker = get_broker()
    job_name = message["job_name"]
    run_id = message["run_id"]

    entry = REGISTRY.get(job_name)
    if not entry:
        logger.error("Unknown job: %s (run_id=%d)", job_name, run_id)
        broker.ack(QUEUE, message)
        return

    db = SessionLocal()
    try:
        run = db.get(JobRun, run_id)
        if not run:
            logger.error("JobRun not found: %d", run_id)
            broker.ack(QUEUE, message)
            return

        payload = message.get("payload") or {}
        run.status = "running"
        run.worker_id = WORKER_ID
        run.payload = json.dumps(payload, ensure_ascii=False) if payload else None
        db.commit()
        logger.info("Running %s (run_id=%d) payload=%s", job_name, run_id, payload)
        result = entry["fn"](db, payload=payload)

        run.status = "completed"
        run.result_summary = str(result) if result else None
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        broker.ack(QUEUE, message)
        logger.info("Completed %s (run_id=%d): %s", job_name, run_id, result)
    except Exception as exc:
        db.rollback()
        run = db.get(JobRun, run_id)
        if run:
            run.status = "failed"
            run.error = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        broker.fail(QUEUE, message, str(exc))
        logger.exception("Failed %s (run_id=%d)", job_name, run_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduler (runs in a daemon thread)
# ---------------------------------------------------------------------------


def _scheduler_loop() -> None:
    broker = get_broker()
    last_run: dict[str, float] = {}

    while not _shutdown.is_set():
        now = time.time()
        for job_name, meta in REGISTRY.items():
            interval = meta.get("schedule_seconds")
            if not interval:
                continue
            if now - last_run.get(job_name, 0) < interval:
                continue

            db = SessionLocal()
            try:
                run = JobRun(job_name=job_name, status="pending")
                db.add(run)
                db.commit()
                db.refresh(run)

                broker.enqueue(QUEUE, {
                    "job_id": str(uuid4()),
                    "job_name": job_name,
                    "run_id": run.id,
                    "enqueued_at": datetime.now(timezone.utc).isoformat(),
                    "payload": {},
                })
                last_run[job_name] = now
                logger.info("Scheduled %s (run_id=%d)", job_name, run.id)
            except Exception:
                db.rollback()
                logger.exception("Failed to schedule %s", job_name)
            finally:
                db.close()

        _shutdown.wait(30)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    settings = get_settings()
    logger.info(
        "Worker %s starting (redis=%s:%d, db=%s:%s/%s)",
        WORKER_ID,
        settings.redis_host, settings.redis_port,
        settings.db_host, settings.db_port, settings.db_name,
    )

    broker = get_broker()

    scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")

    while not _shutdown.is_set():
        message = broker.dequeue(QUEUE, timeout=5)
        if message is None:
            continue
        execute_job(message)

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
