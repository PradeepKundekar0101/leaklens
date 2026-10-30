"""Postgres-backed job queue.

Workers claim jobs with SELECT ... FOR UPDATE SKIP LOCKED, run the registered handler and record
the result or error. Failed jobs are retried until job_max_attempts (1 run + 2 retries by default).

Leases: a running job's worker refreshes heartbeat_at every HEARTBEAT_SECONDS. A job whose heartbeat is older
than LEASE_SECONDS (its process crashed or was replaced by a deploy) goes back to the queue. Finishing is
conditional on still holding the lease (same attempt), so a stale worker can never overwrite a retried job.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Job
from app.db.session import session_scope
from app.services.jsonsafe import to_jsonable

log = get_logger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]
HANDLERS: dict[str, Handler] = {}


def handler(job_type: str) -> Callable[[Handler], Handler]:
    def _register(fn: Handler) -> Handler:
        HANDLERS[job_type] = fn
        return fn

    return _register


async def enqueue(session: AsyncSession, job_type: str, payload: dict[str, Any] | None = None) -> Job:
    job = Job(type=job_type, status="queued", payload=to_jsonable(payload or {}), attempts=0)
    session.add(job)
    await session.flush()
    return job


_CLAIM_SQL = text(
    """
    UPDATE jobs SET status = 'running', started_at = now(), heartbeat_at = now(), attempts = attempts + 1
    WHERE id = (
        SELECT id FROM jobs WHERE status = 'queued'
        ORDER BY created_at, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, type, payload, attempts
    """
)


async def claim_one() -> tuple[int, str, dict, int] | None:
    async with session_scope() as session:
        row = (await session.execute(_CLAIM_SQL)).first()
        await session.commit()
        return (row.id, row.type, row.payload, row.attempts) if row else None


HEARTBEAT_SECONDS = 20
LEASE_SECONDS = 90

_FINISH_SQL = text(
    """
    UPDATE jobs SET status = :status, result = CAST(:result AS jsonb), error = :error, finished_at = :finished_at
    WHERE id = :id AND attempts = :attempt AND status = 'running'
    """
)
_HEARTBEAT_SQL = text(
    "UPDATE jobs SET heartbeat_at = now() WHERE id = :id AND attempts = :attempt AND status = 'running'"
)
_RECOVER_SQL = text(
    f"""
    UPDATE jobs SET status = 'queued'
    WHERE status = 'running' AND COALESCE(heartbeat_at, started_at) < now() - interval '{LEASE_SECONDS} seconds'
    """
)


async def _finish(job_id: int, attempt: int, status: str, result: Any = None, error: str | None = None) -> bool:
    """Records the outcome only if this worker still holds the job's lease."""
    async with session_scope() as session:
        res = await session.execute(
            _FINISH_SQL,
            {
                "id": job_id,
                "attempt": attempt,
                "status": status,
                "result": json.dumps(to_jsonable(result)) if result is not None else None,
                "error": error,
                "finished_at": datetime.now(UTC) if status in ("done", "failed") else None,
            },
        )
        await session.commit()
    if res.rowcount == 0:
        log.warning("job_lease_lost", job_id=job_id, attempt=attempt)
    return res.rowcount == 1


async def _heartbeat(job_id: int, attempt: int) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with session_scope() as session:
                await session.execute(_HEARTBEAT_SQL, {"id": job_id, "attempt": attempt})
                await session.commit()
        except Exception:  # noqa: BLE001 - a missed beat is tolerated; the lease is 90 s
            log.warning("job_heartbeat_failed", job_id=job_id)


async def recover_expired() -> int:
    async with session_scope() as session:
        res = await session.execute(_RECOVER_SQL)
        await session.commit()
    if res.rowcount:
        log.warning("jobs_requeued_after_lease_expiry", count=res.rowcount)
    return res.rowcount


async def run_one() -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    claimed = await claim_one()
    if claimed is None:
        return False
    job_id, job_type, payload, attempts = claimed
    fn = HANDLERS.get(job_type)
    if fn is None:
        await _finish(job_id, attempts, "failed", error=f"no handler for job type {job_type!r}")
        return True
    beat = asyncio.create_task(_heartbeat(job_id, attempts))
    try:
        result = await fn(payload)
    except Exception as exc:  # noqa: BLE001 - the error is recorded on the job
        log.exception("job_failed", job_id=job_id, job_type=job_type, attempt=attempts)
        retry = attempts < get_settings().job_max_attempts
        await _finish(job_id, attempts, "queued" if retry else "failed", error=f"{type(exc).__name__}: {exc}")
        return True
    finally:
        beat.cancel()
    await _finish(job_id, attempts, "done", result=result)
    return True


async def drain(max_jobs: int = 10_000) -> int:
    """Run jobs until the queue is empty (used by scripts and tests)."""
    n = 0
    while n < max_jobs and await run_one():
        n += 1
    return n


class Worker:
    def __init__(self, concurrency: int | None = None) -> None:
        self.concurrency = concurrency or get_settings().job_concurrency
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def _loop(self, n: int) -> None:
        interval = get_settings().job_poll_interval
        last_recovery = time.monotonic()
        while not self._stop.is_set():
            if n == 0 and time.monotonic() - last_recovery > LEASE_SECONDS / 2:
                last_recovery = time.monotonic()
                try:
                    await recover_expired()
                except Exception:  # noqa: BLE001
                    log.exception("job_recovery_failed")
            try:
                worked = await run_one()
            except Exception:  # noqa: BLE001 - keep the worker alive on database hiccups
                log.exception("worker_loop_error", worker=n)
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except TimeoutError:
                    pass

    async def start(self) -> None:
        await recover_expired()
        self._tasks = [asyncio.create_task(self._loop(i)) for i in range(self.concurrency)]
        log.info("worker_started", concurrency=self.concurrency)

    async def stop(self) -> None:
        self._stop.set()
        await asyncio.gather(*self._tasks, return_exceptions=True)
