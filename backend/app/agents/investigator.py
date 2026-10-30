"""Investigator agent: high-risk claims get an evidence-backed report.

ReAct-style loop with MODEL_REASONING, a budget of 8 tool calls, and a schema-validated InvestigationReport.
Every finding must reference a tool result from the same run (checked in code; unsupported findings are dropped).
"""

import json

from app.agents.tools.readonly import INVESTIGATOR_TOOLS
from app.core.config import get_settings
from app.core.pii import mask_payload
from app.services.jsonsafe import to_jsonable
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.schemas import InvestigationReport

TOOL_BUDGET = 8


def check_evidence(report: InvestigationReport, tool_calls: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep findings whose evidence_tool was actually called in this run."""
    called = {c["tool"] for c in tool_calls}
    kept, dropped = [], []
    for f in report.findings:
        (kept if f.evidence_tool in called else dropped).append(f.model_dump())
    return kept, dropped


async def run_investigation(state: dict) -> tuple[dict | None, list[dict], llm.LLMMeta]:
    settings = get_settings()
    system, version = prompts.load("investigator")
    claim = state["claim"]
    brief = mask_payload(
        {
            "claim": {
                k: claim.get(k)
                for k in (
                    "id",
                    "member_id",
                    "product_id",
                    "provider_id",
                    "procedure_code",
                    "diagnosis_code",
                    "admission_at",
                    "discharge_at",
                    "los",
                    "claimed_amount",
                    "policy_start",
                )
            },
            "rule_findings": [
                {k: f.get(k) for k in ("rule_code", "amount_impact", "clause_ref")}
                for f in (state.get("rules") or {}).get("findings", [])
            ],
            "anomaly": {k: (state.get("anomaly") or {}).get(k) for k in ("tier", "risk", "reasons")},
        }
    )
    report, meta = await llm.agent_loop(
        model=settings.model_reasoning,
        system=system,
        user="High-risk claim to investigate:\n" + json.dumps(to_jsonable(brief), indent=1),
        tools=INVESTIGATOR_TOOLS,
        schema=InvestigationReport,
        budget=TOOL_BUDGET,
    )
    if report is None:
        return None, meta.tool_calls, meta
    kept, dropped = check_evidence(report, meta.tool_calls)
    out = {
        "summary": report.summary,
        "findings": kept,
        "dropped_unsupported_findings": dropped,
        "suggested_action": report.suggested_action,
        "open_questions": report.open_questions,
        "incomplete": meta.incomplete,
        "tools_used": sorted({c["tool"] for c in meta.tool_calls}),
        "prompt_version": version,
        "model": meta.model,
    }
    return out, meta.tool_calls, meta
