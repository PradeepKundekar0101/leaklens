from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.decision import RULE_NAMES
from app.core.errors import not_found
from app.core.security import require_role
from app.db.models import Provider
from app.db.session import get_session
from app.services.jsonsafe import to_jsonable
from app.services.portfolio import RANKING_SQL

router = APIRouter(
    prefix="/providers", tags=["providers"], dependencies=[Depends(require_role("auditor", "manager", "admin"))]
)
Session = Annotated[AsyncSession, Depends(get_session)]

SORTS = {"oe_index": "oe_index", "flag_rate": "flag_rate", "leakage": "leakage_total", "claims": "claims"}


@router.get("")
async def ranking(
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: Literal["oe_index", "flag_rate", "leakage", "claims"] = "oe_index",
) -> dict:
    sql = f"SELECT * FROM ({RANKING_SQL}) t ORDER BY {SORTS[sort]} DESC NULLS LAST, id"
    rows = [dict(r) for r in (await session.execute(text(sql))).mappings().all()]
    for rank, r in enumerate(rows, start=1):
        r["rank"] = rank
    start = (page - 1) * page_size
    return to_jsonable({"items": rows[start : start + page_size], "total": len(rows)})


@router.get("/{provider_id}")
async def profile(provider_id: str, session: Session) -> dict:
    p = await session.get(Provider, provider_id)
    if p is None:
        raise not_found("Provider")
    trend = (
        (
            await session.execute(
                text(
                    "SELECT period, claims, claimed_total, leakage_total, flag_rate, oe_index, avg_pharmacy_share, "
                    "peer_pharmacy_share FROM provider_stats WHERE provider_id = :p ORDER BY period"
                ),
                {"p": provider_id},
            )
        )
        .mappings()
        .all()
    )
    findings = (
        (
            await session.execute(
                text(
                    "SELECT f.rule_code, count(*) AS findings, sum(f.amount_impact) AS amount FROM rule_findings f "
                    "JOIN claims c ON c.id = f.claim_id WHERE c.provider_id = :p GROUP BY 1 ORDER BY 2 DESC"
                ),
                {"p": provider_id},
            )
        )
        .mappings()
        .all()
    )
    procedures = (
        (
            await session.execute(
                text(
                    "SELECT c.procedure_code, pr.name, count(*) AS claims, avg(c.claimed_amount) AS avg_claimed "
                    "FROM claims c JOIN procedures pr ON pr.code = c.procedure_code WHERE c.provider_id = :p "
                    "GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10"
                ),
                {"p": provider_id},
            )
        )
        .mappings()
        .all()
    )
    summary = (
        (await session.execute(text(f"SELECT * FROM ({RANKING_SQL}) t WHERE id = :p"), {"p": provider_id}))
        .mappings()
        .one_or_none()
    )
    return to_jsonable(
        {
            "provider": {
                "id": p.id,
                "name": p.name,
                "city": p.city,
                "city_tier": p.city_tier,
                "hospital_tier": p.hospital_tier,
                "nabh": p.nabh,
                "beds": p.beds,
                "network": p.network,
                "joined_at": p.joined_at,
            },
            "summary": dict(summary) if summary else None,
            "trend": [dict(r) for r in trend],
            "common_findings": [
                {**dict(r), "rule_name": RULE_NAMES.get(r["rule_code"], r["rule_code"])} for r in findings
            ],
            "top_procedures": [dict(r) for r in procedures],
        }
    )
