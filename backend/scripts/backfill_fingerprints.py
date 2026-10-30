"""Store text fingerprints for documents loaded without one (used by the reused-document check)."""

import asyncio

from sqlalchemy import select

from app.db.models import ClaimDocument
from app.db.session import dispose_engine, session_scope
from app.services.documents.parse import text_fingerprint
from app.storage import spaces


async def main() -> None:
    n = 0
    async with session_scope() as session:
        for doc in (await session.execute(select(ClaimDocument))).scalars():
            if (doc.extracted or {}).get("text_fingerprint"):
                continue
            data = await asyncio.to_thread(spaces.download, doc.storage_key)
            fp = await asyncio.to_thread(text_fingerprint, data, doc.content_type)
            doc.extracted = {**(doc.extracted or {}), "text_fingerprint": fp}
            n += 1
        await session.commit()
    print(f"fingerprinted {n} documents")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
