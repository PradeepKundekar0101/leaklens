"""Render the policy wording PDF for each synthetic product to data/policies/{product_id}.pdf.

    cd backend && uv run python -m scripts.generate_policy_docs [--out DIR]

The clause structure comes from scripts/datagen/wording.py and every parameter value from data/policies/products.json,
so the clause numbers and values in the PDF match policy_params (including clause_refs) exactly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pypdfium2 as pdfium
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from scripts.datagen.common import POLICIES_DIR, Product, load_products, load_reference
from scripts.datagen.wording import (
    CLAIM_DOCS,
    DAY_CARE,
    INSURER,
    NON_PAYABLE_LISTS,
    build_sections,
    clause_numbers,
    illustration_rows,
    inr,
    pct,
)

rl_config.invariant = 1

ACCENT = colors.HexColor("#123c69")


def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=ss["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        leading=15.5,
        alignment=TA_JUSTIFY,
        spaceAfter=7,
    )
    return {
        "body": body,
        "clause": ParagraphStyle("clause", parent=body, leftIndent=0, spaceAfter=8),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=16, bulletIndent=6, spaceAfter=2),
        "h1": ParagraphStyle(
            "h1",
            parent=ss["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=ACCENT,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=ss["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=ACCENT,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "cover": ParagraphStyle(
            "cover",
            parent=ss["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=ACCENT,
            alignment=TA_CENTER,
        ),
        "center": ParagraphStyle("center", parent=body, alignment=TA_CENTER),
        "small": ParagraphStyle("small", parent=body, fontSize=9, leading=12),
        "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName="Times-Roman", fontSize=10, leading=13),
    }


def _table(rows: list[list[str]], widths: list[float], st, header: bool = True) -> Table:
    data = [[Paragraph(str(c), st["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa8b8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe7f1")))
    t.setStyle(TableStyle(style))
    return t


def build_story(product: Product, ref) -> list:
    st = styles()
    sections = build_sections(product, ref)
    missing = set(product.clause_refs.values()) - clause_numbers(sections)
    if missing:
        raise ValueError(f"{product.id}: clause_refs point to clauses missing from the wording: {sorted(missing)}")
    story: list = []

    # cover
    story += [
        Spacer(1, 50 * mm),
        Paragraph(product.name, st["cover"]),
        Spacer(1, 8 * mm),
        Paragraph("Individual Health Insurance Policy - Policy Wording", st["center"]),
        Paragraph(f"UIN: {product.uin} &nbsp;|&nbsp; Version {product.version}", st["center"]),
        Spacer(1, 30 * mm),
        Paragraph(INSURER, st["center"]),
        Paragraph(
            "This is a synthetic document generated for testing the LeakLens claims auditor. It does not "
            "describe a real insurance product.",
            st["small"],
        ),
        PageBreak(),
    ]

    # preamble and schedule of benefits
    story.append(Paragraph("Preamble", st["h1"]))
    story.append(
        Paragraph(
            f"This Policy is a contract between the Policyholder and {INSURER} (the Company). The proposal, "
            "declaration and any statement made by the Policyholder form the basis of this contract. In "
            "consideration of the premium paid, and subject to the terms, conditions, exclusions and limits contained "
            "herein, the Company agrees to indemnify the Insured Person for medical expenses incurred on "
            "hospitalisation during the Policy period. The headings in this document are for reference only; the "
            "clause numbers (for example 4.2) identify each provision and are quoted in all claim decisions.",
            st["body"],
        )
    )
    story.append(Paragraph("Schedule of benefits", st["h2"]))
    wp = product.waiting_periods
    rows = [
        ["Benefit", "Limit under this product", "Clause"],
        [
            "Sum insured options",
            ", ".join(f"Rs {inr(float(s))}" for s in product.sum_insured_options),
            product.clause_refs["sum_insured"],
        ],
        [
            "Room rent",
            f"{pct(product.room_rent_cap_pct)}% of Sum Insured per day"
            if product.room_rent_cap_pct
            else "No limit (any room category)",
            product.clause_refs["room_rent_cap_pct"],
        ],
        [
            "ICU charges",
            f"{pct(product.icu_cap_pct)}% of Sum Insured per day" if product.icu_cap_pct else "No limit",
            product.clause_refs["icu_cap_pct"],
        ],
        ["Co-payment", f"{pct(product.copay_pct)}% of admissible claim", product.clause_refs["copay_pct"]],
        ["Deductible", f"Rs {inr(float(product.deductible))} per claim", product.clause_refs["deductible"]],
        ["Initial waiting period", f"{wp['initial_days']} days", product.clause_refs["initial_days"]],
        [
            "Specified diseases / procedures",
            f"{wp['listed_conditions_months']} months",
            product.clause_refs["listed_conditions_months"],
        ],
        ["Pre-existing diseases", f"{wp['pre_existing_months']} months", product.clause_refs["pre_existing_months"]],
    ]
    for code, v in product.sub_limits.items():
        rows.append(
            [
                f"Sub-limit: {ref.procedures.set_index('code').loc[code, 'name']}",
                f"Rs {inr(float(v))}",
                product.clause_refs[f"sub_limits.{code}"],
            ]
        )
    rows += [
        ["Pre- / post-hospitalisation", "30 days / 60 days", "2.3, 2.4"],
        ["Road ambulance", "Rs 2,000 per hospitalisation", "2.6"],
    ]
    story.append(_table(rows, [62 * mm, 82 * mm, 22 * mm], st))
    story.append(PageBreak())

    # contents
    story.append(Paragraph("Contents", st["h1"]))
    toc = [[f"Section {s.number}", s.title] for s in sections]
    toc += [
        ["Annexure I", "List of non-payable items"],
        ["Annexure II", "List of day care procedures"],
        ["Annexure III", "Documents required for a claim"],
        ["Annexure IV", "Illustrations"],
    ]
    story.append(_table(toc, [35 * mm, 131 * mm], st, header=False))
    story.append(PageBreak())

    for s in sections:
        story.append(Paragraph(f"{s.number} {s.title}", st["h1"]))
        story.append(Paragraph(s.intro, st["body"]))
        for c in s.clauses:
            para = Paragraph(f"<b>{c.number} {c.title}.</b> {c.text}", st["clause"])
            if c.bullets:
                story.append(KeepTogether([para] + [Paragraph(b, st["bullet"], bulletText="•") for b in c.bullets]))
            else:
                story.append(para)
            if c.number == "4.2" and s.table:
                story.append(_table(s.table, [50 * mm, 58 * mm, 58 * mm], st))
                story.append(Spacer(1, 4 * mm))
        story.append(PageBreak())

    story.append(Paragraph("Annexure I - List of non-payable items", st["h1"]))
    story.append(
        Paragraph(
            f"Items in the lists below are not payable, or are payable only as part of the room, procedure or "
            f"treatment charge, in accordance with clause {product.clause_refs['non_payable']}. Where a hospital bills "
            "them separately, the amount billed is deducted in full.",
            st["body"],
        )
    )
    for title, items in NON_PAYABLE_LISTS.items():
        story.append(Paragraph(title, st["h2"]))
        rows = [["S. No.", "Item"]] + [[str(i), it] for i, it in enumerate(items, start=1)]
        story.append(_table(rows, [20 * mm, 146 * mm], st))
    story.append(PageBreak())
    story.append(Paragraph("Annexure II - List of day care procedures", st["h1"]))
    story.append(
        Paragraph(
            "The following procedures are covered as day care treatment under clause 2.5 when "
            "undertaken in a hospital or day care centre. The list is indicative.",
            st["body"],
        )
    )
    rows = [["S. No.", "Procedure"]] + [[str(i), p] for i, p in enumerate(DAY_CARE, start=1)]
    story.append(_table(rows, [20 * mm, 146 * mm], st))
    story.append(PageBreak())
    story.append(Paragraph("Annexure III - Documents required for a claim", st["h1"]))
    rows = [["S. No.", "Document"]] + [[str(i), d] for i, d in enumerate(CLAIM_DOCS, start=1)]
    story.append(_table(rows, [20 * mm, 146 * mm], st))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Annexure IV - Illustrations", st["h1"]))
    illus = illustration_rows(product)
    if illus:
        story.append(
            Paragraph(
                f"The table below illustrates clause {product.clause_refs['proportional_deduction']} for a stay of "
                "three days in a room charged at 1.5 times the daily limit, with Rs 60,000 of associated medical "
                "expenses (nursing, operation theatre and surgeon fees). Pharmacy, consumables, implants and "
                "investigations are not reduced.",
                st["body"],
            )
        )
        story.append(_table(illus, [22 * mm, 19 * mm, 22 * mm, 12 * mm, 21 * mm, 23 * mm, 23 * mm, 24 * mm], st))
    else:
        story.append(
            Paragraph(
                "This product has no room-rent or ICU limit, so no proportionate deduction applies. "
                "A claim is assessed against the network package rate (clause 4.6), the maximum "
                "retail price (clause 4.5), the sub-limits in Section 6 and the balance Sum Insured.",
                st["body"],
            )
        )
    if product.deductible != "0.00" or product.copay_pct != "0.000":
        story.append(
            Paragraph(
                f"Cost-sharing example: on an admissible amount of Rs 1,00,000 the Insured Person bears a deductible "
                f"of Rs {inr(float(product.deductible))} and then a co-payment of {pct(product.copay_pct)}% of the "
                f"remainder, i.e. Rs {inr((100000 - float(product.deductible)) * float(product.copay_pct) / 100)}; the "
                f"Company pays Rs {inr((100000 - float(product.deductible)) * (1 - float(product.copay_pct) / 100))}.",
                st["body"],
            )
        )
    return story


def render(product: Product, ref, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{product.id}.pdf"

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(20 * mm, 12 * mm, f"{product.name} | UIN {product.uin} | Policy wording v{product.version}")
        canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title=f"{product.name} - Policy wording",
        author=INSURER,
        subject=f"UIN {product.uin}",
    )
    doc.build(build_story(product, ref), onFirstPage=footer, onLaterPages=footer)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=POLICIES_DIR)
    a = ap.parse_args(argv)
    ref = load_reference()
    for product in load_products(ref):
        path = render(product, ref, a.out)
        pdf = pdfium.PdfDocument(str(path))
        print(f"{product.id}: {path} ({len(pdf)} pages)")
        pdf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
