import json
from typing import Protocol, TypedDict


class JobMessage(TypedDict):
    job_id: str
    job_name: str
    run_id: int
    enqueued_at: str
    payload: dict


class JobBroker(Protocol):
    def enqueue(self, queue: str, message: JobMessage) -> None: ...
    def dequeue(self, queue: str, timeout: int) -> JobMessage | None: ...
    def ack(self, queue: str, message: JobMessage) -> None: ...
    def fail(self, queue: str, message: JobMessage, error: str) -> None: ...


class RedisBroker:
    def __init__(self, redis_client):
        self._r = redis_client

    def _key(self, queue: str) -> str:
        return f"jobs:{queue}"

    def _processing_key(self, queue: str) -> str:
        return f"jobs:{queue}:processing"

    def enqueue(self, queue: str, message: JobMessage) -> None:
        self._r.lpush(self._key(queue), json.dumps(message))

    def dequeue(self, queue: str, timeout: int = 5) -> JobMessage | None:
        result = self._r.brpoplpush(
            self._key(queue), self._processing_key(queue), timeout=timeout,
        )
        if result is None:
            return None
        return json.loads(result)

    def ack(self, queue: str, message: JobMessage) -> None:
        self._r.lrem(self._processing_key(queue), 1, json.dumps(message))

    def fail(self, queue: str, message: JobMessage, error: str) -> None:
        self._r.lrem(self._processing_key(queue), 1, json.dumps(message))
