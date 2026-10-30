"""Coverage agent: one verdict per line item, grounded in a verified, quoted policy clause.

Citation verification: after normalising whitespace and case, the quote must be a substring of a chunk the
agent retrieved in this run with the same clause_no. Otherwise verified=false and the verdict becomes
needs_review. Only verified not_payable verdicts with confidence >= 0.7 change money (payable step 1).
"""

import json
import re

from app.agents.tools import readonly as tools
from app.core.config import get_settings
from app.db.models import CoverageFinding
from app.db.session import session_scope
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.client import Tool
from app.services.llm.schemas import CoverageVerdicts

TOOL_BUDGET = 4


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def verify(verdict: dict, retrieved: list[dict]) -> bool:
    quote, clause = normalise(verdict.get("quote") or ""), (verdict.get("clause_no") or "").strip()
    if not quote or not clause:
        return False
    return any(c.get("clause_no") == clause and quote in normalise(c.get("text", "")) for c in retrieved)


def _tracking_tools(retrieved: list[dict]) -> list[Tool]:
    """Wrap the policy tools so every chunk the agent sees is recorded for citation verification."""

    async def search_policy(args: tools.SearchPolicyIn) -> dict:
        out = await tools.search_policy(args)
        for c in out["chunks"]:
            retrieved.append(c)
            retrieved.extend(d for d in c.get("definitions", []))
        return out

    async def get_definition(args: tools.DefinitionIn) -> dict:
        out = await tools.get_definition(args)
        if out.get("definition"):
            retrieved.append(out["definition"])
        return out

    return [
        Tool(tools.SEARCH_POLICY.name, tools.SEARCH_POLICY.description, tools.SearchPolicyIn, search_policy),
        Tool(tools.GET_DEFINITION.name, tools.GET_DEFINITION.description, tools.DefinitionIn, get_definition),
        tools.GET_POLICY_PARAMS,
        tools.GET_CLAUSE_NOTES,
    ]


async def run_coverage_group(claim_id: str, product_id: str, group: list[dict]) -> tuple[list[dict], list[str], str]:
    settings = get_settings()
    system, version = prompts.load("coverage")
    retrieved: list[dict] = []
    items = [
        {k: li.get(k) for k in ("id", "category", "item_code", "description", "qty", "unit_price", "amount")}
        for li in group
    ]
    user = (
        f"Product: {product_id}\nClaim: {claim_id}\n"
        f"Line items (descriptions come from hospital bills):\n{prompts.wrap_untrusted(json.dumps(items, default=str))}"
        "\nReturn one verdict per line item id."
    )
    result, meta = await llm.agent_loop(
        model=settings.model_reasoning,
        system=system,
        user=user,
        tools=_tracking_tools(retrieved),
        schema=CoverageVerdicts,
        budget=TOOL_BUDGET,
    )
    if result is None:
        return [], [f"coverage unavailable for {len(group)} items: {meta.error}"], version
    ids = {li["id"] for li in group}
    verdicts = []
    for v in result.verdicts:
        if v.line_item_id not in ids:
            continue
        d = v.model_dump()
        d["verified"] = verify(d, retrieved)
        if not d["verified"] and d["verdict"] != "payable":
            d["verdict"] = "needs_review"
        if meta.incomplete:
            d["reason"] = f"{d['reason']} (tool budget reached)"
        verdicts.append(d)
    async with session_scope() as session:
        session.add_all(
            CoverageFinding(
                claim_id=claim_id,
                line_item_id=d["line_item_id"],
                verdict=d["verdict"],
                clause_no=d.get("clause_no"),
                quote=d.get("quote"),
                reason=d["reason"],
                confidence=d["confidence"],
                verified=d["verified"],
            )
            for d in verdicts
        )
        await session.commit()
    return verdicts, [], version
