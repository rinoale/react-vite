from jobs.cleanup_tags import cleanup_zero_weight_tags

REGISTRY = {
    "cleanup_zero_weight_tags": {
        "fn": cleanup_zero_weight_tags,
        "description": "Delete user-created tags with weight 0 (not searchable, varied text)",
    },
}
