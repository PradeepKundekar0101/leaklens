"""Append-only audit trail. Every state change on a claim writes a row here."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User
from app.services.jsonsafe import to_jsonable

Actor = User | tuple[str, str]  # a user, or (actor_type, actor_id) for agents and the system


async def log(
    session: AsyncSession,
    actor: Actor,
    action: str,
    entity: str,
    entity_id: str | int,
    payload: dict[str, Any] | None = None,
    model: str | None = None,
) -> AuditLog:
    if isinstance(actor, User):
        actor_type, actor_id = "user", str(actor.id)
    else:
        actor_type, actor_id = actor
    row = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        payload=to_jsonable(payload) if payload is not None else None,
        model=model,
    )
    session.add(row)
    await session.flush()
    return row


SYSTEM: Actor = ("system", "leaklens")


def agent(name: str) -> Actor:
    return ("agent", name)
