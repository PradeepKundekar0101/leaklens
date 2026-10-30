"""Docling parsing with page and bounding-box provenance, plus page rendering for the vision route."""

import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import imagehash
import pypdfium2 as pdfium
from PIL import Image

VISION_MIN_CHARS = 200
_converter = None
_lock = Lock()


@dataclass
class TableRow:
    cells: list[str]
    page: int
    bbox: dict | None = None


@dataclass
class ParsedPage:
    number: int
    text: str = ""
    tables: list[list[TableRow]] = field(default_factory=list)
    width: float | None = None
    height: float | None = None

    @property
    def needs_vision(self) -> bool:
        return len(self.text.strip()) < VISION_MIN_CHARS


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    parser: str

    @property
    def text(self) -> str:
        return "\n\n".join(f"--- page {p.number} ---\n{p.text}" for p in self.pages)


def docling_options():
    """Shared Docling settings: no OCR (scans go to the vision model), table structure on, baked-in models."""
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    from app.core.config import get_settings

    path = get_settings().docling_artifacts_path
    return PdfPipelineOptions(do_ocr=False, do_table_structure=True, artifacts_path=path or None)


def _get_converter():
    global _converter
    with _lock:
        if _converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = docling_options()
            _converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    return _converter


def _bbox(b, page_h: float | None) -> dict | None:
    if b is None:
        return None
    try:
        tl = b.to_top_left_origin(page_height=page_h) if page_h else b
        return {"l": tl.l, "t": tl.t, "r": tl.r, "b": tl.b}
    except Exception:  # noqa: BLE001
        return None


def parse_pdf(data: bytes) -> ParsedDocument:
    from docling_core.types.doc import TableItem, TextItem

    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        doc = _get_converter().convert(Path(f.name)).document
    pages: dict[int, ParsedPage] = {}
    for no, page in (doc.pages or {}).items():
        size = getattr(page, "size", None)
        pages[no] = ParsedPage(no, width=getattr(size, "width", None), height=getattr(size, "height", None))
    for item, _level in doc.iterate_items():
        prov = item.prov[0] if getattr(item, "prov", None) else None
        no = prov.page_no if prov else 1
        page = pages.setdefault(no, ParsedPage(no))
        if isinstance(item, TableItem):
            rows: dict[int, list] = {}
            for cell in item.data.table_cells:
                rows.setdefault(cell.start_row_offset_idx, []).append(cell)
            table = []
            for _, cells in sorted(rows.items()):
                cells.sort(key=lambda c: c.start_col_offset_idx)
                boxes = [c.bbox for c in cells if c.bbox is not None]
                bbox = None
                if boxes:
                    merged = _bbox(boxes[0], page.height)
                    for b in boxes[1:]:
                        bb = _bbox(b, page.height)
                        if merged and bb:
                            merged = {
                                "l": min(merged["l"], bb["l"]),
                                "t": min(merged["t"], bb["t"]),
                                "r": max(merged["r"], bb["r"]),
                                "b": max(merged["b"], bb["b"]),
                            }
                    if merged:
                        merged.update({"page_width": page.width, "page_height": page.height})
                    bbox = merged
                table.append(TableRow([c.text.strip() for c in cells], no, bbox))
            page.tables.append(table)
            page.text += "\n" + item.export_to_markdown(doc=doc) + "\n"
        elif isinstance(item, TextItem):
            page.text += item.text + "\n"
    return ParsedDocument([pages[k] for k in sorted(pages)], "docling")


def page_count(data: bytes, content_type: str) -> int:
    if content_type != "application/pdf":
        return 1
    return len(pdfium.PdfDocument(data))


def render_page(data: bytes, content_type: str, page: int = 1, dpi: int = 200) -> bytes:
    """PNG bytes of a page (PDF rendered with pypdfium2; images passed through as PNG)."""
    if content_type == "application/pdf":
        pdf = pdfium.PdfDocument(data)
        image = pdf[page - 1].render(scale=dpi / 72).to_pil()
    else:
        image = Image.open(io.BytesIO(data))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def text_fingerprint(data: bytes, content_type: str) -> str | None:
    """SHA-256 of the PDF's normalised embedded text (None for images and image-only PDFs)."""
    if content_type != "application/pdf":
        return None
    import hashlib

    pdf = pdfium.PdfDocument(data)
    words = " ".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf))).lower().split()
    return hashlib.sha256(" ".join(words).encode()).hexdigest() if len(words) >= 30 else None


PHASH_SIZE = 11  # 121-bit pHash: 64-bit hashes put same-template bills within distance 5 far too often


def perceptual_hash(data: bytes, content_type: str) -> str:
    """Page-1 perceptual hash. The single implementation used by uploads and by the synthetic-data loader."""
    png = render_page(data, content_type, 1, dpi=100)
    return str(imagehash.phash(Image.open(io.BytesIO(png)), hash_size=PHASH_SIZE))
