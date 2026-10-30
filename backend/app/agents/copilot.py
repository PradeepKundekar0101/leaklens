"""Adjuster copilot: streaming chat about one claim, with read-only tools (budget 6 per message).

thread_id = copilot:{claim_id}:{user_id}; history is kept in the LangGraph store under ("copilot", thread_id).
"""

import json
from collections.abc import AsyncIterator

import anthropic

from app.agents import runtime
from app.agents.tools.readonly import COPILOT_TOOLS, ClaimIn, get_claim_state
from app.core.config import get_settings
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.money import inr

TOOL_BUDGET = 6
HISTORY_TURNS = 12


def thread_id(claim_id: str, user_id: int) -> str:
    return f"copilot:{claim_id}:{user_id}"


async def load_history(tid: str) -> list[dict]:
    item = await runtime.store().aget(("copilot",), tid)
    return (item.value.get("messages") if item else None) or []


async def save_history(tid: str, messages: list[dict]) -> None:
    await runtime.store().aput(("copilot",), tid, {"messages": messages[-HISTORY_TURNS * 2 :]}, index=False)


async def _fallback(claim_id: str) -> str:
    state = await get_claim_state(ClaimIn(claim_id=claim_id))
    rec = state.get("recommendation") or {}
    findings = state.get("rule_findings") or []
    lines = ["The language model is not configured (ANTHROPIC_API_KEY), so here is the stored analysis."]
    if rec:
        lines.append(
            f"Recommendation: {rec.get('action')} - payable {inr(rec.get('payable_amount'))}, "
            f"leakage {inr(rec.get('leakage_amount'))}."
        )
        lines.append(rec.get("explanation") or "")
    for f in findings:
        clause = f" (clause {f['clause_ref']})" if f.get("clause_ref") else ""
        lines.append(f"- {f['rule_code']}{clause}: {inr(f['amount_impact'])}")
    anomaly = state.get("anomaly") or {}
    for r in (anomaly.get("reasons") or [])[:3]:
        lines.append(f"- {r.get('text')}")
    return "\n".join(x for x in lines if x)


async def chat(claim_id: str, user_id: int, message: str) -> AsyncIterator[dict]:
    """Yields events: {"type": "text", "delta"}, {"type": "tool", "name", "input"}, {"type": "done", ...}."""
    tid = thread_id(claim_id, user_id)
    history = await load_history(tid)
    settings = get_settings()
    if not settings.llm_enabled:
        text = await _fallback(claim_id)
        yield {"type": "text", "delta": text}
        await save_history(
            tid, [*history, {"role": "user", "content": message}, {"role": "assistant", "content": text}]
        )
        yield {"type": "done", "tool_calls": 0, "source": "fallback"}
        return

    system, version = prompts.load("copilot")
    system = system.replace("{{CLAIM_ID}}", claim_id)
    by_name = {t.name: t for t in COPILOT_TOOLS}
    specs = [t.spec() for t in COPILOT_TOOLS]
    messages: list[dict] = [*history, {"role": "user", "content": message}]
    calls = 0
    final_text = ""
    client = llm.get_client()
    while True:
        kwargs = {"model": settings.model_reasoning, "max_tokens": 4000, "system": system, "messages": messages}
        if calls < TOOL_BUDGET:
            kwargs["tools"] = specs
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    final_text += text
                    yield {"type": "text", "delta": text}
                response = await stream.get_final_message()
        except anthropic.APIError as exc:
            yield {"type": "error", "message": f"model unavailable: {type(exc).__name__}"}
            break
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            break
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            if calls >= TOOL_BUDGET:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "tool budget exhausted",
                        "is_error": True,
                    }
                )
                continue
            calls += 1
            yield {"type": "tool", "name": block.name, "input": block.input}
            tool = by_name.get(block.name)
            content, is_error = (
                (await llm.run_tool(tool, block.input)) if tool else (f"unknown tool {block.name}", True)
            )
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
        if final_text and not final_text.endswith("\n"):
            final_text += "\n\n"
            yield {"type": "text", "delta": "\n\n"}
    await save_history(
        tid,
        [*history, {"role": "user", "content": message}, {"role": "assistant", "content": final_text or "(no answer)"}],
    )
    yield {"type": "done", "tool_calls": calls, "source": "llm", "prompt_version": version}


def sse(event: dict) -> str:
    return json.dumps(event, default=str)
