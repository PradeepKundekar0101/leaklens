"""Postgres-backed job queue.

Workers claim jobs with SELECT ... FOR UPDATE SKIP LOCKED, run the registered handler and record
the result or error. Failed jobs are retried until job_max_attempts (1 run + 2 retries by default).
"""

import asyncio
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
    UPDATE jobs SET status = 'running', started_at = now(), attempts = attempts + 1
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


async def _finish(job_id: int, status: str, result: Any = None, error: str | None = None) -> None:
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.status = status
        job.result = to_jsonable(result) if result is not None else None
        job.error = error
        job.finished_at = datetime.now(UTC) if status in ("done", "failed") else None
        await session.commit()


async def run_one() -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    claimed = await claim_one()
    if claimed is None:
        return False
    job_id, job_type, payload, attempts = claimed
    fn = HANDLERS.get(job_type)
    if fn is None:
        await _finish(job_id, "failed", error=f"no handler for job type {job_type!r}")
        return True
    try:
        result = await fn(payload)
    except Exception as exc:  # noqa: BLE001 - the error is recorded on the job
        log.exception("job_failed", job_id=job_id, job_type=job_type, attempt=attempts)
        retry = attempts < get_settings().job_max_attempts
        await _finish(job_id, "queued" if retry else "failed", error=f"{type(exc).__name__}: {exc}")
        return True
    await _finish(job_id, "done", result=result)
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
        while not self._stop.is_set():
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

    async def _recover_stale(self) -> None:
        """Jobs left 'running' by a stopped process (crash or redeploy) go back to the queue.

        Assumes one worker process per database, which is how the app is deployed (a single API instance runs the
        worker). With several instances this would re-queue jobs another instance is still running.
        """
        async with session_scope() as session:
            await session.execute(text("UPDATE jobs SET status='queued' WHERE status='running'"))
            await session.commit()

    async def start(self) -> None:
        await self._recover_stale()
        self._tasks = [asyncio.create_task(self._loop(i)) for i in range(self.concurrency)]
        log.info("worker_started", concurrency=self.concurrency)

    async def stop(self) -> None:
        self._stop.set()
        await asyncio.gather(*self._tasks, return_exceptions=True)
