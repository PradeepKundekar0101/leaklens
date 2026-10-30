"""PII masking before prompts: member names, phone numbers and account numbers become stable tokens.

Tokens are keyed HMACs (stable across calls, not reversible without the secret). Unmasking happens only in
the UI, which reads the original values from the database.
"""

import hashlib
import hmac
import re
from typing import Any

from app.core.config import get_settings

NAME_KEYS = frozenset({"name", "member_name", "patient_name", "insured_name", "attendant_name"})
PHONE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
ACCOUNT = re.compile(r"(?<![\d.,])\d{11,18}(?![\d.,])")


def token(kind: str, value: str) -> str:
    digest = hmac.new(get_settings().jwt_secret.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"[{kind}_{digest[:8]}]"


def mask_text(text: str, names: list[str] | None = None) -> str:
    for name in sorted({n for n in (names or []) if n and len(n) > 2}, key=len, reverse=True):
        text = re.sub(re.escape(name), token("PERSON", name.lower()), text, flags=re.IGNORECASE)
    text = PHONE.sub(lambda m: token("PHONE", re.sub(r"\D", "", m.group(0))[-10:]), text)
    return ACCOUNT.sub(lambda m: token("ACCOUNT", m.group(0)), text)


def mask_payload(value: Any, names: list[str] | None = None) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in NAME_KEYS and isinstance(v, str) and v:
                out[k] = token("PERSON", v.lower())
            else:
                out[k] = mask_payload(v, names)
        return out
    if isinstance(value, list):
        return [mask_payload(v, names) for v in value]
    if isinstance(value, str):
        return mask_text(value, names)
    return value
