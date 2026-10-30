"""Policy wording chunker: numeric (synthetic wordings) and lettered (IRDAI standard layout) numbering."""

from app.services.policy.chunker import Block, chunk_blocks, classify_heuristic, defined_terms, detect_scheme


def _chunks(texts: list[str | tuple[str, bool]]):
    blocks = [Block(t, 1) if isinstance(t, str) else Block(t[0], 1, is_table=t[1]) for t in texts]
    return {c.clause_no: c for c in chunk_blocks(blocks)}


def test_numeric_scheme_sections_clauses_and_annexure():
    chunks = _chunks(
        [
            "Preamble text before any section.",
            "4 Limits",
            "This section sets the limits.",
            "4.2 Room rent. Room rent is payable up to 1% of the Sum Insured per day.",
            ("| Plan | Limit |\n|---|---|\n| Silver | 1% |", True),
            "4.3 ICU. ICU charges are payable up to 2% of the Sum Insured per day.",
            "Annexure I - List of non-payable items",
            "Items in the lists below are not payable.",
            ("| S. No. | Item |\n|---|---|\n| 1 | Baby food |", True),
        ]
    )
    assert set(chunks) == {"0", "4", "4.2", "4.3", "Annexure I"}
    assert chunks["4.2"].section_path == "4 Limits > 4.2"
    assert "| Silver | 1% |" in chunks["4.2"].text  # the table stays with its clause
    assert "Baby food" in chunks["Annexure I"].text  # annexure content is not attributed to clause 4.3
    assert "Baby food" not in chunks["4.3"].text


def test_lettered_scheme_irdai_layout():
    texts = [
        "Section B - Definitions",
        "B.1 Standard definitions",
        "Def. 12 Hospital means an institution established for in-patient care.",
        "Def. 13 Room Rent means the amount charged by a Hospital towards room and boarding expenses.",
        "Section C - Benefits covered under the Policy",
        "The benefits below are available under the plan stated in the Policy Schedule.",
        "C.1 In-patient hospitalisation treatment",
        "The Company will pay the Medical Expenses for Inpatient Care.",
        "C.1.2 Room rent eligibility",
        "Room charges are payable up to the eligibility of the plan opted, as follows:",
        ("| Plan | Room eligibility per day |\n|---|---|\n| Classic | 1% of Sum Insured |", True),
        "C.1.4 Proportionate deduction",
        "1. If the room exceeds eligibility, Associated Medical Expenses are paid proportionately.",
        "2. The reduction does not apply to pharmacy, consumables, implants or diagnostics.",
        "Section D - Waiting periods and exclusions",
        "D.2.6 Hazardous or adventure sports (Code - Excl09)",
        "Expenses related to treatment necessitated by professional hazardous sports.",
    ]
    assert detect_scheme([t for t in texts if isinstance(t, str)]) == "lettered"
    chunks = _chunks(texts)
    assert {"Def. 12", "Def. 13", "C", "C.1", "C.1.2", "C.1.4", "D.2.6"} <= set(chunks)
    assert chunks["Def. 12"].section_path == "B Definitions > Def. 12"
    assert chunks["C.1.2"].section_path == "C Benefits covered under the Policy > C.1.2"
    assert "Classic | 1% of Sum Insured" in chunks["C.1.2"].text
    # numbered list items are body text in a lettered document, not clauses "1" and "2"
    assert "1" not in chunks and "2" not in chunks
    assert "pharmacy, consumables" in chunks["C.1.4"].text
    assert chunks["C"].text.startswith("The benefits below")


def test_defined_terms_quoted_and_leading():
    assert defined_terms('"Hospital" means an institution.') == ["Hospital"]
    assert defined_terms("Def. 43 Room Rent means the amount charged by a Hospital.") == ["Room Rent"]
    assert defined_terms("2.18 Day Care Centre means an institution.") == ["Day Care Centre"]
    assert defined_terms("C.1.2 Room rent eligibility. Room charges are payable.") == []


def test_classify_definition_by_section():
    assert classify_heuristic("B Definitions > Def. 12", "Def. 12 Hospital means an institution.") == "definition"
