from jobs.cleanup_tags import cleanup_zero_weight_tags
from jobs.verify_users import verify_users_from_horn_bugle

DEFAULT_QUEUE = "default"


def _lazy_run_v3_pipeline_job(db, **kwargs):
    from jobs.run_pipeline import run_v3_pipeline_job
    return run_v3_pipeline_job(db, **kwargs)


REGISTRY = {
    "cleanup_zero_weight_tags": {
        "fn": cleanup_zero_weight_tags,
        "description": "Delete user-created tags with weight 0 (not searchable, varied text)",
        "schedule_seconds": 12 * 3600,
        "queue": DEFAULT_QUEUE,
    },
    "verify_users": {
        "fn": verify_users_from_horn_bugle,
        "description": "Poll horn bugle and verify pending users via in-game OTP",
        "schedule_seconds": 20 * 60,  # every 20 minutes
        "queue": DEFAULT_QUEUE,
    },
    "run_v3_pipeline": {
        "fn": _lazy_run_v3_pipeline_job,
        "description": "Run V3 OCR pipeline on uploaded image (GPU-heavy)",
        "queue": "gpu",
    },
}


def get_queue(job_name: str) -> str:
    return REGISTRY.get(job_name, {}).get("queue", DEFAULT_QUEUE)
