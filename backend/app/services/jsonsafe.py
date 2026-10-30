"""Convert Decimals, dates and dataclasses into JSON-safe values (money stays a string, never a float)."""

import dataclasses
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item") and callable(value.item):  # numpy scalars
        return value.item()
    return value
