import os

from lib.storage.base import FileStorage
from lib.storage.local import LocalFileStorage


_instances: dict[str, FileStorage] = {}


def get_storage(backend: str | None = None) -> FileStorage:
    """Return a storage instance for the given backend.

    Args:
        backend: "r2" or "local". Defaults to settings.storage_backend.
    """
    from core.config import get_settings
    settings = get_settings()

    key = backend or settings.storage_backend

    if key in _instances:
        return _instances[key]

    if key == "r2":
        from lib.storage.r2 import R2FileStorage
        _instances[key] = R2FileStorage(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket,
            prefix=settings.r2_prefix,
        )
    else:
        base_dir = settings.storage_local_dir
        if not base_dir:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                '..', 'tmp', 'ocr_crops',
            )
        _instances[key] = LocalFileStorage(base_dir=base_dir)

    return _instances[key]
