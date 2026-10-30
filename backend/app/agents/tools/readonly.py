"""Read-only tools for agents. Every tool opens a READ ONLY transaction, so no tool can modify data.

Each tool has a Pydantic input model and returns compact JSON.
"""

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import func, select, text

from app.agents import runtime
from app.db.models import (
    AnomalyScore,
    Claim,
    ClaimDocument,
    CoverageFinding,
    Investigation,
    Member,
    MemberPolicy,
    PolicyParams,
    Provider,
    ProviderStats,
    Recommendation,
    RuleFinding,
)
from app.db.session import readonly_session
from app.services.anomaly.features import LABELS, Z_FEATURES, features_for_claims, load_features
from app.services.anomaly.peer_stats import LEVEL_KEYS
from app.services.anomaly.scorer import ensure_scorer
from app.services.jsonsafe import to_jsonable
from app.services.llm.client import Tool
from app.services.llm.prompts import wrap_untrusted
from app.services.policy import search as policy_search


# ---- inputs -------------------------------------------------------------------------------------------------------
class SearchPolicyIn(BaseModel):
    product_id: str
    query: str = Field(description="Natural-language search, e.g. 'room rent limit' or 'gloves non-payable'")
    clause_type: str | None = Field(
        default=None,
        description="Optional filter: definition, benefit, exclusion, waiting_period, sub_limit, procedure, general",
    )


class DefinitionIn(BaseModel):
    product_id: str
    term: str


class ProductIn(BaseModel):
    product_id: str


class ClauseNotesIn(BaseModel):
    product_id: str
    clause_no: str


class MemberIn(BaseModel):
    member_id: str


class ProviderIn(BaseModel):
    provider_id: str


class PeerIn(BaseModel):
    claim_id: str
    feature: str = Field(description=f"One of: {', '.join(Z_FEATURES)}")


class SimilarCasesIn(BaseModel):
    query: str


class ClaimIn(BaseModel):
    claim_id: str


class DocumentTextIn(BaseModel):
    claim_id: str
    doc_type: str = Field(default="bill", description="bill, discharge_summary, prescription, preauth_letter, other")


# ---- implementations ----------------------------------------------------------------------------------------------
async def search_policy(args: SearchPolicyIn) -> dict:
    async with readonly_session() as s:
        chunks = await policy_search.search(s, args.product_id, args.query, args.clause_type)
    return {
        "chunks": [
            {k: c.get(k) for k in ("clause_no", "section_path", "page", "text", "definitions") if c.get(k) is not None}
            for c in chunks
        ]
    }


async def get_definition(args: DefinitionIn) -> dict:
    async with readonly_session() as s:
        d = await policy_search.get_definition(s, args.product_id, args.term)
    return {"definition": d and {"clause_no": d["clause_no"], "text": d["text"]}}


async def get_policy_params(args: ProductIn) -> dict:
    async with readonly_session() as s:
        p = await s.get(PolicyParams, args.product_id)
    if p is None:
        return {"params": None}
    return {
        "params": to_jsonable(
            {
                "room_rent_cap_pct_of_si_per_day": p.room_rent_cap_pct,
                "icu_cap_pct_of_si_per_day": p.icu_cap_pct,
                "copay_pct": p.copay_pct,
                "deductible": p.deductible,
                "sub_limits": p.sub_limits,
                "waiting_periods": p.waiting_periods,
                "clause_refs": p.clause_refs,
                "approved_at": p.approved_at,
            }
        )
    }


def clause_namespace(product_id: str, clause_no: str) -> tuple[str, ...]:
    """Store namespace for adjuster notes on a clause. Labels cannot contain '.', so 4.2 is stored as 4_2."""
    return ("clauses", product_id, clause_no.replace(".", "_"))


async def get_clause_notes(args: ClauseNotesIn) -> dict:
    items = await runtime.store().asearch(clause_namespace(args.product_id, args.clause_no), limit=10)
    return {"notes": [i.value for i in items]}


async def get_member_history(args: MemberIn) -> dict:
    async with readonly_session() as s:
        member = await s.get(Member, args.member_id)
        if member is None:
            return {"error": "member not found"}
        policies = (await s.execute(select(MemberPolicy).where(MemberPolicy.member_id == args.member_id))).scalars()
        policies = list(policies)
        rows = (
            await s.execute(
                select(Claim, Recommendation.action)
                .outerjoin(Recommendation, Recommendation.claim_id == Claim.id)
                .where(Claim.member_policy_id.in_([p.id for p in policies]))
                .order_by(Claim.admission_at)
            )
        ).all()
    return to_jsonable(
        {
            "member_id": member.id,
            "age": member.age,
            "member_since": member.member_since,
            "declared_conditions": member.declared_conditions,
            "policies": [
                {
                    "id": p.id,
                    "product_id": p.product_id,
                    "start_date": p.start_date,
                    "sum_insured": p.sum_insured,
                    "balance": p.balance,
                }
                for p in policies
            ],
            "claims": [
                {
                    "claim_id": c.id,
                    "admission_at": c.admission_at,
                    "procedure_code": c.procedure_code,
                    "provider_id": c.provider_id,
                    "claimed_amount": c.claimed_amount,
                    "status": c.status,
                    "recommended": action,
                }
                for c, action in rows[-20:]
            ],
        }
    )


async def get_provider_profile(args: ProviderIn) -> dict:
    async with readonly_session() as s:
        p = await s.get(Provider, args.provider_id)
        if p is None:
            return {"error": "provider not found"}
        stats = (
            await s.execute(
                select(ProviderStats)
                .where(ProviderStats.provider_id == args.provider_id)
                .order_by(ProviderStats.period.desc())
                .limit(3)
            )
        ).scalars()
        common = (
            await s.execute(
                select(RuleFinding.rule_code, func.count())
                .join(Claim, Claim.id == RuleFinding.claim_id)
                .where(Claim.provider_id == args.provider_id)
                .group_by(RuleFinding.rule_code)
                .order_by(func.count().desc())
                .limit(5)
            )
        ).all()
    return to_jsonable(
        {
            "provider": {
                "id": p.id,
                "name": p.name,
                "city": p.city,
                "city_tier": p.city_tier,
                "hospital_tier": p.hospital_tier,
                "nabh": p.nabh,
                "network": p.network,
            },
            "recent_stats": [
                {
                    "period": st.period,
                    "claims": st.claims,
                    "claimed_total": st.claimed_total,
                    "leakage_total": st.leakage_total,
                    "flag_rate": st.flag_rate,
                    "oe_index": st.oe_index,
                    "avg_pharmacy_share": st.avg_pharmacy_share,
                    "peer_pharmacy_share": st.peer_pharmacy_share,
                }
                for st in stats
            ],
            "common_findings": [{"rule_code": code, "count": n} for code, n in common],
        }
    )


async def peer_distribution(claim_id: str, feature: str, sample: int = 500) -> dict:
    """Peer group values (train split, same level the scorer used) and the claim's value."""
    if feature not in Z_FEATURES:
        return {"error": f"unknown feature {feature}"}
    async with readonly_session() as s:
        claim_df = await features_for_claims(s, [claim_id])
        if claim_df.empty:
            return {"error": "claim not found"}
        row = claim_df.iloc[0]
        scorer = await ensure_scorer()
        stat = (
            scorer.table.lookup(feature, row["procedure_code"], int(row["hospital_tier"]), int(row["city_tier"]))
            if scorer
            else None
        )
        level = stat.level if stat else 3
        keys = LEVEL_KEYS[level]
        where = ["c.split = 'train'"] + [f"{'c.' if k == 'procedure_code' else 'p.'}{k} = :{k}" for k in keys]
        params = {k: (row[k] if k == "procedure_code" else int(row[k])) for k in keys}
        peers = await load_features(s, " AND ".join(where), params)
    values = peers[feature].to_numpy()
    if len(values) > sample:
        values = peers[feature].sample(sample, random_state=0).to_numpy()
    full = peers[feature]
    value = float(row[feature])
    return {
        "feature": feature,
        "label": LABELS[feature],
        "level": level,
        "group": {k: params[k] for k in keys},
        "n": int(len(full)),
        "claim_value": value,
        "quantiles": {q: float(full.quantile(int(q[1:]) / 100)) for q in ("p10", "p50", "p90", "p99")}
        if len(full)
        else {},
        "percentile": float((full <= value).mean()) if len(full) else None,
        "values": [float(v) for v in values],
    }


async def get_peer_distribution(args: PeerIn) -> dict:
    result = await peer_distribution(args.claim_id, args.feature, sample=500)
    result.pop("values", None)  # agents get quantiles, the UI gets the sample
    return result


async def search_similar_cases(args: SimilarCasesIn) -> dict:
    items = await runtime.store().asearch(("cases", "outcomes"), query=args.query, limit=5)
    return {"cases": [{**i.value, "score": round(i.score or 0, 3)} for i in items]}


async def find_near_duplicates(args: ClaimIn) -> dict:
    async with readonly_session() as s:
        c = await s.get(Claim, args.claim_id)
        if c is None:
            return {"error": "claim not found"}
        mp = await s.get(MemberPolicy, c.member_policy_id)
        lo, hi = c.claimed_amount * Decimal("0.95"), c.claimed_amount * Decimal("1.05")
        rows = (
            await s.execute(
                select(Claim)
                .join(MemberPolicy, MemberPolicy.id == Claim.member_policy_id)
                .where(
                    MemberPolicy.member_id == mp.member_id,
                    Claim.id != c.id,
                    Claim.admission_at.between(c.admission_at - timedelta(days=3), c.admission_at + timedelta(days=3)),
                    Claim.claimed_amount.between(lo, hi),
                )
            )
        ).scalars()
        out = []
        for o in rows:
            out.append(
                {
                    "claim_id": o.id,
                    "provider_id": o.provider_id,
                    "admission_at": o.admission_at,
                    "claimed_amount": o.claimed_amount,
                    "bill_no": o.bill_no,
                    "bill_no_similarity": fuzz.ratio(o.bill_no or "", c.bill_no or "") if c.bill_no else None,
                }
            )
    return to_jsonable({"claim_id": c.id, "near_duplicates": out})


async def get_document_text(args: DocumentTextIn) -> dict:
    async with readonly_session() as s:
        docs = (
            await s.execute(
                select(ClaimDocument).where(
                    ClaimDocument.claim_id == args.claim_id, ClaimDocument.doc_type == args.doc_type
                )
            )
        ).scalars()
        texts = []
        for d in docs:
            raw = (d.extracted or {}).get("text") or ""
            texts.append({"document_id": d.id, "text": wrap_untrusted(raw[:6000])})
    return {"documents": texts}


async def get_claim_state(args: ClaimIn) -> dict:
    async with readonly_session() as s:
        c = await s.get(Claim, args.claim_id)
        if c is None:
            return {"error": "claim not found"}
        rec = await s.get(Recommendation, args.claim_id)
        score = await s.get(AnomalyScore, args.claim_id)
        inv = await s.get(Investigation, args.claim_id)
        rules = (await s.execute(select(RuleFinding).where(RuleFinding.claim_id == args.claim_id))).scalars()
        cov = (await s.execute(select(CoverageFinding).where(CoverageFinding.claim_id == args.claim_id))).scalars()
        mp = await s.get(MemberPolicy, c.member_policy_id)
        return to_jsonable(
            {
                "claim": {
                    "id": c.id,
                    "status": c.status,
                    "procedure_code": c.procedure_code,
                    "provider_id": c.provider_id,
                    "member_id": mp.member_id if mp else None,
                    "product_id": mp.product_id if mp else None,
                    "admission_at": c.admission_at,
                    "discharge_at": c.discharge_at,
                    "los": c.los,
                    "claimed_amount": c.claimed_amount,
                },
                "recommendation": rec
                and {
                    "action": rec.action,
                    "payable_amount": rec.payable_amount,
                    "leakage_amount": rec.leakage_amount,
                    "confidence": rec.confidence,
                    "explanation": rec.explanation,
                    "key_findings": rec.key_findings,
                    "payable_steps": rec.payable_steps,
                },
                "rule_findings": [
                    {
                        "rule_code": f.rule_code,
                        "amount_impact": f.amount_impact,
                        "clause_ref": f.clause_ref,
                        "evidence": f.evidence,
                    }
                    for f in rules
                ],
                "coverage_findings": [
                    {
                        "line_item_id": f.line_item_id,
                        "verdict": f.verdict,
                        "clause_no": f.clause_no,
                        "quote": f.quote,
                        "reason": f.reason,
                        "verified": f.verified,
                    }
                    for f in cov
                ],
                "anomaly": score and {"tier": score.tier, "risk": score.risk, "reasons": score.reasons},
                "investigation": inv and inv.report,
            }
        )


async def readonly_check() -> bool:
    """Used by tests: a write inside a readonly session must fail."""
    async with readonly_session() as s:
        await s.execute(text("CREATE TEMP TABLE _ro_probe (x int)"))
    return True


# ---- tool sets ----------------------------------------------------------------------------------------------------
def _t(name: str, desc: str, model: type[BaseModel], fn) -> Tool:
    return Tool(name=name, description=desc, input_model=model, fn=fn)


SEARCH_POLICY = _t(
    "search_policy",
    "Hybrid search of the policy wording. Returns up to 6 clauses with text.",
    SearchPolicyIn,
    search_policy,
)
GET_DEFINITION = _t("get_definition", "Definition clause for a defined term, or null.", DefinitionIn, get_definition)
GET_POLICY_PARAMS = _t(
    "get_policy_params", "Approved policy parameters with clause references.", ProductIn, get_policy_params
)
GET_CLAUSE_NOTES = _t(
    "get_clause_notes", "Adjuster interpretation notes recorded for a clause.", ClauseNotesIn, get_clause_notes
)
GET_MEMBER_HISTORY = _t(
    "get_member_history", "Member's prior claims, policy start, declared conditions.", MemberIn, get_member_history
)
GET_PROVIDER_PROFILE = _t(
    "get_provider_profile", "Provider's latest statistics and most common findings.", ProviderIn, get_provider_profile
)
GET_PEER_DISTRIBUTION = _t(
    "get_peer_distribution",
    "Peer quantiles (p10/p50/p90/p99), claim value and percentile.",
    PeerIn,
    get_peer_distribution,
)
SEARCH_SIMILAR_CASES = _t(
    "search_similar_cases",
    "Up to 5 past case memories with decisions and reasons.",
    SimilarCasesIn,
    search_similar_cases,
)
FIND_NEAR_DUPLICATES = _t(
    "find_near_duplicates",
    "Claims of the same member within 3 days and 5% of the amount, with bill-number similarity.",
    ClaimIn,
    find_near_duplicates,
)
GET_DOCUMENT_TEXT = _t(
    "get_document_text",
    "Extracted text of a claim document, wrapped in untrusted tags.",
    DocumentTextIn,
    get_document_text,
)
GET_CLAIM_STATE = _t(
    "get_claim_state", "Stored findings, scores and recommendation for a claim.", ClaimIn, get_claim_state
)

COVERAGE_TOOLS = [SEARCH_POLICY, GET_DEFINITION, GET_POLICY_PARAMS, GET_CLAUSE_NOTES]
INVESTIGATOR_TOOLS = [
    SEARCH_POLICY,
    GET_DEFINITION,
    GET_POLICY_PARAMS,
    GET_CLAUSE_NOTES,
    GET_MEMBER_HISTORY,
    GET_PROVIDER_PROFILE,
    GET_PEER_DISTRIBUTION,
    SEARCH_SIMILAR_CASES,
    FIND_NEAR_DUPLICATES,
    GET_DOCUMENT_TEXT,
]
COPILOT_TOOLS = [*INVESTIGATOR_TOOLS, GET_CLAIM_STATE]
