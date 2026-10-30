"""Document agent pipeline: classify -> parse (Docling) -> vision route -> extract -> validate (2 re-extractions of
failing pages) -> normalise -> persist line items with page/bbox evidence."""

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.core import audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Claim, ClaimDocument, Item, LineItem, Provider
from app.db.session import session_scope
from app.services.documents import extract as ex
from app.services.documents.normalise import (
    SERVICE_CODES,
    ItemRef,
    classify_category,
    match_item,
    match_provider,
)
from app.services.documents.parse import ParsedDocument, ParsedPage, parse_pdf
from app.services.documents.validate import validate_bill
from app.services.jsonsafe import to_jsonable
from app.services.llm import prompts
from app.services.llm.schemas import BillExtraction
from app.storage import spaces

log = get_logger(__name__)
MAX_REEXTRACT = 2


async def _parse(data: bytes, content_type: str) -> ParsedDocument:
    if content_type != "application/pdf":
        return ParsedDocument([ParsedPage(1)], "image")
    try:
        return await asyncio.to_thread(parse_pdf, data)
    except Exception:  # noqa: BLE001 - treat as an image-only document
        log.exception("docling_parse_failed")
        from app.services.documents.parse import page_count

        return ParsedDocument([ParsedPage(i + 1) for i in range(page_count(data, content_type))], "failed")


async def extract_document(
    data: bytes, content_type: str, parsed: ParsedDocument
) -> tuple[BillExtraction, list[str], str]:
    """Returns (extraction, unresolved issues, route)."""
    llm_on = get_settings().llm_enabled
    vision_pages = [p.number for p in parsed.pages if p.needs_vision]
    if not llm_on:
        bill = ex.extract_from_tables(parsed)
        issues = [i.message for i in validate_bill(bill)]
        if vision_pages and not bill.line_items:
            issues.append("scanned pages need the vision model (ANTHROPIC_API_KEY not set)")
        return bill, issues, "tables"

    parts: list[BillExtraction] = []
    text_pages = ex.pages_for_llm(parsed.pages)
    if text_pages:
        r = await ex.extract_llm(text_pages)
        if r:
            parts.append(r)
    for n in vision_pages:
        r = await ex.extract_vision(data, content_type, n)
        if r:
            parts.append(r)
    bill = ex.merge(parts)
    issues = validate_bill(bill)
    attempt = 0
    while issues and attempt < MAX_REEXTRACT:
        attempt += 1
        failing = sorted({i.page for i in issues if i.page}) or [p.number for p in parsed.pages]
        feedback = "; ".join(i.message for i in issues)[:1500]
        replaced: list[BillExtraction] = []
        for n in failing:
            page = next((p for p in parsed.pages if p.number == n), None)
            if page is None:
                continue
            r = (
                await ex.extract_vision(data, content_type, n, feedback)
                if page.needs_vision
                else await ex.extract_llm([(n, page.text)], feedback)
            )
            if r:
                replaced.append(r)
        if replaced:
            kept = [li for li in bill.line_items if li.page not in failing]
            fresh = ex.merge(replaced)
            bill = bill.model_copy(
                update={
                    "line_items": kept + fresh.line_items,
                    "total": bill.total if bill.total is not None else fresh.total,
                }
            )
        issues = validate_bill(bill)
    route = "vision" if vision_pages else "text"
    return bill, [i.message for i in issues], route


def _bbox_for(parsed: ParsedDocument, description: str, page: int) -> dict | None:
    for p in parsed.pages:
        if p.number != page:
            continue
        for table in p.tables:
            for row in table:
                if row.cells and description.strip().lower() in " ".join(row.cells).lower():
                    return {**row.bbox, "page": page} if row.bbox else None
    return None


async def process_document(doc_id: int) -> dict:
    async with session_scope() as session:
        doc = await session.get(ClaimDocument, doc_id)
        if doc is None:
            raise ValueError(f"document {doc_id} not found")
        claim = await session.get(Claim, doc.claim_id)
        items = [ItemRef(i.item_code, i.name, i.category) for i in (await session.execute(select(Item))).scalars()]
        providers = [(p.id, p.name) for p in (await session.execute(select(Provider))).scalars()]
        doc.parse_status = "parsing"
        await session.commit()
        storage_key, content_type, claim_id = doc.storage_key, doc.content_type, doc.claim_id

    data = await asyncio.to_thread(spaces.download, storage_key)
    parsed = await _parse(data, content_type)
    first_text = parsed.pages[0].text if parsed.pages else ""
    doc_type = await ex.classify(first_text) if first_text.strip() else "bill"

    result: dict = {"document_id": doc_id, "doc_type": doc_type, "parser": parsed.parser}
    bill, issues, route = (BillExtraction(), [], "skipped")
    if doc_type == "bill":
        bill, issues, route = await extract_document(data, content_type, parsed)
    status = "needs_human" if (doc_type == "bill" and issues) else "parsed"

    async with session_scope() as session:
        doc = await session.get(ClaimDocument, doc_id)
        claim = await session.get(Claim, claim_id)
        doc.doc_type = doc_type
        doc.parse_status = status
        doc.pages = len(parsed.pages)
        doc.extracted = to_jsonable(
            {
                "text_fingerprint": (doc.extracted or {}).get("text_fingerprint"),
                "bill": bill.model_dump() if doc_type == "bill" else None,
                "issues": issues,
                "route": route,
                "parser": parsed.parser,
                "text": parsed.text[:50_000],
                "prompt_version": prompts.load("extract")[1],
            }
        )
        n_items = 0
        if doc_type == "bill" and bill.line_items:
            await session.execute(delete(LineItem).where(LineItem.document_id == doc_id))
            adm = claim.admission_at
            for li in bill.line_items:
                ref, _score = match_item(li.description, items) if li.category not in SERVICE_CODES else (None, 0)
                category = ref.category if ref else await classify_category(li.description, li.category)
                if category == "other":
                    category = "consumables"
                session.add(
                    LineItem(
                        claim_id=claim_id,
                        category=category,
                        item_code=ref.item_code if ref else SERVICE_CODES.get(category),
                        description=li.description[:255],
                        qty=li.qty,
                        unit_price=li.unit_price,
                        amount=li.amount,
                        service_date=date.fromisoformat(li.service_date) if li.service_date else adm,
                        document_id=doc_id,
                        page=li.page,
                        bbox=_bbox_for(parsed, li.description, li.page),
                    )
                )
                n_items += 1
            if claim.split == "live":
                total = sum((li.amount for li in bill.line_items), Decimal(0))
                claim.claimed_amount = total
                claim.pharmacy_amount = sum(
                    (li.amount for li in bill.line_items if li.category == "pharmacy"), Decimal(0)
                )
                claim.bill_no = bill.bill_no or claim.bill_no
                room = next((li for li in bill.line_items if li.category == "room"), None)
                if room:
                    claim.room_rent_per_day = room.unit_price
                provider_id = match_provider(bill.hospital_name, providers)
                if provider_id and provider_id != claim.provider_id:
                    result["provider_mismatch"] = provider_id
        await audit.log(
            session,
            audit.agent("document"),
            "document_parsed",
            "claim",
            claim_id,
            {
                "document_id": doc_id,
                "doc_type": doc_type,
                "status": status,
                "route": route,
                "line_items": n_items,
                "issues": issues[:5],
            },
            model=get_settings().model_fast if get_settings().llm_enabled else None,
        )
        await session.commit()
    result.update({"status": status, "route": route, "line_items": n_items, "issues": issues})
    return result


async def process_claim_documents(claim_id: str) -> dict:
    async with session_scope() as session:
        ids = [
            d.id
            for d in (
                await session.execute(
                    select(ClaimDocument).where(
                        ClaimDocument.claim_id == claim_id, ClaimDocument.parse_status.in_(("pending", "failed"))
                    )
                )
            ).scalars()
        ]
    results, errors = [], []
    for doc_id in ids:
        try:
            results.append(await process_document(doc_id))
        except Exception as exc:  # noqa: BLE001
            log.exception("document_failed", document_id=doc_id)
            errors.append(f"document {doc_id}: {exc}")
    return {"documents": results, "errors": errors, "prompt_version": prompts.load("extract")[1]}
