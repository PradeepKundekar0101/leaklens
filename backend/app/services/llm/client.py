"""Thin wrapper over the Anthropic SDK.

Rules enforced here:
- Every structured output is validated with a Pydantic schema; invalid output gets one retry with the
  validation error, then the caller receives None and must flag the claim for human review.
- Timeouts (30 s) and API errors get one retry with backoff, then the step is marked unavailable.
- When ANTHROPIC_API_KEY is unset, every call returns None immediately so callers use their
  deterministic fallbacks; nothing in the pipeline depends on an LLM to compute money.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_client: anthropic.AsyncAnthropic | None = None
MIN_MAX_TOKENS = 4000


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        settings = get_settings()
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
        )
        if settings.langsmith_tracing and settings.langsmith_api_key:
            from langsmith.wrappers import wrap_anthropic

            client = wrap_anthropic(client)
        _client = client
    return _client


@dataclass
class LLMMeta:
    model: str
    ok: bool = False
    unavailable: bool = False
    attempts: int = 0
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    incomplete: bool = False
    elapsed_ms: int = 0


async def _create(**kwargs: Any) -> Any:
    """messages.parse with one retry on transport errors (the SDK also retries 429/5xx once)."""
    client = get_client()
    try:
        return await client.messages.parse(**kwargs)
    except (anthropic.APITimeoutError, anthropic.APIConnectionError, anthropic.InternalServerError):
        await asyncio.sleep(1.5)
        return await client.messages.parse(**kwargs)


def _text_of(response: Any) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text")


async def structured[T: BaseModel](
    *,
    model: str,
    system: str,
    user: str | list[dict],
    schema: type[T],
    max_tokens: int = 4000,
    effort: str | None = None,
) -> tuple[T | None, LLMMeta]:
    """One structured call. Returns (None, meta) when the LLM is disabled, unavailable or invalid twice."""
    meta = LLMMeta(model=model)
    if not get_settings().llm_enabled:
        meta.unavailable = True
        meta.error = "llm_disabled"
        return None, meta
    started = time.monotonic()
    content = user if isinstance(user, list) else [{"type": "text", "text": user}]
    messages: list[dict] = [{"role": "user", "content": content}]
    # Current models think adaptively by default and thinking counts against max_tokens, so small limits truncate
    # the JSON. Small extraction/classification tasks on the fast model run at low effort.
    max_tokens = max(max_tokens, MIN_MAX_TOKENS)
    effort = effort or ("low" if model == get_settings().model_fast else None)
    extra: dict[str, Any] = {"output_config": {"effort": effort}} if effort else {}
    for attempt in (1, 2):
        meta.attempts = attempt
        try:
            response = await _create(
                model=model, max_tokens=max_tokens, system=system, messages=messages, output_format=schema, **extra
            )
        except ValidationError as exc:  # the SDK validates while parsing; truncated or malformed JSON lands here
            meta.error = f"invalid_output: {exc.errors()[0].get('msg', exc)}"
            max_tokens *= 2
            messages = [
                *messages,
                {"role": "assistant", "content": "(invalid output)"},
                {
                    "role": "user",
                    "content": f"Your output failed validation: {meta.error}. Return complete JSON "
                    "matching the schema.",
                },
            ]
            continue
        except anthropic.APIError as exc:
            meta.unavailable = True
            meta.error = f"{type(exc).__name__}: {exc}"
            log.warning("llm_unavailable", model=model, error=meta.error)
            break
        meta.input_tokens += response.usage.input_tokens
        meta.output_tokens += response.usage.output_tokens
        try:
            parsed = response.parsed_output
            if parsed is None:
                parsed = schema.model_validate_json(_text_of(response))
            meta.ok = True
            meta.elapsed_ms = int((time.monotonic() - started) * 1000)
            return parsed, meta
        except (ValidationError, ValueError) as exc:
            meta.error = f"invalid_output: {exc}"
            messages = [
                *messages,
                {"role": "assistant", "content": _text_of(response) or "(empty)"},
                {
                    "role": "user",
                    "content": f"Your output failed validation:\n{exc}\nReturn corrected JSON matching the schema.",
                },
            ]
    meta.elapsed_ms = int((time.monotonic() - started) * 1000)
    return None, meta


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[[BaseModel], Awaitable[Any]]

    def spec(self) -> dict:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


async def run_tool(tool: Tool, raw_input: dict) -> tuple[str, bool]:
    try:
        args = tool.input_model.model_validate(raw_input)
        result = await tool.fn(args)
        return json.dumps(result, default=str)[:12000], False
    except ValidationError as exc:
        return f"invalid tool input: {exc}", True
    except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error
        return f"tool error: {type(exc).__name__}: {exc}", True


async def agent_loop[T: BaseModel](
    *,
    model: str,
    system: str,
    user: str,
    tools: list[Tool],
    schema: type[T],
    budget: int,
    max_tokens: int = 8000,
) -> tuple[T | None, LLMMeta]:
    """Manual tool-use loop with a hard tool-call budget, ending in a schema-validated answer.

    When the budget is reached the model is asked to answer with what it has, and meta.incomplete is set.
    """
    meta = LLMMeta(model=model)
    if not get_settings().llm_enabled:
        meta.unavailable = True
        meta.error = "llm_disabled"
        return None, meta
    started = time.monotonic()
    by_name = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    messages: list[dict] = [{"role": "user", "content": user}]
    for _turn in range(budget + 2):
        out_of_budget = len(meta.tool_calls) >= budget
        kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
        if out_of_budget:
            meta.incomplete = True
            kwargs["output_format"] = schema
        else:
            kwargs["tools"] = specs
            kwargs["output_format"] = schema
        try:
            response = await _create(**kwargs)
        except ValidationError as exc:
            if meta.attempts >= 1:
                meta.error = f"invalid_output: {exc.errors()[0].get('msg', exc)}"
                break
            meta.attempts += 1
            messages.append(
                {
                    "role": "user",
                    "content": "Your last answer was not valid JSON for the schema. "
                    "Answer again with complete, valid JSON.",
                }
            )
            continue
        except anthropic.APIError as exc:
            meta.unavailable = True
            meta.error = f"{type(exc).__name__}: {exc}"
            log.warning("llm_unavailable", model=model, error=meta.error)
            return None, meta
        meta.input_tokens += response.usage.input_tokens
        meta.output_tokens += response.usage.output_tokens
        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        if response.stop_reason == "tool_use" and tool_uses and not out_of_budget:
            messages.append({"role": "assistant", "content": response.content})
            remaining = budget - len(meta.tool_calls)
            results = []
            for block in tool_uses:
                if remaining <= 0:
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "budget exhausted",
                            "is_error": True,
                        }
                    )
                    continue
                remaining -= 1
                tool = by_name.get(block.name)
                if tool is None:
                    content, is_error = f"unknown tool {block.name}", True
                else:
                    content, is_error = await run_tool(tool, block.input)
                meta.tool_calls.append({"tool": block.name, "input": block.input, "result": content[:4000]})
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
                )
            messages.append({"role": "user", "content": results})
            continue
        try:
            parsed = response.parsed_output or schema.model_validate_json(_text_of(response))
            meta.ok = True
            meta.elapsed_ms = int((time.monotonic() - started) * 1000)
            return parsed, meta
        except (ValidationError, ValueError) as exc:
            if meta.attempts >= 1:
                meta.error = f"invalid_output: {exc}"
                break
            meta.attempts += 1
            messages.append({"role": "assistant", "content": _text_of(response) or "(empty)"})
            messages.append({"role": "user", "content": f"Output failed validation: {exc}. Return corrected JSON."})
    meta.elapsed_ms = int((time.monotonic() - started) * 1000)
    return None, meta


async def stream_text(*, model: str, system: str, messages: list[dict], max_tokens: int = 4000):
    """Yield text deltas (used by the copilot when no tool calls are pending)."""
    async with get_client().messages.stream(
        model=model, max_tokens=max_tokens, system=system, messages=messages
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def ping() -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        return {"ok": False, "model": settings.model_fast, "error": "ANTHROPIC_API_KEY not set"}
    started = time.monotonic()
    try:
        response = await get_client().messages.create(
            model=settings.model_fast, max_tokens=16, messages=[{"role": "user", "content": "Reply with: pong"}]
        )
    except anthropic.APIError as exc:
        return {"ok": False, "model": settings.model_fast, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "model": settings.model_fast,
        "reply": _text_of(response),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
