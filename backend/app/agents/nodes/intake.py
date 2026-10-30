"""load_claim, document, load_policy."""

from sqlalchemy import delete, select

from app.agents.state import ClaimState
from app.core import audit
from app.db.models import (
    Claim,
    ClaimDocument,
    CoverageFinding,
    Investigation,
    LineItem,
    MemberPolicy,
    PolicyParams,
    Provider,
    Recommendation,
    RuleFinding,
)
from app.db.session import session_scope
from app.services.claims import set_status
from app.services.jsonsafe import to_jsonable


def line_item_dict(li: LineItem) -> dict:
    return to_jsonable(
        {
            "id": li.id,
            "category": li.category,
            "item_code": li.item_code,
            "description": li.description,
            "qty": li.qty,
            "unit_price": li.unit_price,
            "amount": li.amount,
            "service_date": li.service_date,
            "document_id": li.document_id,
            "page": li.page,
        }
    )


async def load_claim(state: ClaimState) -> dict:
    claim_id = state["claim_id"]
    async with session_scope() as session:
        claim = await session.get(Claim, claim_id)
        if claim is None:
            raise ValueError(f"claim {claim_id} not found")
        mp = await session.get(MemberPolicy, claim.member_policy_id)
        provider = await session.get(Provider, claim.provider_id)
        # A (re)run starts from a clean slate of analysis results.
        for model in (RuleFinding, CoverageFinding, Recommendation, Investigation):
            await session.execute(delete(model).where(model.claim_id == claim_id))
        await set_status(session, claim_id, "processing", audit.agent("orchestrator"), {"run_id": state["run_id"]})
        lines = (
            await session.execute(select(LineItem).where(LineItem.claim_id == claim_id).order_by(LineItem.id))
        ).scalars()
        docs = (await session.execute(select(ClaimDocument).where(ClaimDocument.claim_id == claim_id))).scalars()
        payload = {
            "claim": to_jsonable(
                {
                    "id": claim.id,
                    "member_policy_id": claim.member_policy_id,
                    "member_id": mp.member_id if mp else None,
                    "product_id": mp.product_id if mp else None,
                    "sum_insured": mp.sum_insured if mp else None,
                    "balance": mp.balance if mp else None,
                    "policy_start": mp.start_date if mp else None,
                    "provider_id": claim.provider_id,
                    "provider_name": provider.name if provider else None,
                    "procedure_code": claim.procedure_code,
                    "diagnosis_code": claim.diagnosis_code,
                    "admission_at": claim.admission_at,
                    "discharge_at": claim.discharge_at,
                    "los": claim.los,
                    "claimed_amount": claim.claimed_amount,
                    "claim_type": claim.claim_type,
                    "split": claim.split,
                }
            ),
            "line_items": [line_item_dict(li) for li in lines],
            "documents": [
                {"id": d.id, "doc_type": d.doc_type, "parse_status": d.parse_status, "pages": d.pages} for d in docs
            ],
        }
        await session.commit()
    return payload


async def document(state: ClaimState) -> dict:
    """Runs the document agent when a claim has documents but no line items yet (Phase 6)."""
    if state.get("line_items") or not state.get("documents"):
        return {}
    from app.services.documents.pipeline import process_claim_documents

    result = await process_claim_documents(state["claim_id"])
    async with session_scope() as session:
        lines = (
            await session.execute(select(LineItem).where(LineItem.claim_id == state["claim_id"]).order_by(LineItem.id))
        ).scalars()
        docs = (
            await session.execute(select(ClaimDocument).where(ClaimDocument.claim_id == state["claim_id"]))
        ).scalars()
        return {
            "line_items": [line_item_dict(li) for li in lines],
            "documents": [
                {"id": d.id, "doc_type": d.doc_type, "parse_status": d.parse_status, "pages": d.pages} for d in docs
            ],
            "errors": result.get("errors", []),
            "versions": {"document_prompt": result.get("prompt_version", "none")},
        }


async def load_policy(state: ClaimState) -> dict:
    product_id = state["claim"].get("product_id")
    async with session_scope() as session:
        params = await session.get(PolicyParams, product_id)
        if params is None:
            return {"policy_params": {}, "errors": [f"no policy_params for {product_id}"]}
        return {
            "policy_params": to_jsonable(
                {
                    "product_id": params.product_id,
                    "room_rent_cap_pct": params.room_rent_cap_pct,
                    "icu_cap_pct": params.icu_cap_pct,
                    "copay_pct": params.copay_pct,
                    "deductible": params.deductible,
                    "sub_limits": params.sub_limits,
                    "waiting_periods": params.waiting_periods,
                    "clause_refs": params.clause_refs,
                    "approved_at": params.approved_at,
                }
            )
        }
