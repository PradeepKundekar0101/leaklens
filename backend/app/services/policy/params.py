"""Policy parameter extraction from the wording (MODEL_REASONING). Results are stored as a proposal next to the
approved parameters; only an admin's approval updates policy_params, and rules use only approved values."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import PolicyChunk, PolicyParams
from app.services.jsonsafe import to_jsonable
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.schemas import ExtractedParams

RELEVANT_TYPES = ("benefit", "sub_limit", "waiting_period", "exclusion", "general")


def current_as_comparable(p: PolicyParams) -> dict:
    wp = p.waiting_periods or {}
    return to_jsonable(
        {
            "room_rent_cap_pct": p.room_rent_cap_pct,
            "icu_cap_pct": p.icu_cap_pct,
            "copay_pct": p.copay_pct,
            "deductible": p.deductible,
            "sub_limits": p.sub_limits,
            "initial_days": wp.get("initial_days"),
            "listed_conditions_months": wp.get("listed_conditions_months"),
            "pre_existing_months": wp.get("pre_existing_months"),
            "clause_refs": p.clause_refs,
        }
    )


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:  # noqa: BLE001
        return a == b


def diff(current: dict, proposed: dict) -> list[dict]:
    rows = []
    for key in (
        "room_rent_cap_pct",
        "icu_cap_pct",
        "copay_pct",
        "deductible",
        "initial_days",
        "listed_conditions_months",
        "pre_existing_months",
    ):
        rows.append(
            {
                "param": key,
                "current": current.get(key),
                "proposed": proposed.get(key),
                "changed": not _same(current.get(key), proposed.get(key)),
            }
        )
    for code in sorted(set(current.get("sub_limits") or {}) | set(proposed.get("sub_limits") or {})):
        a, b = (current.get("sub_limits") or {}).get(code), (proposed.get("sub_limits") or {}).get(code)
        rows.append({"param": f"sub_limits.{code}", "current": a, "proposed": b, "changed": not _same(a, b)})
    return rows


async def extract(session: AsyncSession, product_id: str) -> dict:
    settings = get_settings()
    chunks = (
        (
            await session.execute(
                select(PolicyChunk).where(PolicyChunk.product_id == product_id).order_by(PolicyChunk.id)
            )
        )
        .scalars()
        .all()
    )
    if not chunks:
        raise ValueError("policy not ingested")
    params = await session.get(PolicyParams, product_id)
    text = "\n\n".join(f"[{c.clause_no}] {c.text}" for c in chunks if c.clause_type in RELEVANT_TYPES)[:150_000]
    system, version = prompts.load("params")
    codes = sorted((params.sub_limits or {}).keys()) if params else []
    result, meta = await llm.structured(
        model=settings.model_reasoning,
        system=system,
        user=f"Product {product_id}. Procedure codes in use: {codes}\n\n{prompts.wrap_untrusted(text)}",
        schema=ExtractedParams,
        max_tokens=4000,
    )
    if result is None:
        return {"ok": False, "error": meta.error or "llm unavailable"}
    proposed = to_jsonable(result.model_dump())
    if params is not None:
        params.proposed = {**proposed, "extracted_at": datetime.now(UTC).isoformat(), "prompt_version": version}
    return {"ok": True, "proposed": proposed, "diff": diff(current_as_comparable(params), proposed) if params else []}


async def approve(session: AsyncSession, product_id: str, approver: str) -> PolicyParams:
    params = await session.get(PolicyParams, product_id)
    if params is None or not params.proposed:
        raise ValueError("no proposed parameters to approve")
    p = params.proposed
    params.room_rent_cap_pct = p.get("room_rent_cap_pct")
    params.icu_cap_pct = p.get("icu_cap_pct")
    params.copay_pct = p.get("copay_pct") or 0
    params.deductible = Decimal(str(p.get("deductible") or 0))
    params.sub_limits = p.get("sub_limits") or {}
    wp = dict(params.waiting_periods or {})
    for k in ("initial_days", "listed_conditions_months", "pre_existing_months"):
        if p.get(k) is not None:
            wp[k] = p[k]
    params.waiting_periods = wp
    params.clause_refs = {**(params.clause_refs or {}), **(p.get("clause_refs") or {})}
    params.approved_by = approver
    params.approved_at = datetime.now(UTC)
    params.proposed = None
    return params
