"""Ingest policy wordings into policy_chunks (and extract parameters for approval when the LLM is configured).

Usage: python -m scripts.ingest_policy [PRODUCT_ID ...] [--file path.pdf --product PUBLIC]
"""

import argparse
import asyncio
import time
from pathlib import Path

from sqlalchemy import select

from app.db.models import PolicyProduct
from app.db.session import dispose_engine, session_scope
from app.services.policy import params as policy_params
from app.services.policy.ingest import ingest_product
from app.services.policy.search import search
from app.storage import spaces


async def main(products: list[str], file: str | None, product: str | None) -> None:
    async with session_scope() as session:
        if file:
            pid = product or "PUBLIC"
            if await session.get(PolicyProduct, pid) is None:
                session.add(PolicyProduct(id=pid, name=Path(file).stem, version="public", status="reference"))
                await session.flush()
            data = Path(file).read_bytes()
            spaces.upload(f"policies/{pid}.pdf", data, "application/pdf")
            (await session.get(PolicyProduct, pid)).wording_key = f"policies/{pid}.pdf"
            products = [pid]
        if not products:
            rows = await session.execute(select(PolicyProduct.id).where(PolicyProduct.wording_key.is_not(None)))
            products = list(rows.scalars())
        await session.commit()
    for pid in products:
        t0 = time.monotonic()
        async with session_scope() as session:
            result = await ingest_product(session, pid)
            await session.commit()
        print(
            f"{pid}: {result['chunks']} chunks via {result['parser']} ({result['embed_model']}) "
            f"in {time.monotonic() - t0:.1f}s"
        )
        async with session_scope() as session:
            top = await search(session, pid, "room rent limit", expand_definitions=False)
            if top:
                print(f"  'room rent limit' -> clause {top[0]['clause_no']}: {top[0]['text'][:90]!r}")
            try:
                extraction = await policy_params.extract(session, pid)
                if extraction.get("ok"):
                    changed = [d for d in extraction["diff"] if d["changed"]]
                    print(
                        f"  extracted params: {len(changed)} differ from approved values"
                        + (f" {[d['param'] for d in changed]}" if changed else "")
                    )
                else:
                    print(f"  parameter extraction skipped: {extraction.get('error')}")
            except ValueError as exc:
                print(f"  parameter extraction skipped: {exc}")
            await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("products", nargs="*")
    parser.add_argument("--file")
    parser.add_argument("--product")
    args = parser.parse_args()
    asyncio.run(main(args.products, args.file, args.product))
