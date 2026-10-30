"""Small reference lists for forms and filters (any signed-in role)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ANY_ROLE
from app.db.models import Member, MemberPolicy, Procedure, Provider
from app.db.session import get_session

router = APIRouter(prefix="/lookups", tags=["lookups"], dependencies=[Depends(ANY_ROLE)])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/procedures")
async def procedures(session: Session) -> dict:
    rows = (await session.execute(select(Procedure).order_by(Procedure.name))).scalars().all()
    return {
        "items": [{"code": p.code, "name": p.name, "icd10": p.icd10, "category": p.category} for p in rows],
        "total": len(rows),
    }


@router.get("/providers")
async def providers(session: Session) -> dict:
    rows = (await session.execute(select(Provider).order_by(Provider.name))).scalars().all()
    return {
        "items": [{"id": p.id, "name": p.name, "city": p.city, "network": p.network} for p in rows],
        "total": len(rows),
    }


@router.get("/member-policies")
async def member_policies(
    session: Session, q: Annotated[str, Query(min_length=2, max_length=64)], limit: int = 20
) -> dict:
    """Search by member policy ID or member ID. Names are not searchable here, to limit PII exposure."""
    term = f"{q.strip().upper()}%"
    rows = (
        await session.execute(
            select(MemberPolicy, Member.age, Member.city)
            .join(Member, Member.id == MemberPolicy.member_id)
            .where(or_(MemberPolicy.id.ilike(term), MemberPolicy.member_id.ilike(term)))
            .order_by(MemberPolicy.id)
            .limit(min(limit, 50))
        )
    ).all()
    return {
        "items": [
            {
                "id": mp.id,
                "member_id": mp.member_id,
                "product_id": mp.product_id,
                "sum_insured": str(mp.sum_insured),
                "start_date": mp.start_date.isoformat(),
                "member_age": age,
                "member_city": city,
            }
            for mp, age, city in rows
        ],
        "total": len(rows),
    }
