from jobs.cleanup_tags import cleanup_zero_weight_tags

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
    "run_v3_pipeline": {
        "fn": _lazy_run_v3_pipeline_job,
        "description": "Run V3 OCR pipeline on uploaded image (GPU-heavy)",
        "queue": "gpu",
    },
}


def get_queue(job_name: str) -> str:
    return REGISTRY.get(job_name, {}).get("queue", DEFAULT_QUEUE)
