"""Build ClaimContexts from the database, in bulk (a handful of queries regardless of batch size)."""

import hashlib
import re
from collections import defaultdict
from decimal import Decimal

import imagehash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Claim,
    ClaimDocument,
    CoverageFinding,
    Item,
    LineItem,
    Member,
    MemberPolicy,
    PolicyParams,
    Tariff,
)
from app.services.rules.context import (
    ClaimContext,
    DocumentMatch,
    LineItemCtx,
    PolicyParamsCtx,
    PriorClaim,
    dec,
)

PHASH_MAX_DISTANCE = 5
COVERAGE_EXCLUSION_MIN_CONFIDENCE = Decimal("0.7")


def params_ctx(p: PolicyParams) -> PolicyParamsCtx:
    return PolicyParamsCtx(
        room_rent_cap_pct=None if p.room_rent_cap_pct is None else dec(p.room_rent_cap_pct),
        icu_cap_pct=None if p.icu_cap_pct is None else dec(p.icu_cap_pct),
        copay_pct=dec(p.copay_pct),
        deductible=dec(p.deductible),
        sub_limits={k: dec(v) for k, v in (p.sub_limits or {}).items()},
        waiting_periods=p.waiting_periods or {},
        clause_refs={k: str(v) for k, v in (p.clause_refs or {}).items()},
    )


async def _item_reference(session: AsyncSession) -> tuple[dict[str, Decimal], frozenset[str]]:
    rows = (await session.execute(select(Item.item_code, Item.mrp, Item.non_payable))).all()
    return {r.item_code: dec(r.mrp) for r in rows}, frozenset(r.item_code for r in rows if r.non_payable)


def text_fingerprint(doc: ClaimDocument) -> str | None:
    """Hash of the document's normalised extracted text, or None for image-only / unparsed documents."""
    stored = (doc.extracted or {}).get("text_fingerprint")
    if stored:
        return stored
    raw = (doc.extracted or {}).get("text") or ""
    words = re.sub(r"--- page \d+ ---", " ", raw).lower().split()
    return hashlib.sha256(" ".join(words).encode()).hexdigest() if len(words) >= 30 else None


def document_matches(docs: list[ClaimDocument], claim_ids: set[str]) -> dict[str, list[DocumentMatch]]:
    """Exact SHA-256 or perceptual-hash (Hamming distance <= 5) matches against earlier documents of other claims.

    A perceptual hash cannot tell apart two digital bills printed from the same template, so when both documents
    have extractable text a phash match also requires identical normalised text. Scanned (image-only) documents
    match on the perceptual hash alone.
    """
    out: dict[str, list[DocumentMatch]] = defaultdict(list)
    hashes = [(d, imagehash.hex_to_hash(d.phash) if d.phash else None, text_fingerprint(d)) for d in docs]
    for d, h, fp in hashes:
        if d.claim_id not in claim_ids:
            continue
        for other, oh, ofp in hashes:
            # Only an earlier document can be the original; the claim that reuses it is the one flagged.
            if other.claim_id == d.claim_id or (other.created_at, other.id) >= (d.created_at, d.id):
                continue
            if d.sha256 == other.sha256:
                out[d.claim_id].append(DocumentMatch(d.id, other.claim_id, other.id, "sha256", 0))
            elif h is not None and oh is not None and h.hash.shape == oh.hash.shape and (h - oh) <= PHASH_MAX_DISTANCE:
                if fp is not None and ofp is not None and fp != ofp:
                    continue
                out[d.claim_id].append(DocumentMatch(d.id, other.claim_id, other.id, "phash", int(h - oh)))
    return out


async def load_contexts(session: AsyncSession, claim_ids: list[str]) -> dict[str, ClaimContext]:
    if not claim_ids:
        return {}
    claims = (await session.execute(select(Claim).where(Claim.id.in_(claim_ids)))).scalars().all()
    mp_ids = {c.member_policy_id for c in claims}
    policies = {
        p.id: p for p in (await session.execute(select(MemberPolicy).where(MemberPolicy.id.in_(mp_ids)))).scalars()
    }
    members = {
        m.id: m
        for m in (
            await session.execute(select(Member).where(Member.id.in_({p.member_id for p in policies.values()})))
        ).scalars()
    }
    params = {p.product_id: params_ctx(p) for p in (await session.execute(select(PolicyParams))).scalars()}
    tariffs = {
        (t.provider_id, t.procedure_code): dec(t.package_rate)
        for t in (
            await session.execute(select(Tariff).where(Tariff.provider_id.in_({c.provider_id for c in claims})))
        ).scalars()
    }
    item_mrp, non_payable = await _item_reference(session)

    line_rows = (
        (await session.execute(select(LineItem).where(LineItem.claim_id.in_(claim_ids)).order_by(LineItem.id)))
        .scalars()
        .all()
    )
    lines: dict[str, list[LineItemCtx]] = defaultdict(list)
    for li in line_rows:
        lines[li.claim_id].append(
            LineItemCtx(
                id=li.id,
                category=li.category,
                item_code=li.item_code,
                description=li.description,
                qty=dec(li.qty),
                unit_price=dec(li.unit_price),
                amount=dec(li.amount),
                service_date=li.service_date,
            )
        )

    prior_rows = (
        await session.execute(
            select(
                Claim.id,
                Claim.member_policy_id,
                Claim.provider_id,
                Claim.admission_at,
                Claim.claimed_amount,
                Claim.created_at,
                Claim.procedure_code,
            ).where(Claim.member_policy_id.in_(mp_ids))
        )
    ).all()
    prior: dict[str, list[PriorClaim]] = defaultdict(list)
    for r in prior_rows:
        prior[r.member_policy_id].append(
            PriorClaim(r.id, r.provider_id, r.admission_at, dec(r.claimed_amount), r.created_at, r.procedure_code)
        )

    docs = (await session.execute(select(ClaimDocument))).scalars().all()
    matches = document_matches(list(docs), set(claim_ids))

    exclusions: dict[str, set[int]] = defaultdict(set)
    cov_rows = (
        await session.execute(
            select(CoverageFinding.claim_id, CoverageFinding.line_item_id).where(
                CoverageFinding.claim_id.in_(claim_ids),
                CoverageFinding.verdict == "not_payable",
                CoverageFinding.verified.is_(True),
                CoverageFinding.confidence >= COVERAGE_EXCLUSION_MIN_CONFIDENCE,
                CoverageFinding.line_item_id.is_not(None),
            )
        )
    ).all()
    for r in cov_rows:
        exclusions[r.claim_id].add(r.line_item_id)

    out: dict[str, ClaimContext] = {}
    for c in claims:
        mp = policies[c.member_policy_id]
        member = members[mp.member_id]
        pp = params[mp.product_id]
        out[c.id] = ClaimContext(
            claim_id=c.id,
            member_id=member.id,
            member_policy_id=mp.id,
            product_id=mp.product_id,
            provider_id=c.provider_id,
            procedure_code=c.procedure_code,
            diagnosis_code=c.diagnosis_code,
            admission_at=c.admission_at,
            discharge_at=c.discharge_at,
            claimed_amount=dec(c.claimed_amount),
            room_rent_per_day=dec(c.room_rent_per_day),
            created_at=c.created_at,
            sum_insured=dec(mp.sum_insured),
            balance=dec(mp.balance),
            policy_start=mp.start_date,
            params=pp,
            line_items=lines.get(c.id, []),
            tariff=tariffs.get((c.provider_id, c.procedure_code)),
            item_mrp=item_mrp,
            non_payable_items=non_payable,
            listed_procedures=frozenset(pp.waiting_periods.get("listed_procedures", [])),
            declared_conditions=frozenset(member.declared_conditions or []),
            prior_claims=[p for p in prior[mp.id] if p.id != c.id],
            document_matches=matches.get(c.id, []),
            excluded_line_ids=frozenset(exclusions.get(c.id, set())),
        )
    return out


async def load_context(session: AsyncSession, claim_id: str) -> ClaimContext | None:
    return (await load_contexts(session, [claim_id])).get(claim_id)
