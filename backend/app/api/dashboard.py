from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.session import get_session
from app.services.jsonsafe import to_jsonable

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _rows(session: AsyncSession, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(r) for r in (await session.execute(text(sql), params or {})).mappings().all()]


@router.get("/summary", dependencies=[Depends(require_role("manager", "auditor", "admin"))])
async def summary(session: Session) -> dict:
    kpi = (
        (
            await session.execute(
                text(
                    """
                SELECT count(r.claim_id) AS processed,
                       COALESCE(sum(r.leakage_amount), 0) AS leakage_identified,
                       COALESCE(sum(r.claimed_amount), 0) AS claimed_processed,
                       COALESCE(sum(r.payable_amount), 0) AS payable_processed,
                       COALESCE(avg(CASE WHEN r.action = 'approve' THEN 1.0 ELSE 0.0 END), 0) AS auto_approval_rate,
                       (SELECT count(*) FROM claims WHERE status = 'pending_review') AS pending_review,
                       (SELECT count(*) FROM claims) AS total_claims,
                       (SELECT count(*) FROM claims WHERE status = 'received') AS unprocessed
                FROM recommendations r
                """
                )
            )
        )
        .mappings()
        .one()
    )
    by_rule = await _rows(
        session,
        """SELECT f.rule_code, count(*) AS findings, sum(f.amount_impact) AS amount
           FROM rule_findings f JOIN recommendations r ON r.claim_id = f.claim_id
           GROUP BY f.rule_code ORDER BY amount DESC""",
    )
    by_action = await _rows(
        session,
        "SELECT action, count(*) AS claims, sum(leakage_amount) AS leakage FROM recommendations GROUP BY action "
        "ORDER BY claims DESC",
    )
    weekly = await _rows(
        session,
        """SELECT date_trunc('week', c.admission_at)::date AS week, count(*) AS claims,
                  sum(r.leakage_amount) AS leakage, sum(r.claimed_amount) AS claimed,
                  avg(CASE WHEN r.action = 'approve' THEN 1.0 ELSE 0.0 END) AS auto_approval_rate
           FROM recommendations r JOIN claims c ON c.id = r.claim_id
           GROUP BY 1 ORDER BY 1""",
    )
    by_provider = await _rows(
        session,
        """SELECT c.provider_id, p.name, count(*) AS claims, sum(r.leakage_amount) AS leakage
           FROM recommendations r JOIN claims c ON c.id = r.claim_id JOIN providers p ON p.id = c.provider_id
           GROUP BY 1, 2 ORDER BY leakage DESC LIMIT 10""",
    )
    by_procedure = await _rows(
        session,
        """SELECT c.procedure_code, pr.name, count(*) AS claims, sum(r.leakage_amount) AS leakage
           FROM recommendations r JOIN claims c ON c.id = r.claim_id JOIN procedures pr ON pr.code = c.procedure_code
           GROUP BY 1, 2 ORDER BY leakage DESC LIMIT 10""",
    )
    tiers = await _rows(session, "SELECT tier, count(*) AS claims FROM anomaly_scores GROUP BY tier")
    return to_jsonable(
        {
            "kpis": dict(kpi),
            "leakage_by_rule": by_rule,
            "by_action": by_action,
            "weekly": weekly,
            "leakage_by_provider": by_provider,
            "leakage_by_procedure": by_procedure,
            "risk_tiers": tiers,
        }
    )
