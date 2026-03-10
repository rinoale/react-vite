from jobs.cleanup_tags import cleanup_zero_weight_tags
from jobs.run_pipeline import run_v3_pipeline_job

REGISTRY = {
    "cleanup_zero_weight_tags": {
        "fn": cleanup_zero_weight_tags,
        "description": "Delete user-created tags with weight 0 (not searchable, varied text)",
        "schedule_seconds": 12 * 3600,
    },
    "run_v3_pipeline": {
        "fn": run_v3_pipeline_job,
        "description": "Run V3 OCR pipeline on uploaded image (GPU-heavy)",
    },
}
