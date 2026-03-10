import redis

from core.config import get_settings
from jobs.broker import RedisBroker

_broker: RedisBroker | None = None


def get_broker() -> RedisBroker:
    global _broker
    if _broker is None:
        settings = get_settings()
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _broker = RedisBroker(client)
    return _broker
