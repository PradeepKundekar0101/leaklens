"""Split a policy wording into clause chunks.

Splits on clause numbering (^\\d+(\\.\\d+)*\\s) inside the heading hierarchy; tables stay whole; chunks over
~800 tokens are split at sentence boundaries and keep the same clause number.
"""

import re
from dataclasses import dataclass, field

CLAUSE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", re.S)
SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
MAX_CHARS = 3200  # ~800 tokens


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


def chunk_blocks(blocks: list[Block]) -> list[Chunk]:
    sections: dict[str, str] = {}  # top-level number -> title
    chunks: list[Chunk] = []
    current: Chunk | None = None
    current_top: str | None = None

    def flush() -> None:
        nonlocal current
        if current and current.text.strip():
            for part in _split_long(current.text.strip()):
                chunks.append(Chunk(current.clause_no, current.section_path, current.page, part))
        current = None

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        m = CLAUSE.match(text) if not block.is_table else None
        if m:
            number, rest = m.group(1), m.group(2).strip()
            top = number.split(".")[0]
            if "." not in number and len(rest) < 80:
                sections[top] = rest.title() if rest.isupper() else rest
                current_top = top
                flush()
                continue
            flush()
            section = sections.get(top, f"Section {top}")
            current = Chunk(number, f"{top} {section} > {number}", block.page, text)
            continue
        if current is None:
            if current_top is not None:  # a section's introductory text belongs to the section itself
                current = Chunk(current_top, f"{current_top} {sections[current_top]}", block.page, "")
            else:
                current = Chunk("0", "Preamble", block.page, "")
        current.text += ("\n\n" if block.is_table else " ") + text
    flush()
    return chunks


DEFINITION_TERM = re.compile(r"[\"“'‘]([A-Z][A-Za-z\- ]{2,40})[\"”'’]\s+(?:means|shall mean|refers to)")


def defined_terms(text: str) -> list[str]:
    return DEFINITION_TERM.findall(text)


def classify_heuristic(section_path: str, text: str) -> str:
    s = (section_path + " " + text[:200]).lower()
    if "definition" in s or DEFINITION_TERM.search(text):
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
