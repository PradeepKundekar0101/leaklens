"""Extraction evaluation on the generated sample bills (no database writes).

For every bill in data/generated/documents_manifest.csv: parse with Docling, extract (Claude when configured,
Docling tables otherwise; vision for scanned pages), validate, and compare the extracted line-item total with the
claim's true line items. Also checks the prompt-injection canary bill extracts like any other bill.
"""

import argparse
import asyncio
import csv
import json
import time
from decimal import Decimal

from sqlalchemy import text

from app.core.config import DATA_DIR
from app.db.session import dispose_engine, session_scope
from app.services.documents.parse import ParsedDocument, ParsedPage, parse_pdf
from app.services.documents.pipeline import extract_document

TOLERANCE = Decimal("1.00")


async def truth_totals(claim_ids: list[str]) -> dict[str, Decimal]:
    async with session_scope() as s:
        rows = await s.execute(
            text("SELECT claim_id, sum(amount) FROM line_items WHERE claim_id = ANY(:ids) GROUP BY claim_id"),
            {"ids": claim_ids},
        )
        return {cid: total for cid, total in rows.all()}


async def evaluate(limit: int | None, concurrency: int) -> dict:
    manifest = DATA_DIR / "generated" / "documents_manifest.csv"
    rows = [r for r in csv.DictReader(manifest.open()) if r["doc_type"] == "bill"][: limit or None]
    truth = await truth_totals([r["claim_id"] for r in rows])
    sem = asyncio.Semaphore(concurrency)

    async def one(r: dict) -> dict:
        async with sem:
            data = (DATA_DIR / "generated" / "documents" / r["filename"]).read_bytes()
            t0 = time.monotonic()
            try:
                parsed = await asyncio.to_thread(parse_pdf, data)
            except Exception:  # noqa: BLE001
                parsed = ParsedDocument([ParsedPage(1)], "failed")
            bill, issues, route = await extract_document(data, "application/pdf", parsed)
            total = sum((li.amount for li in bill.line_items), Decimal(0))
            expected = truth.get(r["claim_id"])
            return {
                "claim_id": r["claim_id"],
                "filename": r["filename"],
                "scanned": r["scanned"] == "true",
                "canary": r["canary"] == "true",
                "route": route,
                "items": len(bill.line_items),
                "extracted_total": str(total),
                "expected_total": str(expected),
                "match": expected is not None and abs(total - expected) <= TOLERANCE,
                "issues": issues[:3],
                "seconds": round(time.monotonic() - t0, 1),
            }

    results = await asyncio.gather(*(one(r) for r in rows))
    scanned = [r for r in results if r["scanned"]]
    return {
        "bills": len(results),
        "matched": sum(r["match"] for r in results),
        "match_rate": round(sum(r["match"] for r in results) / len(results), 4) if results else None,
        "scanned": len(scanned),
        "scanned_matched": sum(r["match"] for r in scanned),
        "scanned_routes": sorted({r["route"] for r in scanned}),
        "canary_matched": [r["match"] for r in results if r["canary"]],
        "failures": [r for r in results if not r["match"]],
    }


async def main(limit: int | None, concurrency: int) -> None:
    summary = await evaluate(limit, concurrency)
    print(json.dumps(summary, indent=1))
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.concurrency))
