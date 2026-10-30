"""Number guardrail: every number in an LLM explanation must appear in the input JSON.

Numbers are normalised (commas, ₹ and % stripped, compared as Decimals) so "₹1,42,000" matches 142000.00.
Digits inside identifiers such as claim IDs (C0001234) are not treated as numbers.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER = re.compile(r"(?<![\w.])(?:₹|Rs\.?\s?|INR\s?)?(\d[\d,]*(?:\.\d+)?)(%?)(?![\w])")


def _norm(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", "")).normalize()
    except InvalidOperation:
        return None


def numbers_in_text(text: str) -> list[tuple[str, Decimal]]:
    out = []
    for m in NUMBER.finditer(text):
        value = _norm(m.group(1))
        if value is not None:
            out.append((m.group(0), value))
    return out


def _walk(value: Any, sink: set[Decimal]) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _walk(v, sink)
    elif isinstance(value, list | tuple):
        for v in value:
            _walk(v, sink)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, int | float | Decimal):
        d = _norm(str(value))
        if d is not None:
            sink.add(d)
            if isinstance(value, float):  # shares like 0.38 may be written as 38%
                sink.add(_norm(str(round(value * 100))) or d)
                sink.add(_norm(f"{value * 100:.1f}") or d)
    elif isinstance(value, str):
        for _, d in numbers_in_text(value):
            sink.add(d)
        d = _norm(value) if re.fullmatch(r"-?\d[\d,]*(\.\d+)?", value.strip()) else None
        if d is not None:
            sink.add(d)


def allowed_numbers(payload: Any) -> set[Decimal]:
    sink: set[Decimal] = set()
    _walk(json.loads(json.dumps(payload, default=str)), sink)
    return sink


def check_numbers(text: str, payload: Any) -> list[str]:
    """Returns the offending number tokens (empty list = passes)."""
    allowed = allowed_numbers(payload)
    return [raw for raw, value in numbers_in_text(text) if value not in allowed]
