"""investigate, decide, human_review, finalize."""

import json
from decimal import Decimal

from langgraph.config import get_store
from langgraph.types import interrupt

from app.agents.policy import confidence_for, decide_action
from app.agents.state import ClaimState
from app.core import audit
from app.core.config import get_settings
from app.core.pii import mask_payload
from app.db.models import Investigation, Review
from app.db.models import Recommendation as RecommendationRow
from app.db.session import session_scope
from app.services.claims import REVIEW_DECISION_STATUS, set_status
from app.services.jsonsafe import to_jsonable
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.guardrail import check_numbers
from app.services.llm.schemas import Recommendation
from app.services.money import inr

RULE_NAMES = {
    "R01": "Room rent above cap",
    "R02": "ICU rent above cap",
    "R03": "Above contracted tariff",
    "R04": "Item above MRP",
    "R05": "Non-payable item",
    "R06": "Waiting period",
    "R07": "Sub-limit exceeded",
    "R08": "Exact duplicate",
    "R09": "Service date outside stay",
    "R10": "Exceeds remaining sum insured",
    "R11": "Reused document",
}


async def investigate(state: ClaimState) -> dict:
    from app.agents.investigator import run_investigation

    report, tool_calls, meta = await run_investigation(state)
    if report is None:
        note = "investigation unavailable" if meta.unavailable else f"investigation failed: {meta.error}"
        return {"investigation": None, "errors": [note]}
    async with session_scope() as session:
        await session.merge(
            Investigation(claim_id=state["claim_id"], report=report, tool_calls=tool_calls, run_id=state["run_id"])
        )
        await audit.log(
            session,
            audit.agent("investigator"),
            "investigation",
            "claim",
            state["claim_id"],
            {"run_id": state["run_id"], "tool_calls": len(tool_calls), "incomplete": meta.incomplete},
            model=meta.model,
        )
        await session.commit()
    return {"investigation": report, "versions": {"investigator_prompt": report.get("prompt_version", "")}}


def decision_input(state: ClaimState, action: str) -> dict:
    rules = state.get("rules") or {}
    payable = rules.get("payable") or {}
    anomaly = state.get("anomaly") or {}
    return {
        "claim_id": state["claim_id"],
        "procedure_code": state["claim"].get("procedure_code"),
        "provider": state["claim"].get("provider_name"),
        "claimed_amount": payable.get("claimed", state["claim"].get("claimed_amount")),
        "action": action,
        "payable_amount": payable.get("payable"),
        "leakage_amount": payable.get("leakage"),
        "member_share": payable.get("member_share"),
        "payable_steps": [
            {k: s[k] for k in ("step", "name", "before", "after", "delta")}
            for s in payable.get("steps", [])
            if Decimal(str(s.get("delta", 0))) != 0
        ],
        "rule_findings": [
            {
                "rule_code": f["rule_code"],
                "rule": RULE_NAMES.get(f["rule_code"], f["rule_code"]),
                "amount_impact": f["amount_impact"],
                "clause_ref": f.get("clause_ref"),
                "evidence": {k: v for k, v in (f.get("evidence") or {}).items() if k != "associated"},
            }
            for f in rules.get("findings", [])
        ],
        "coverage_findings": [
            {k: v.get(k) for k in ("line_item_id", "verdict", "clause_no", "reason", "verified")}
            for v in state.get("coverage") or []
            if v.get("verdict") != "payable"
        ],
        "anomaly": {
            "tier": anomaly.get("tier"),
            "risk": anomaly.get("risk"),
            "reasons": [r["text"] for r in anomaly.get("reasons", [])],
        },
        "investigation": state.get("investigation"),
    }


def template_explanation(inp: dict) -> tuple[str, list[str]]:
    action = inp["action"].replace("_", " ")
    parts = [f"Recommended action: {action}."]
    findings = []
    for f in inp["rule_findings"]:
        clause = f" (clause {f['clause_ref']})" if f.get("clause_ref") else ""
        findings.append(f"{f['rule_code']} {f['rule']}{clause}: {inr(f['amount_impact'])}")
    if findings:
        parts.append("Rule findings: " + "; ".join(findings) + ".")
    else:
        parts.append("No rule findings.")
    tier = inp["anomaly"].get("tier")
    if tier:
        parts.append(f"Anomaly risk tier: {tier}.")
    findings.extend(inp["anomaly"]["reasons"][:3])
    if inp.get("investigation"):
        parts.append(f"Investigation: {inp['investigation'].get('summary', '')}")
    parts.append(
        f"Payable {inr(inp['payable_amount'])} of {inr(inp['claimed_amount'])} claimed; "
        f"leakage {inr(inp['leakage_amount'])}."
    )
    return " ".join(parts), findings[:6]


async def write_explanation(inp: dict) -> tuple[str, list[str], str, str | None, float | None]:
    """Returns (explanation, key_findings, source, prompt_version, model_confidence)."""
    settings = get_settings()
    system, version = prompts.load("decision")
    masked = mask_payload(inp)
    user = "Input JSON:\n" + json.dumps(masked, default=str, indent=1)
    for attempt in (1, 2):
        rec, meta = await llm.structured(
            model=settings.model_reasoning, system=system, user=user, schema=Recommendation, max_tokens=2000
        )
        if rec is None:
            break
        bad = check_numbers(rec.explanation + " " + " ".join(rec.key_findings), masked)
        if not bad:
            return rec.explanation, rec.key_findings[:6], "llm", version, rec.confidence
        if attempt == 1:
            user += (
                f"\n\nYour previous explanation used numbers that are not in the input: {', '.join(bad)}. "
                "Rewrite it using only numbers that appear in the input JSON."
            )
    text, findings = template_explanation(inp)
    return text, findings, "template", version, None


async def decide(state: ClaimState) -> dict:
    rules = state.get("rules") or {}
    payable = rules.get("payable") or {}
    findings = rules.get("findings") or []
    anomaly = state.get("anomaly") or {}
    deductions = sum((Decimal(str(f["amount_impact"])) for f in findings), Decimal(0))
    documents_missing = not state.get("line_items") or any(
        d.get("parse_status") == "needs_human" for d in state.get("documents") or []
    )
    action = decide_action([f["rule_code"] for f in findings], deductions, anomaly.get("tier"), documents_missing)
    needs_review = sum(1 for v in state.get("coverage") or [] if v.get("verdict") == "needs_review")
    confidence = confidence_for(action, anomaly.get("tier"), anomaly.get("risk"), needs_review)

    inp = decision_input(state, action)
    explanation, key_findings, source, version, _ = await write_explanation(inp)
    rec = {
        "action": action,  # always from code
        "claimed_amount": payable.get("claimed", state["claim"].get("claimed_amount")),
        "payable_amount": payable.get("payable", "0.00"),
        "leakage_amount": payable.get("leakage", "0.00"),
        "member_share": payable.get("member_share", "0.00"),
        "confidence": confidence,
        "explanation": explanation,
        "key_findings": key_findings,
        "explanation_source": source,
    }
    async with session_scope() as session:
        await session.merge(
            RecommendationRow(
                claim_id=state["claim_id"],
                action=action,
                claimed_amount=Decimal(str(rec["claimed_amount"])),
                payable_amount=Decimal(str(rec["payable_amount"])),
                leakage_amount=Decimal(str(rec["leakage_amount"])),
                confidence=confidence,
                explanation=explanation,
                key_findings=key_findings,
                payable_steps=payable.get("steps", []),
                explanation_source=source,
                run_id=state["run_id"],
            )
        )
        await audit.log(
            session,
            audit.agent("decision"),
            "recommendation",
            "claim",
            state["claim_id"],
            {
                "run_id": state["run_id"],
                "action": action,
                "payable": rec["payable_amount"],
                "leakage": rec["leakage_amount"],
                "explanation_source": source,
                "prompt_version": version,
                "versions": state.get("versions", {}),
            },
            model=get_settings().model_reasoning if source == "llm" else None,
        )
        await set_status(
            session,
            state["claim_id"],
            "pending_review",
            audit.agent("orchestrator"),
            {"run_id": state["run_id"], "action": action},
        )
        await session.commit()
    return {"recommendation": rec, "versions": {"decision_prompt": version or ""}}


async def human_review(state: ClaimState) -> dict:
    review = interrupt({"claim_id": state["claim_id"], "recommendation": state.get("recommendation")})
    return {"review": review}


async def finalize(state: ClaimState) -> dict:
    review = state.get("review") or {}
    rec = state.get("recommendation") or {}
    decision = review.get("decision", rec.get("action", "approve"))
    status = REVIEW_DECISION_STATUS.get(decision, "pending_review")
    final_amount = Decimal(str(review.get("final_amount", rec.get("payable_amount", "0"))))
    async with session_scope() as session:
        row = Review(
            claim_id=state["claim_id"],
            reviewer_id=int(review["reviewer_id"]),
            decision=decision,
            final_amount=final_amount,
            notes=review.get("notes"),
            overrides=to_jsonable(review.get("overrides")),
        )
        session.add(row)
        actor = ("user", str(review["reviewer_id"]))
        await audit.log(
            session,
            actor,
            "review_decision",
            "claim",
            state["claim_id"],
            {
                "decision": decision,
                "final_amount": final_amount,
                "recommended": rec.get("action"),
                "recommended_payable": rec.get("payable_amount"),
                "notes": review.get("notes"),
            },
        )
        await set_status(session, state["claim_id"], status, actor, {"decision": decision})
        await session.commit()

    # Case memory: one-line summary of findings and decision, for similar-case search.
    try:
        codes = sorted({f["rule_code"] for f in (state.get("rules") or {}).get("findings", [])})
        tier = (state.get("anomaly") or {}).get("tier", "unknown")
        claim = state["claim"]
        summary = (
            f"{claim.get('procedure_code')} at {claim.get('provider_id')}: rules {', '.join(codes) or 'none'}, "
            f"risk {tier}; recommended {rec.get('action')}, adjuster decided {decision}"
            + (f" ({review.get('notes')})" if review.get("notes") else "")
        )
        await get_store().aput(
            ("cases", "outcomes"),
            state["claim_id"],
            {
                "text": summary,
                "claim_id": state["claim_id"],
                "provider_id": claim.get("provider_id"),
                "procedure_code": claim.get("procedure_code"),
                "decision": decision,
                "reason": review.get("notes") or rec.get("explanation", "")[:300],
            },
        )
    except Exception as exc:  # noqa: BLE001 - memory is best-effort, the decision is already recorded
        return {"errors": [f"case memory write failed: {exc}"]}
    return {}
