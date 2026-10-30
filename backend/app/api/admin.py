from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.security import require_role
from app.db.models import Job, ModelRegistry, User
from app.db.session import get_session
from app.jobs.runner import enqueue

router = APIRouter(prefix="/admin", tags=["admin"])
Session = Annotated[AsyncSession, Depends(get_session)]
Manager = Annotated[User, Depends(require_role("manager", "admin"))]


class BatchIn(BaseModel):
    split: Literal["test", "train", "live"] = "test"
    limit: int = Field(default=100, ge=1, le=5000)
    concurrency: int = Field(default=5, ge=1, le=16)
    only_unprocessed: bool = True


@router.post("/process-batch", status_code=202)
async def process_batch(body: BatchIn, session: Session, user: Manager) -> dict:
    job = await enqueue(session, "process_batch", body.model_dump())
    await audit.log(session, user, "process_batch_requested", "job", job.id, body.model_dump())
    await session.commit()
    return {"job_id": job.id}


@router.post("/retrain", status_code=202)
async def retrain(session: Session, user: Manager) -> dict:
    job = await enqueue(session, "retrain", {"user_id": user.id})
    await audit.log(session, user, "retrain_requested", "job", job.id)
    await session.commit()
    return {"job_id": job.id}


@router.post("/provider-stats", status_code=202)
async def provider_stats(session: Session, user: Manager) -> dict:
    job = await enqueue(session, "provider_stats", {"user_id": user.id})
    await session.commit()
    return {"job_id": job.id}


@router.get("/models")
async def models(session: Session, _: Manager) -> dict:
    rows = (await session.execute(select(ModelRegistry).order_by(ModelRegistry.trained_at.desc()))).scalars().all()
    items = [
        {"version": r.version, "kind": r.kind, "trained_at": r.trained_at, "active": r.active, "metrics": r.metrics}
        for r in rows
    ]
    active = next((i for i in items if i["active"] and i["kind"] == "iforest"), None)
    return {"items": items, "total": len(items), "active": active}


@router.get("/jobs")
async def jobs(session: Session, _: Manager, limit: int = 20) -> dict:
    rows = (await session.execute(select(Job).order_by(Job.id.desc()).limit(min(limit, 100)))).scalars().all()
    counts = dict((await session.execute(text("SELECT status, count(*) FROM jobs GROUP BY status"))).all())
    return {
        "items": [
            {
                "id": j.id,
                "type": j.type,
                "status": j.status,
                "attempts": j.attempts,
                "error": j.error,
                "result": j.result,
                "created_at": j.created_at,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
            }
            for j in rows
        ],
        "total": len(rows),
        "counts": counts,
    }
