"""rules, anomaly, coverage fan-out, join and route."""

from decimal import Decimal

from langgraph.types import Send

from app.agents.state import ClaimState, CoverageTask
from app.core.config import get_settings
from app.db.models import RuleFinding as RuleFindingRow
from app.db.session import session_scope
from app.services.anomaly import scorer
from app.services.jsonsafe import to_jsonable
from app.services.rules.engine import RULES_VERSION, run_rules
from app.services.rules.loader import COVERAGE_EXCLUSION_MIN_CONFIDENCE, load_context
from app.services.rules.payable import compute_payable

COVERAGE_GROUP_SIZE = 10


def payable_dict(result) -> dict:
    return to_jsonable(
        {
            "claimed": result.claimed,
            "payable": result.payable,
            "member_share": result.member_share,
            "leakage": result.leakage,
            "steps": [
                {
                    "step": s.step,
                    "name": s.name,
                    "rule_codes": s.rule_codes,
                    "before": s.before,
                    "after": s.after,
                    "delta": s.delta,
                    "detail": s.detail,
                }
                for s in result.steps
            ],
        }
    )


def finding_dict(f) -> dict:
    return to_jsonable(
        {
            "rule_code": f.rule_code,
            "severity": f.severity,
            "amount_impact": f.amount_impact,
            "line_item_id": f.line_item_id,
            "clause_ref": f.clause_ref,
            "evidence": f.evidence,
            "full_claim": f.full_claim,
        }
    )


async def rules(state: ClaimState) -> dict:
    async with session_scope() as session:
        ctx = await load_context(session, state["claim_id"])
        if ctx is None:
            return {"rules": {}, "errors": ["rules: claim context missing"]}
        out = run_rules(ctx)
        for f in out.findings:
            session.add(
                RuleFindingRow(
                    claim_id=ctx.claim_id,
                    line_item_id=f.line_item_id,
                    rule_code=f.rule_code,
                    severity=f.severity,
                    amount_impact=f.amount_impact,
                    clause_ref=f.clause_ref,
                    evidence=to_jsonable(f.evidence),
                    rules_version=out.rules_version,
                )
            )
        await session.commit()
    return {
        "rules": {
            "findings": [finding_dict(f) for f in out.findings],
            "payable": payable_dict(out.payable),
            "full_claim_codes": out.full_claim_codes,
        },
        "versions": {"rules": RULES_VERSION},
    }


async def anomaly(state: ClaimState) -> dict:
    async with session_scope() as session:
        result = await scorer.score(session, state["claim_id"])
        await session.commit()
    if result is None:
        return {"anomaly": {"unavailable": True}, "errors": ["anomaly: no active model"]}
    return {
        "anomaly": result.as_dict(),
        "versions": {"iforest": result.model_version, "peer_stats": result.model_version},
    }


def fan_out(state: ClaimState) -> list:
    """After load_policy: rules and anomaly always; one coverage task per group of up to 10 line items."""
    sends: list = [Send("rules", state), Send("anomaly", state)]
    items = state.get("line_items") or []
    if get_settings().llm_enabled and items and state["claim"].get("product_id"):
        by_category: dict[str, list[dict]] = {}
        for li in items:
            by_category.setdefault(li["category"], []).append(li)
        for cat_items in by_category.values():
            for i in range(0, len(cat_items), COVERAGE_GROUP_SIZE):
                task: CoverageTask = {
                    "claim_id": state["claim_id"],
                    "run_id": state["run_id"],
                    "product_id": state["claim"]["product_id"],
                    "group": cat_items[i : i + COVERAGE_GROUP_SIZE],
                }
                sends.append(Send("coverage", task))
    return sends


async def coverage(task: CoverageTask) -> dict:
    from app.services.policy.coverage import run_coverage_group

    verdicts, errors, version = await run_coverage_group(task["claim_id"], task["product_id"], task["group"])
    return {"coverage": verdicts, "errors": errors, "versions": {"coverage_prompt": version}}


async def join(state: ClaimState) -> dict:
    """Merge results. Verified not_payable coverage verdicts (confidence >= 0.7) are applied at payable step 1."""
    excluded = {
        v["line_item_id"]
        for v in state.get("coverage") or []
        if v.get("verdict") == "not_payable"
        and v.get("verified")
        and Decimal(str(v.get("confidence", 0))) >= COVERAGE_EXCLUSION_MIN_CONFIDENCE
        and v.get("line_item_id") is not None
    }
    rules_state = dict(state.get("rules") or {})
    if excluded and rules_state:
        async with session_scope() as session:
            ctx = await load_context(session, state["claim_id"])
        if ctx is not None:
            ctx.excluded_line_ids = frozenset(excluded)
            rules_state["payable"] = payable_dict(compute_payable(ctx, rules_state.get("full_claim_codes")))
            rules_state["coverage_exclusions"] = sorted(excluded)
    tier = (state.get("anomaly") or {}).get("tier")
    return {"rules": rules_state, "route": "investigate" if tier == "high" else "standard"}


def route(state: ClaimState) -> str:
    return "investigate" if state.get("route") == "investigate" else "decide"
