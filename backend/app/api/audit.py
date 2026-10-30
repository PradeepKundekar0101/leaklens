import csv
import io
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.models import AuditLog, User
from app.db.session import get_session
from app.services.jsonsafe import to_jsonable

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_role("auditor", "manager", "admin"))])
Session = Annotated[AsyncSession, Depends(get_session)]


def _filtered(
    entity: str | None,
    entity_id: str | None,
    actor_type: str | None,
    actor_id: str | None,
    action: str | None,
    date_from: date | None,
    date_to: date | None,
):
    q = select(AuditLog)
    if entity:
        q = q.where(AuditLog.entity == entity)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if actor_type:
        q = q.where(AuditLog.actor_type == actor_type)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if action:
        q = q.where(AuditLog.action == action)
    if date_from:
        q = q.where(AuditLog.created_at >= date_from)
    if date_to:
        q = q.where(AuditLog.created_at < date_to + timedelta(days=1))
    return q


@router.get("")
async def list_audit(
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    entity: str | None = None,
    entity_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    q = _filtered(entity, entity_id, actor_type, actor_id, action, date_from, date_to)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    users = {str(u.id): u.name for u in (await session.execute(select(User))).scalars()}
    actions = sorted((await session.execute(select(AuditLog.action).distinct())).scalars())
    return to_jsonable(
        {
            "items": [
                {**r.as_dict(), "actor_name": users.get(r.actor_id) if r.actor_type == "user" else r.actor_id}
                for r in rows
            ],
            "total": total,
            "actions": actions,
        }
    )


@router.get("/export")
async def export_csv(
    session: Session,
    entity: str | None = None,
    entity_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> StreamingResponse:
    q = _filtered(entity, entity_id, actor_type, actor_id, action, date_from, date_to)
    rows = (await session.execute(q.order_by(AuditLog.created_at, AuditLog.id).limit(100_000))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "actor_type", "actor_id", "action", "entity", "entity_id", "model", "payload"])
    for r in rows:
        w.writerow(
            [
                r.id,
                r.created_at.isoformat(),
                r.actor_type,
                r.actor_id,
                r.action,
                r.entity,
                r.entity_id,
                r.model or "",
                to_jsonable(r.payload),
            ]
        )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leaklens-audit.csv"'},
    )
