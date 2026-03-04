"""Centralized logger and timing utilities for the backend.

Usage:
    from lib.utils.log import logger, timed, timed_block

All modules share a single 'mabinogi' logger configured in main.py.
"""

import functools
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger('mabinogi')


def timed(label=None):
    """Decorator that logs execution time of a function.

    Usage:
        @timed
        def my_func(): ...

        @timed("custom label")
        def my_func(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            name = _label or fn.__qualname__
            t0 = time.monotonic()
            result = fn(*args, **kwargs)
            elapsed = (time.monotonic() - t0) * 1000
            logger.info("%s  %.1fms", name, elapsed)
            return result
        return wrapper

    if callable(label):
        _label = None
        return decorator(label)
    _label = label
    return decorator


@contextmanager
def timed_block(label):
    """Context manager that captures elapsed time for custom logging.

    Usage:
        with timed_block("step1") as elapsed_ms:
            do_work()
        logger.info("step1 %d items  %.1fms", count, elapsed_ms())
    """
    t0 = time.monotonic()
    yield lambda: (time.monotonic() - t0) * 1000
