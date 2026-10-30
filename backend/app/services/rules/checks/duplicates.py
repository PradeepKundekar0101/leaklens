"""R08 exact duplicate, R11 reused document."""

from app.services.rules.context import ZERO, ClaimContext, RuleFinding
from app.services.rules.engine import rule


@rule("R08", "Exact duplicate: same member policy, provider, admission date and amount")
def exact_duplicate(ctx: ClaimContext) -> list[RuleFinding]:
    matches = [
        p
        for p in ctx.prior_claims
        if p.id != ctx.claim_id
        and p.provider_id == ctx.provider_id
        and p.admission_at == ctx.admission_at
        and p.claimed_amount == ctx.claimed_amount
        and (p.created_at is None or ctx.created_at is None or (p.created_at, p.id) < (ctx.created_at, ctx.claim_id))
    ]
    if not matches:
        return []
    return [
        RuleFinding(
            rule_code="R08",
            severity="high",
            amount_impact=ctx.claimed_amount,
            full_claim=True,
            evidence={"duplicate_of": [m.id for m in matches], "admission_at": ctx.admission_at},
        )
    ]


@rule("R11", "Bill document reused from another claim (same SHA-256 or near-identical image)")
def reused_document(ctx: ClaimContext) -> list[RuleFinding]:
    return [
        RuleFinding(
            rule_code="R11",
            severity="high",
            amount_impact=ZERO,
            evidence={
                "document_id": m.document_id,
                "other_claim_id": m.other_claim_id,
                "other_document_id": m.other_document_id,
                "method": m.method,
                "hamming_distance": m.distance,
            },
        )
        for m in ctx.document_matches
    ]
