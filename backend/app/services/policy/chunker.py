"""Split a policy wording into clause chunks.

Two numbering schemes are recognised:
- numeric: "4 Benefits" opens a section and "4.2 Room rent" a clause (the synthetic LeakLens wordings);
- lettered (IRDAI standard layout): "Section C - Benefits" opens a section, "C.1.2 Room rent" a clause and
  "Def. 12 Hospital means ..." a definition. In this scheme numbered list items ("1. ...") are body text.
"Annexure II - ..." headings open a section in both schemes. Tables stay whole; chunks over ~800 tokens are split
at sentence boundaries and keep the same clause number.
"""

import re
from dataclasses import dataclass, field

NUMERIC = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", re.S)
LETTERED = re.compile(r"^([A-Z]\.\d+(?:\.\d+)*)\.?\s+(.*)$", re.S)
DEFINITION_NO = re.compile(r"^(Def\.\s?\d+)\.?\s+(.*)$", re.S)
HEADING = re.compile(r"^(Section|Part|Annexure|Appendix|Schedule)\s+([A-Z]|[IVXL]+|\d+)\s*[-:–—.]\s*(.{2,100})$", re.I)
SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
MAX_CHARS = 3200  # ~800 tokens
MIN_LETTERED = 5  # lettered clause numbers needed before a document is treated as lettered


@dataclass
class Block:
    text: str
    page: int | None
    is_table: bool = False


@dataclass
class Chunk:
    clause_no: str
    section_path: str
    page: int | None
    text: str
    pages: list[int] = field(default_factory=list)


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, current = [], ""
    for sentence in SENTENCE_END.split(text):
        if current and len(current) + len(sentence) + 1 > MAX_CHARS:
            parts.append(current.strip())
            current = ""
        current += sentence + " "
    if current.strip():
        parts.append(current.strip())
    return parts


def detect_scheme(texts: list[str]) -> str:
    lettered = sum(1 for t in texts if LETTERED.match(t.strip()))
    return "lettered" if lettered >= MIN_LETTERED else "numeric"


def clause_start(text: str, scheme: str) -> bool:
    """True when a line starts a new clause or section (used by the plain-text fallback to split paragraphs)."""
    text = text.strip()
    pattern = LETTERED if scheme == "lettered" else NUMERIC
    return bool(pattern.match(text) or DEFINITION_NO.match(text) or HEADING.match(text))


def _heading(m: re.Match) -> tuple[str, str]:
    kind, ident, title = m.group(1).title(), m.group(2), m.group(3).strip()
    key = ident if kind in ("Section", "Part") else f"{kind} {ident}"
    return key, title.title() if title.isupper() else title


def chunk_blocks(blocks: list[Block]) -> list[Chunk]:
    scheme = detect_scheme([b.text for b in blocks if not b.is_table])
    clause_re = LETTERED if scheme == "lettered" else NUMERIC
    sections: dict[str, str] = {}  # section key ("4", "C", "Annexure II") -> title
    chunks: list[Chunk] = []
    current: Chunk | None = None
    current_top: str | None = None

    def flush() -> None:
        nonlocal current
        if current and current.text.strip():
            for part in _split_long(current.text.strip()):
                chunks.append(Chunk(current.clause_no, current.section_path, current.page, part))
        current = None

    def open_section(key: str, title: str) -> None:
        nonlocal current_top, current
        flush()
        sections[key] = title
        current_top = key
        if key.startswith(("Annexure", "Appendix", "Schedule")):
            # annexures have no clause numbers of their own; their content is cited as the annexure
            current = Chunk(key, f"{key} {title}", None, "")

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if not block.is_table:
            if (h := HEADING.match(text)) and len(text) <= 110:
                open_section(*_heading(h))
                if current is not None:
                    current.page = block.page
                continue
            m = DEFINITION_NO.match(text) or clause_re.match(text)
            if m:
                number, rest = re.sub(r"\s+", " ", m.group(1)), m.group(2).strip()
                if scheme == "numeric" and "." not in number and len(rest) < 80:
                    open_section(number, rest.title() if rest.isupper() else rest)
                    continue
                top = (current_top or "Definitions") if number.startswith("Def.") else number.split(".")[0]
                flush()
                section = sections.get(top, top if top.startswith("Annexure") else f"Section {top}")
                path_head = top if top.startswith(("Annexure", "Appendix", "Schedule")) else f"{top} {section}"
                current = Chunk(number, f"{path_head} > {number}", block.page, text)
                continue
        if current is None:
            if current_top is not None:  # a section's introductory text belongs to the section itself
                current = Chunk(current_top, f"{current_top} {sections[current_top]}", block.page, "")
            else:
                current = Chunk("0", "Preamble", block.page, "")
        current.text += ("\n\n" if block.is_table else " ") + text
    flush()
    return chunks


QUOTED_TERM = re.compile(r"[\"“'‘]([A-Z][A-Za-z\- ]{2,40})[\"”'’]\s+(?:means|shall mean|refers to)")
# "Def. 12 Hospital means ..." or "2.18 Hospital means ..." at the start of a definition clause
LEADING_TERM = re.compile(
    r"^(?:Def\.\s?\d+|\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z\-/ ]{2,60}?)\s+(?:means|shall mean|refers to)\b"
)


def defined_terms(text: str) -> list[str]:
    terms = QUOTED_TERM.findall(text)
    if not terms and (m := LEADING_TERM.match(text.strip())):
        terms = [m.group(1).strip()]
    return terms


def classify_heuristic(section_path: str, text: str) -> str:
    s = (section_path + " " + text[:200]).lower()
    if "definition" in s or defined_terms(text):
        return "definition"
    if "waiting" in s:
        return "waiting_period"
    if "sub-limit" in s or "sub limit" in s or "sublimit" in s:
        return "sub_limit"
    if "exclusion" in s or "not payable" in s or "non-payable" in s:
        return "exclusion"
    if "claim" in s and ("procedure" in s or "intimation" in s or "documents" in s):
        return "procedure"
    if "cover" in s or "benefit" in s or "room" in s or "co-pay" in s or "deductible" in s:
        return "benefit"
    return "general"
