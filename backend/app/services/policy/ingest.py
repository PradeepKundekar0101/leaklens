"""Policy ingestion: Docling parse -> clause chunks -> clause_type -> contextual embeddings -> policy_chunks."""

import asyncio
import re
import tempfile
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import PolicyChunk, PolicyProduct
from app.services.documents.parse import docling_options
from app.services.llm import client as llm
from app.services.llm.schemas import ClauseType
from app.services.policy.chunker import Block, Chunk, chunk_blocks, classify_heuristic, clause_start, detect_scheme
from app.services.policy.embed import active_model, embed
from app.storage import spaces

log = get_logger(__name__)
CLAUSE_MARKER = re.compile(r"\d+(?:\.\d+)*")


def _docling_blocks(pdf_path: Path) -> list[Block]:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import TableItem, TextItem

    options = docling_options()
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    doc = converter.convert(str(pdf_path)).document
    blocks: list[Block] = []
    for item, _level in doc.iterate_items():
        page = item.prov[0].page_no if getattr(item, "prov", None) else None
        if isinstance(item, TableItem):
            blocks.append(Block(item.export_to_markdown(doc=doc), page, is_table=True))
        elif isinstance(item, TextItem) and item.text.strip():
            # Docling moves list enumerations ("4.2") into ListItem.marker; put clause numbers back in the text.
            marker = (getattr(item, "marker", "") or "").strip().rstrip(".")
            text = item.text
            if marker and CLAUSE_MARKER.fullmatch(marker) and not text.lstrip().startswith(marker):
                text = f"{marker} {text}"
            blocks.append(Block(text, page))
    return blocks


def _pdfium_blocks(pdf_path: Path) -> list[Block]:
    """Fallback when Docling fails: lines joined into paragraphs that break at clause numbers, with page numbers."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    pages = [
        [ln.strip() for ln in pdf[i].get_textpage().get_text_range().splitlines() if ln.strip()]
        for i in range(len(pdf))
    ]
    scheme = detect_scheme([ln for page in pages for ln in page])
    blocks = []
    for i, lines in enumerate(pages):
        paragraph = ""
        for line in lines:
            if paragraph and clause_start(line, scheme):
                blocks.append(Block(paragraph, i + 1))
                paragraph = ""
            paragraph = f"{paragraph} {line}".strip()
        if paragraph:
            blocks.append(Block(paragraph, i + 1))
    return blocks


def parse_pdf(data: bytes) -> tuple[list[Chunk], str]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        path = Path(f.name)
        try:
            blocks, parser = _docling_blocks(path), "docling"
        except Exception:  # noqa: BLE001 - fall back to plain text extraction
            log.exception("docling_failed_falling_back")
            blocks, parser = _pdfium_blocks(path), "pypdfium2"
    chunks = chunk_blocks(blocks)
    if len(chunks) < 5 and parser == "docling":
        chunks, parser = chunk_blocks(_pdfium_blocks_from_bytes(data)), "pypdfium2"
    return chunks, parser


def _pdfium_blocks_from_bytes(data: bytes) -> list[Block]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        return _pdfium_blocks(Path(f.name))


async def classify(chunk: Chunk) -> str:
    heuristic = classify_heuristic(chunk.section_path, chunk.text)
    settings = get_settings()
    if not settings.llm_enabled:
        return heuristic
    result, _ = await llm.structured(
        model=settings.model_fast,
        system="Classify this insurance policy clause. Reply with the clause_type only.",
        user=f"Section: {chunk.section_path}\nClause {chunk.clause_no}:\n{chunk.text[:2000]}",
        schema=ClauseType,
        max_tokens=200,
    )
    return result.clause_type if result else heuristic


async def ingest_bytes(session: AsyncSession, product_id: str, data: bytes) -> dict:
    chunks, parser = await asyncio.to_thread(parse_pdf, data)
    product = await session.get(PolicyProduct, product_id)
    name = product.name if product else product_id
    sem = asyncio.Semaphore(8)

    async def _cls(c: Chunk) -> str:
        async with sem:
            return await classify(c)

    types = await asyncio.gather(*(_cls(c) for c in chunks))
    contextual = [f"{name} > {c.section_path} > {c.clause_no}: {c.text}" for c in chunks]
    vectors = await embed(contextual)
    await session.execute(delete(PolicyChunk).where(PolicyChunk.product_id == product_id))
    model = active_model()
    session.add_all(
        PolicyChunk(
            product_id=product_id,
            section_path=c.section_path,
            clause_no=c.clause_no,
            clause_type=t,
            page=c.page,
            text=c.text,
            embedding=v,
            embed_model=model,
        )
        for c, t, v in zip(chunks, types, vectors, strict=True)
    )
    await session.flush()
    return {"product_id": product_id, "chunks": len(chunks), "parser": parser, "embed_model": model}


async def ingest_product(session: AsyncSession, product_id: str) -> dict:
    product = await session.get(PolicyProduct, product_id)
    if product is None or not product.wording_key:
        raise ValueError(f"no wording uploaded for {product_id}")
    data = await asyncio.to_thread(spaces.download, product.wording_key)
    return await ingest_bytes(session, product_id, data)
