"""Upload validation (type from bytes, size) and bill validation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import filetype

from app.services.llm.schemas import BillExtraction

MAX_BYTES = 15 * 1024 * 1024
ALLOWED = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}
TOLERANCE = Decimal("1.00")


class UploadRejected(ValueError):
    pass


def sniff(data: bytes) -> tuple[str, str]:
    """Returns (content_type, ext) from the file's bytes, never from its name."""
    if len(data) > MAX_BYTES:
        raise UploadRejected(f"file exceeds {MAX_BYTES // (1024 * 1024)} MB")
    if not data:
        raise UploadRejected("empty file")
    kind = filetype.guess(data)
    mime = kind.mime if kind else None
    if mime is None and data[:5] == b"%PDF-":
        mime = "application/pdf"
    if mime not in ALLOWED:
        raise UploadRejected(f"unsupported file type {mime or 'unknown'}; only PDF, PNG and JPEG are accepted")
    return mime, ALLOWED[mime]


@dataclass
class ValidationIssue:
    page: int | None
    message: str


def _date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def validate_bill(bill: BillExtraction) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not bill.line_items:
        return [ValidationIssue(None, "no line items extracted")]
    total = sum((li.amount for li in bill.line_items), Decimal(0))
    if bill.total is not None and abs(total - bill.total) > TOLERANCE:
        issues.append(ValidationIssue(None, f"line items sum to {total} but the bill total is {bill.total}"))
    for li in bill.line_items:
        if abs(li.qty * li.unit_price - li.amount) > TOLERANCE:
            issues.append(
                ValidationIssue(li.page, f"'{li.description}': qty {li.qty} x unit {li.unit_price} != {li.amount}")
            )
    adm, dis = _date(bill.admission_date), _date(bill.discharge_date)
    if adm and dis and dis < adm:
        issues.append(ValidationIssue(None, f"discharge {dis} before admission {adm}"))
    if adm and dis:
        for li in bill.line_items:
            d = _date(li.service_date)
            if d and not (adm <= d <= dis):
                issues.append(ValidationIssue(li.page, f"'{li.description}' service date {d} outside the stay"))
    return issues
