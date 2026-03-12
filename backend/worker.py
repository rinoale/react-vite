"""
Standalone job worker. Runs separately from the web server.

Usage:
    python worker.py                         # all queues (default + gpu)
    python worker.py --queues gpu            # GPU jobs only (local PC)
    python worker.py --queues default        # lightweight jobs only
    bash scripts/worker/run-remote.sh        # remote GPU worker via SSH tunnel
"""

import argparse
import json
import logging
import signal
import socket
import threading
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from core.config import get_settings
from db.connector import SessionLocal
from db.models import JobRun
from jobs import REGISTRY, get_queue
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


def execute_job(queue: str, message: JobMessage) -> None:
    broker = get_broker()
    job_name = message["job_name"]
    run_id = UUID(message["run_id"]) if isinstance(message["run_id"], str) else message["run_id"]

    entry = REGISTRY.get(job_name)
    if not entry:
        logger.error("Unknown job: %s (run_id=%s)", job_name, run_id)
        broker.ack(queue, message)
        return

    db = SessionLocal()
    try:
        run = db.get(JobRun, run_id)
        if not run:
            logger.error("JobRun not found: %s", run_id)
            broker.ack(queue, message)
            return

        payload = message.get("payload") or {}
        run.status = "running"
        run.worker_id = WORKER_ID
        run.payload = json.dumps(payload, ensure_ascii=False) if payload else None
        db.commit()
        logger.info("Running %s (run_id=%s) queue=%s payload=%s", job_name, run_id, queue, payload)
        result = entry["fn"](db, payload=payload)

        run.status = "completed"
        run.result_summary = str(result) if result else None
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        broker.ack(queue, message)
        logger.info("Completed %s (run_id=%s): %s", job_name, run_id, result)
    except Exception as exc:
        db.rollback()
        run = db.get(JobRun, run_id)
        if run:
            run.status = "failed"
            run.error = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        broker.fail(queue, message, str(exc))
        logger.exception("Failed %s (run_id=%s)", job_name, run_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Heartbeat (runs in a daemon thread)
# ---------------------------------------------------------------------------


def _heartbeat_loop(broker, worker_id: str, queues: set[str]) -> None:
    while not _shutdown.is_set():
        try:
            broker.register_worker(worker_id, queues)
        except Exception:
            logger.exception("Heartbeat refresh failed")
        _shutdown.wait(30)


# ---------------------------------------------------------------------------
# Scheduler (runs in a daemon thread)
# ---------------------------------------------------------------------------


def _scheduler_loop(queues: set[str]) -> None:
    broker = get_broker()
    last_run: dict[str, float] = {}

    while not _shutdown.is_set():
        now = time.time()
        for job_name, meta in REGISTRY.items():
            interval = meta.get("schedule_seconds")
            if not interval:
                continue
            queue = meta.get("queue", "default")
            if queue not in queues:
                continue
            if now - last_run.get(job_name, 0) < interval:
                continue

            db = SessionLocal()
            try:
                run = JobRun(job_name=job_name, status="pending")
                db.add(run)
                db.commit()
                db.refresh(run)

                broker.enqueue(queue, {
                    "job_id": str(uuid4()),
                    "job_name": job_name,
                    "run_id": str(run.id),
                    "enqueued_at": datetime.now(timezone.utc).isoformat(),
                    "payload": {},
                })
                last_run[job_name] = now
                logger.info("Scheduled %s (run_id=%s) queue=%s", job_name, run.id, queue)
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
    parser = argparse.ArgumentParser(description="Job worker")
    parser.add_argument(
        "--queues",
        nargs="+",
        default=None,
        help="Queue names to listen on (default: all queues from registry)",
    )
    args = parser.parse_args()

    # Determine queues: CLI arg or all unique queues from registry
    if args.queues:
        queues = set(args.queues)
    else:
        queues = {meta.get("queue", "default") for meta in REGISTRY.values()}

    settings = get_settings()
    logger.info(
        "Worker %s starting (queues=%s, redis=%s:%d, db=%s:%s/%s)",
        WORKER_ID,
        sorted(queues),
        settings.redis_host, settings.redis_port,
        settings.db_host, settings.db_port, settings.db_name,
    )

    # Ensure DB schema is up to date (idempotent — no-op if already current)
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")

    # Alembic's fileConfig() disables pre-existing loggers and sets root to WARNING
    logger.disabled = False
    logging.getLogger().setLevel(logging.INFO)
    logger.info("DB schema up to date")

    broker = get_broker()

    # Register heartbeat and start refresh thread
    broker.register_worker(WORKER_ID, queues)
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, args=(broker, WORKER_ID, queues), daemon=True,
    )
    heartbeat_thread.start()
    logger.info("Heartbeat registered (queues=%s)", sorted(queues))

    scheduler_thread = threading.Thread(target=_scheduler_loop, args=(queues,), daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")

    queue_list = sorted(queues)
    while not _shutdown.is_set():
        for queue in queue_list:
            message = broker.dequeue(queue, timeout=1)
            if message is not None:
                execute_job(queue, message)
                break
        else:
            # No message from any queue in this round
            continue

    broker.unregister_worker(WORKER_ID, queues)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
