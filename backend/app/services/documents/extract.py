"""Bill extraction.

- LLM path (MODEL_FAST): page text (wrapped as untrusted) -> BillExtraction; vision for pages with < 200 chars.
- Deterministic path (no API key, digital PDFs): read the line-item table Docling found, by header names.
"""

import base64
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.config import get_settings
from app.services.documents.parse import ParsedDocument, ParsedPage, render_page
from app.services.llm import client as llm
from app.services.llm import prompts
from app.services.llm.schemas import BillExtraction, BillLineItem, DocumentClass

AMOUNT = re.compile(r"-?[\d,]+(?:\.\d+)?")
CATEGORY_WORDS = {
    "room": "room",
    "ward": "room",
    "bed": "room",
    "icu": "icu",
    "nursing": "nursing",
    "ot ": "ot",
    "operation theatre": "ot",
    "theatre": "ot",
    "surgeon": "surgeon",
    "surgery": "surgeon",
    "pharmacy": "pharmacy",
    "medicine": "pharmacy",
    "drug": "pharmacy",
    "consumable": "consumables",
    "investigation": "investigations",
    "lab": "investigations",
    "diagnostic": "investigations",
    "implant": "implants",
}


def money(s: str | None) -> Decimal | None:
    if not s:
        return None
    m = AMOUNT.search(s.replace("₹", "").replace("Rs.", ""))
    try:
        return Decimal(m.group(0).replace(",", "")) if m else None
    except InvalidOperation:
        return None


def to_iso(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%d.%m.%Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def classify_heuristic(text: str) -> str:
    t = text.lower()[:3000]
    if "discharge summary" in t:
        return "discharge_summary"
    if "pre-authori" in t or "preauth" in t:
        return "preauth_letter"
    if "prescription" in t or "rx" in t.split():
        return "prescription"
    if "bill" in t or "invoice" in t or "amount" in t:
        return "bill"
    return "other"


async def classify(first_page_text: str) -> str:
    settings = get_settings()
    if not settings.llm_enabled or not first_page_text.strip():
        return classify_heuristic(first_page_text)
    result, _ = await llm.structured(
        model=settings.model_fast,
        system="Classify a hospital document from its first page. " + prompts.UNTRUSTED_NOTE,
        user=prompts.wrap_untrusted(first_page_text[:4000]),
        schema=DocumentClass,
        max_tokens=200,
    )
    return result.doc_type if result else classify_heuristic(first_page_text)


def _field(text: str, *labels: str) -> str | None:
    for label in labels:
        m = re.search(rf"{label}\s*[:#.-]?\s*([^\n|]+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _guess_category(desc: str, explicit: str | None) -> str:
    for source in (explicit or "", desc):
        low = f" {source.lower()} "
        for word, cat in CATEGORY_WORDS.items():
            if word in low:
                return cat
    return "other"


def extract_from_tables(parsed: ParsedDocument) -> BillExtraction:
    """Deterministic extraction from the bill's line-item table (header-driven column mapping)."""
    text = parsed.text
    items: list[BillLineItem] = []
    total: Decimal | None = None
    for page in parsed.pages:
        for table in page.tables:
            if not table:
                continue
            header = [c.lower() for c in table[0].cells]

            def col(*names: str, header: list[str] = header) -> int | None:
                for i, h in enumerate(header):
                    if any(n in h for n in names):
                        return i
                return None

            i_desc, i_amt = col("description", "particular", "item", "service"), col("amount", "total")
            if i_desc is None or i_amt is None:
                continue
            i_qty, i_rate = col("qty", "quantity", "units", "days"), col("rate", "unit", "price")
            i_date, i_cat = col("date"), col("category", "head", "dept")
            for row in table[1:]:
                cells = row.cells
                if len(cells) <= max(i_desc, i_amt):
                    continue
                desc = cells[i_desc]
                amount = money(cells[i_amt])
                if amount is None or not desc:
                    continue
                if re.search(r"\b(grand\s+)?total\b|net payable|amount payable", desc, re.IGNORECASE):
                    total = amount
                    continue
                qty = money(cells[i_qty]) if i_qty is not None and i_qty < len(cells) else None
                rate = money(cells[i_rate]) if i_rate is not None and i_rate < len(cells) else None
                qty = qty or Decimal(1)
                rate = rate if rate is not None else (amount / qty).quantize(Decimal("0.01"))
                items.append(
                    BillLineItem(
                        description=desc,
                        category=_guess_category(
                            desc, cells[i_cat] if i_cat is not None and i_cat < len(cells) else None
                        ),
                        qty=qty,
                        unit_price=rate,
                        amount=amount,
                        service_date=to_iso(cells[i_date]) if i_date is not None and i_date < len(cells) else None,
                        page=page.number,
                    )
                )
    if total is None:
        total = money(_field(text, r"grand total", r"net amount", r"total amount", r"total"))
    return BillExtraction(
        hospital_name=(text.strip().splitlines() or [None])[0],
        bill_no=_field(text, r"bill\s*no", r"invoice\s*no", r"bill number"),
        bill_date=to_iso(_field(text, r"bill\s*date", r"date of bill")),
        patient_name=_field(text, r"patient\s*name", r"patient"),
        admission_date=to_iso(_field(text, r"date of admission", r"admission\s*date", r"admitted\s*on", r"doa")),
        discharge_date=to_iso(_field(text, r"date of discharge", r"discharge\s*date", r"discharged\s*on", r"dod")),
        line_items=items,
        total=total,
    )


async def extract_llm(page_texts: list[tuple[int, str]], feedback: str | None = None) -> BillExtraction | None:
    settings = get_settings()
    system, _ = prompts.load("extract")
    body = "\n\n".join(f"--- page {n} ---\n{t}" for n, t in page_texts)
    user = prompts.wrap_untrusted(body)
    if feedback:
        user += f"\n\nThe previous extraction failed validation: {feedback}. Re-read the page and correct it."
    result, _ = await llm.structured(
        model=settings.model_fast, system=system, user=user, schema=BillExtraction, max_tokens=8000
    )
    return result


async def extract_vision(
    data: bytes, content_type: str, page: int, feedback: str | None = None
) -> BillExtraction | None:
    settings = get_settings()
    system, _ = prompts.load("extract")
    png = render_page(data, content_type, page, dpi=200)
    text = f"This is page {page} of a scanned hospital document. Extract it with the schema."
    if feedback:
        text += f" The previous extraction failed validation: {feedback}."
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode()},
        },
        {"type": "text", "text": text},
    ]
    result, _ = await llm.structured(
        model=settings.model_fast, system=system, user=content, schema=BillExtraction, max_tokens=8000
    )
    if result:
        for li in result.line_items:
            li.page = page
    return result


def merge(parts: list[BillExtraction]) -> BillExtraction:
    out = BillExtraction()
    for p in parts:
        for k in ("hospital_name", "bill_no", "bill_date", "patient_name", "admission_date", "discharge_date", "total"):
            if getattr(out, k) is None and getattr(p, k) is not None:
                setattr(out, k, getattr(p, k))
        out.line_items.extend(p.line_items)
    return out


def pages_for_llm(pages: list[ParsedPage]) -> list[tuple[int, str]]:
    return [(p.number, p.text) for p in pages if not p.needs_vision]


def today() -> date:
    return date.today()
