"""Claim state changes. Every status change writes an audit_log row."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import AppError, not_found
from app.db.models import CLAIM_STATUSES, Claim


async def set_status(
    session: AsyncSession,
    claim_id: str,
    status: str,
    actor: audit.Actor,
    payload: dict | None = None,
    model: str | None = None,
) -> Claim:
    if status not in CLAIM_STATUSES:
        raise AppError(400, "bad_status", f"Unknown claim status {status!r}")
    claim = await session.get(Claim, claim_id)
    if claim is None:
        raise not_found("Claim")
    previous = claim.status
    claim.status = status
    await audit.log(
        session,
        actor,
        "status_change",
        "claim",
        claim_id,
        {"from": previous, "to": status, **(payload or {})},
        model=model,
    )
    return claim


async def get_claim_or_404(session: AsyncSession, claim_id: str) -> Claim:
    claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise not_found("Claim")
    return claim


REVIEW_DECISION_STATUS = {
    "approve": "approved",
    "approve_with_deductions": "approved_with_deductions",
    "query": "queried",
    "investigate": "investigating",
    "refer_siu": "investigating",
    "reject": "rejected",
}
