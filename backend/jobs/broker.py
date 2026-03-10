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


HEARTBEAT_TTL = 60  # seconds — workers refresh every 30s


class NoWorkerError(Exception):
    """Raised when no worker is listening on the target queue."""

    def __init__(self, queue: str):
        self.queue = queue
        super().__init__(f"No worker listening on queue '{queue}'")


class RedisBroker:
    def __init__(self, redis_client):
        self._r = redis_client

    def _key(self, queue: str) -> str:
        return f"jobs:{queue}"

    def _processing_key(self, queue: str) -> str:
        return f"jobs:{queue}:processing"

    def _heartbeat_key(self, queue: str) -> str:
        return f"jobs:{queue}:workers"

    # -- Heartbeat ----------------------------------------------------------

    def register_worker(self, worker_id: str, queues: set[str]) -> None:
        """Add this worker to each queue's worker set and refresh TTL."""
        for queue in queues:
            key = self._heartbeat_key(queue)
            self._r.sadd(key, worker_id)
            self._r.expire(key, HEARTBEAT_TTL)

    def unregister_worker(self, worker_id: str, queues: set[str]) -> None:
        """Remove this worker from each queue's worker set."""
        for queue in queues:
            self._r.srem(self._heartbeat_key(queue), worker_id)

    def has_workers(self, queue: str) -> bool:
        """Check if at least one worker is registered for the queue."""
        return self._r.scard(self._heartbeat_key(queue)) > 0

    def worker_count(self, queue: str) -> int:
        """Return number of workers registered for the queue."""
        return self._r.scard(self._heartbeat_key(queue))

    # -- Queue operations ---------------------------------------------------

    def enqueue(self, queue: str, message: JobMessage) -> None:
        if not self.has_workers(queue):
            raise NoWorkerError(queue)
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
