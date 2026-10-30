"""Render the reference policy wording (fictional insurer, IRDAI standard layout) to data/policies/public/.

    cd backend && uv run python -m scripts.generate_reference_wording [--out PATH]
    uv run python -m scripts.ingest_policy --file ../data/policies/public/SWASTHYA_RAKSHA_PLUS.pdf --product PUBLIC

The layout differs from the synthetic LeakLens wordings on purpose: lettered sections with alphanumeric clause
numbers, definitions set in two columns, a running header, a plan comparison table and form-style annexures.
Content lives in scripts/datagen/reference_wording.py.
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
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    FrameBreak,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from scripts.datagen.common import POLICIES_DIR
from scripts.datagen.reference_wording import (
    DAY_CARE_BY_SPECIALTY,
    DISCLAIMER,
    INSURER,
    PLAN_NAMES,
    PLANS,
    PRODUCT,
    REG_OFFICE,
    UIN,
    VERSION,
    Clause,
    Section,
    illustration_rows,
    lakh,
    schedule_rows,
    sections,
)
from scripts.datagen.wording import NON_PAYABLE_LISTS

rl_config.invariant = 1

INK = colors.HexColor("#1d2b36")
TEAL = colors.HexColor("#0f5e5a")
TINT = colors.HexColor("#e3efed")
RULE = colors.HexColor("#8fa9a6")
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
DEFAULT_OUT = POLICIES_DIR / "public" / "SWASTHYA_RAKSHA_PLUS.pdf"


def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.2,
        alignment=TA_JUSTIFY,
        textColor=INK,
        spaceAfter=5,
    )
    return {
        "body": body,
        "def": ParagraphStyle("def", parent=body, fontSize=8.8, leading=11.8, spaceAfter=5),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=2),
        "section": ParagraphStyle(
            "section",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.white,
            alignment=0,
        ),
        "clause": ParagraphStyle(
            "clause",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=TEAL,
            spaceBefore=6,
            spaceAfter=3,
            alignment=0,
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
            alignment=0,
        ),
        "cover": ParagraphStyle(
            "cover",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=30,
            leading=36,
            textColor=TEAL,
            alignment=TA_CENTER,
        ),
        "center": ParagraphStyle("center", parent=body, alignment=TA_CENTER, fontSize=11, leading=15),
        "small": ParagraphStyle("small", parent=body, fontSize=8, leading=10.5, textColor=colors.HexColor("#4a5a66")),
        "cell": ParagraphStyle("cell", parent=body, fontSize=8.4, leading=10.8, alignment=0, spaceAfter=0),
        "head": ParagraphStyle(
            "head", parent=body, fontName="Helvetica-Bold", fontSize=8.4, leading=10.8, alignment=0, spaceAfter=0
        ),
    }


ST = styles()


def table(rows: list[list[str]], widths_mm: tuple[float, ...], header: bool = True, zebra: bool = True) -> Table:
    data = [
        [Paragraph(str(c), ST["head"] if header and r == 0 else ST["cell"]) for c in row] for r, row in enumerate(rows)
    ]
    t = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), TINT))
    if zebra:
        for r in range(2 if header else 1, len(rows), 2):
            style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f6f9f9")))
    t.setStyle(TableStyle(style))
    return t


def section_band(text: str) -> Table:
    t = Table([[Paragraph(text, ST["section"])]], colWidths=[PAGE_W - 2 * MARGIN], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TEAL),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def clause_flowables(c: Clause, two_column: bool) -> list:
    if not c.paras and not c.table:  # a sub-heading such as B.1 or E.1
        return [CondPageBreak(30 * mm), Paragraph(f"{c.number} {c.title}", ST["sub"])]
    if c.number.startswith("Def. "):
        # Definitions run in: "Def. 12 Hospital means ..."
        text = c.paras[0].replace(f'"{c.title}"', f"<b>{c.title}</b>", 1)
        return [Paragraph(f"<b>{c.number}</b> {text}", ST["def"])]
    out: list = [Paragraph(f"{c.number} {c.title}", ST["clause"])]
    out += [Paragraph(p, ST["body"]) for p in c.paras]
    out += [Paragraph(b, ST["bullet"], bulletText="•") for b in c.bullets]
    if c.table:
        out += [table(c.table, c.widths or (166,)), Spacer(1, 3 * mm)]
    # keep a short clause and its heading together; a long table may split, but never leaves its heading behind
    if not c.table or len(c.table) <= 8:
        return [KeepTogether(out)]
    return [CondPageBreak(80 * mm)] + out


def section_flowables(s: Section) -> list:
    # Two-column sections open on a page whose full-width top frame holds the band and the introduction.
    out: list = [NextPageTemplate("two_start" if s.two_column else "one"), PageBreak()]
    out.append(section_band(f"Section {s.letter} - {s.title}"))
    out.append(Spacer(1, 3 * mm))
    if s.intro:
        out.append(Paragraph(s.intro, ST["body"]))
    if s.two_column:
        out += [NextPageTemplate("two"), FrameBreak()]
    for c in s.clauses:
        out += clause_flowables(c, s.two_column)
    return out


def cover() -> list:
    return [
        Spacer(1, 38 * mm),
        Paragraph(INSURER, ST["center"]),
        Spacer(1, 10 * mm),
        Paragraph(PRODUCT, ST["cover"]),
        Spacer(1, 6 * mm),
        Paragraph("Individual and Family Floater Health Insurance Policy", ST["center"]),
        Paragraph("Policy Wording", ST["center"]),
        Spacer(1, 6 * mm),
        Paragraph(f"UIN: {UIN} &nbsp;&middot;&nbsp; Version {VERSION}", ST["center"]),
        Paragraph("Plans: " + ", ".join(PLAN_NAMES), ST["center"]),
        Spacer(1, 60 * mm),
        Paragraph(DISCLAIMER, ST["small"]),
        Spacer(1, 2 * mm),
        Paragraph(REG_OFFICE, ST["small"]),
    ]


def policy_schedule() -> list:
    """A filled specimen schedule, so the wording has one concrete policy to reason about."""
    details = [
        ["Policy number", "SGI/HL/27/000123456 (specimen)", "Plan", "Premier"],
        ["Policyholder", "A. Specimen", "Policy type", "Family floater"],
        ["Policy period", "01-04-2027 to 31-03-2028", "Base Sum Insured", "Rs. 10,00,000"],
        ["First inception", "01-04-2024", "Cumulative Bonus", "Rs. 2,00,000"],
        ["Zone", "Zone B (Pune)", "Voluntary Deductible", "Rs. 25,000 per Policy Year"],
        ["Premium (incl. GST)", "Rs. 38,412", "Instalments", "Annual"],
        ["TPA", "Specimen Health TPA Pvt. Ltd.", "Intermediary", "Direct"],
    ]
    t = table(details, (32, 51, 32, 51), header=False, zebra=False)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), TINT), ("BACKGROUND", (2, 0), (2, -1), TINT)]))
    insured = [
        ["S. No.", "Insured Person", "Relationship", "Age at entry", "Pre-existing diseases declared"],
        ["1", "A. Specimen", "Self", "58", "Type 2 diabetes mellitus (since 2019)"],
        ["2", "B. Specimen", "Spouse", "62", "Hypertension (since 2016)"],
        ["3", "C. Specimen", "Son", "24", "None"],
        ["4", "D. Specimen", "Daughter", "21", "Bronchial asthma (since 2012)"],
    ]
    return [
        NextPageTemplate("one"),
        PageBreak(),
        section_band("Policy Schedule (specimen)"),
        Spacer(1, 3 * mm),
        Paragraph(
            "The Policy Schedule is issued with every Policy and states the plan, Sum Insured and Insured Persons. "
            "The schedule below is a specimen used in the illustrations; it does not relate to any real person.",
            ST["body"],
        ),
        t,
        Spacer(1, 5 * mm),
        Paragraph("Insured Persons", ST["sub"]),
        table(insured, (14, 36, 28, 24, 64)),
        Spacer(1, 5 * mm),
        Paragraph("Endorsements and special conditions", ST["sub"]),
        Paragraph(
            "1. Co-payment under C.17.1 applies to Insured Person 2 (entry age 62) on every admissible claim.",
            ST["body"],
        ),
        Paragraph(
            "2. The pre-existing diseases declared above are covered after 36 months of continuous coverage from "
            "first inception, that is from 01-04-2027, under D.1.1.",
            ST["body"],
        ),
        Paragraph(
            "3. The Sum Insured was enhanced from Rs. 5,00,000 to Rs. 10,00,000 on 01-04-2026. The waiting periods "
            "in D.1 apply afresh to the enhanced Rs. 5,00,000 from that date.",
            ST["body"],
        ),
        Paragraph(
            "4. Maternity under C.11 is available to Insured Person 4 from 01-04-2026, after 24 months of "
            "continuous coverage.",
            ST["body"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "This schedule must be read with the Policy wording. Please check it on receipt and inform the Company "
            "of any discrepancy within the free look period (E.1.15).",
            ST["small"],
        ),
    ]


def schedule() -> list:
    return [
        NextPageTemplate("one"),
        PageBreak(),
        section_band("Schedule of Benefits"),
        Spacer(1, 3 * mm),
        Paragraph(
            "The table summarises the limits of each plan. The plan opted, the Base Sum Insured and any voluntary "
            "Deductible are stated in the Policy Schedule. Where this summary and the clause it refers to differ, "
            "the clause prevails.",
            ST["body"],
        ),
        table(schedule_rows(), (38, 38, 38, 38, 14)),
    ]


def contents(secs: list[Section]) -> list:
    rows = [[f"Section {s.letter}", s.title] for s in secs] + [
        ["Annexure I", "List of day care procedures"],
        ["Annexure II", "List of items not payable or subsumed (Lists I to IV)"],
        ["Annexure III", "Customer information sheet"],
        ["Annexure IV", "Illustration of proportionate deduction and cost sharing"],
        ["Annexure V", "Claim form (Part A - to be filled by the Insured Person)"],
    ]
    return [
        Spacer(1, 6 * mm),
        Paragraph("Contents", ST["sub"]),
        table(rows, (34, 132), header=False, zebra=False),
    ]


def annexures() -> list:
    out: list = [NextPageTemplate("one"), PageBreak(), section_band("Annexure I - List of day care procedures")]
    out.append(Spacer(1, 3 * mm))
    out.append(
        Paragraph(
            "The procedures below are covered as Day Care Treatment under clause C.4 when undertaken in a Hospital "
            "or Day Care Centre and requiring less than 24 hours of hospitalisation. The list is indicative; a "
            "procedure not listed is covered if it meets the definition of Day Care Treatment in Section B.",
            ST["body"],
        )
    )
    rows = [["S. No.", "Specialty", "Procedure"]]
    n = 0
    for specialty, procs in DAY_CARE_BY_SPECIALTY.items():
        for p in procs:
            n += 1
            rows.append([str(n), specialty, p])
    out.append(table(rows, (14, 52, 100)))

    out += [PageBreak(), section_band("Annexure II - List of items not payable or subsumed"), Spacer(1, 3 * mm)]
    out.append(
        Paragraph(
            "List I sets out items for which no payment is made. Lists II, III and IV set out items that are "
            "payable only as part of the room charge, the procedure charge or the cost of treatment respectively, "
            "and are deducted when billed separately (clause D.3.9). In a Network Provider, items that form part of "
            "an agreed Package Rate are not deducted again.",
            ST["body"],
        )
    )
    for title, items in NON_PAYABLE_LISTS.items():
        heading = Paragraph(title, ST["sub"])
        half = (len(items) + 1) // 2
        rows = [["S. No.", "Item", "S. No.", "Item"]]
        for i in range(half):
            right = [str(half + i + 1), items[half + i]] if half + i < len(items) else ["", ""]
            rows.append([str(i + 1), items[i]] + right)
        t = table(rows, (12, 71, 12, 71))
        out += [KeepTogether([heading, t])] if len(rows) <= 16 else [CondPageBreak(60 * mm), heading, t]

    out += [PageBreak(), section_band("Annexure III - Customer information sheet"), Spacer(1, 3 * mm)]
    out.append(
        Paragraph(
            "This sheet gives a summary of the key features of the Policy for quick reference. It is not a "
            "substitute for the Policy wording, and in case of any difference the wording prevails.",
            ST["body"],
        )
    )
    cis = [
        ["S. No.", "Title", "Description", "Refer to"],
        ["1", "Product name", f"{PRODUCT} (UIN {UIN})", "Cover page"],
        ["2", "Policy type", "Indemnity; individual and family floater", "A.1"],
        [
            "3",
            "Sum insured",
            "; ".join(f"{n}: " + ", ".join(lakh(s) for s in PLANS[n].sum_insured) for n in PLAN_NAMES),
            "E.1.14",
        ],
        [
            "4",
            "What is covered",
            "In-patient hospitalisation, pre- and post-hospitalisation, day care, domiciliary, AYUSH, organ donor, "
            "ambulance, modern treatments; maternity, restoration and air ambulance by plan",
            "C.1 to C.16",
        ],
        [
            "5",
            "What is not covered",
            "Standard exclusions Excl04 to Excl18 and the specific exclusions, including non-payable items",
            "D.2, D.3, Annexure II",
        ],
        [
            "6",
            "Waiting periods",
            "30 days initial; 24 months for specified diseases; pre-existing diseases "
            + ", ".join(f"{n} {PLANS[n].pre_existing_months} months" for n in PLAN_NAMES)
            + "; maternity 24 months",
            "D.1, C.11",
        ],
        [
            "7",
            "Payout basis",
            "Indemnity: actual admissible expenses up to the limits, after Proportionate Deduction where the room "
            "exceeds eligibility",
            "A.3, C.1.4",
        ],
        [
            "8",
            "Cost sharing",
            "20% co-payment for entry age 61 or more and 15% zone co-payment (Classic and Premier); optional "
            "voluntary deductible",
            "C.17",
        ],
        ["9", "Sub-limits", "Room rent and ICU (Classic), cataract, modern treatments, maternity", "C.1.2 to C.11"],
        ["10", "Cumulative bonus", "; ".join(f"{n}: {PLANS[n].cumulative_bonus}" for n in PLAN_NAMES), "C.13"],
        ["11", "Cancellation", "7 days' notice; refund as per the scale in E.1.7 when no claim has been made", "E.1.7"],
        ["12", "Claim procedure", "Cashless at Network Providers; reimbursement within 30 days of discharge", "F"],
        ["13", "Grievance redressal", "Company, Grievance Redressal Officer, Bima Bharosa, Insurance Ombudsman", "G"],
    ]
    out.append(table(cis, (12, 32, 94, 28)))

    out += [
        PageBreak(),
        section_band("Annexure IV - Illustration of proportionate deduction and cost sharing"),
        Spacer(1, 3 * mm),
    ]
    out.append(
        Paragraph(
            "Illustration 1 (clause C.1.4). An Insured Person under the Classic plan with a Base Sum Insured of "
            "Rs. 3,00,000 is eligible for a room of Rs. 3,000 per day (1% of Sum Insured). The Insured Person stays "
            "four days in a room charged at Rs. 6,000 per day for a hernia repair. The eligible room charge is half "
            "the actual room charge, so the Associated Medical Expenses are paid at 50%. Pharmacy, consumables and "
            "the implant are not reduced.",
            ST["body"],
        )
    )
    out.append(table(illustration_rows(), (58, 26, 52, 30)))
    out.append(Spacer(1, 4 * mm))
    out.append(
        Paragraph(
            "Illustration 2 (clause C.17). An Insured Person under the Premier plan, enrolled at age 63, pays a Zone "
            "B premium and is treated in Mumbai (Zone A) for a planned surgery. The admissible amount after all "
            "limits is Rs. 2,00,000. The senior co-payment of 20% is applied first (Rs. 40,000), and the zone "
            "co-payment of 15% is applied to the remaining Rs. 1,60,000 (Rs. 24,000). The Company pays "
            "Rs. 1,36,000 and the Insured Person bears Rs. 64,000.",
            ST["body"],
        )
    )
    out.append(
        Paragraph(
            "Illustration 3 (clauses C.13 and C.14). An Insured Person under the Premier plan with a Base Sum Insured "
            "of Rs. 5,00,000 has a Cumulative Bonus of Rs. 1,00,000 after one claim-free year. A claim of Rs. "
            "5,50,000 for a cardiac procedure exhausts the Sum Insured of Rs. 6,00,000 except Rs. 50,000. Later in "
            "the same Policy Year, a claim of Rs. 3,00,000 for an unrelated fracture is paid from the remaining "
            "Rs. 50,000 and the Restoration Amount of Rs. 5,00,000. A further claim for the same cardiac condition "
            "in that Policy Year cannot use the Restoration Amount.",
            ST["body"],
        )
    )

    out += [
        PageBreak(),
        section_band("Annexure V - Claim form (Part A - to be filled by the Insured Person)"),
        Spacer(1, 3 * mm),
    ]
    out.append(
        Paragraph(
            "Please fill in capital letters, attach the documents listed in F.4 and send the form to the TPA within "
            "the time limits in F.3. Part B is completed by the Hospital.",
            ST["body"],
        )
    )
    form_sections = {
        "A. Details of primary insured": [
            "Policy number",
            "Certificate / health card number",
            "Name of the primary insured",
            "Address and PIN code",
            "Mobile number and e-mail",
        ],
        "B. Details of the Insured Person hospitalised": [
            "Name of the patient",
            "Gender and date of birth",
            "Relationship to primary insured",
            "Occupation",
        ],
        "C. Details of hospitalisation": [
            "Name and city of the Hospital",
            "Room category occupied",
            "Date and time of admission",
            "Date and time of discharge",
            "Injury / illness / maternity",
            "If injury: cause, and whether reported to police",
        ],
        "D. Details of claim": [
            "Pre-hospitalisation expenses (Rs.)",
            "Hospitalisation expenses (Rs.)",
            "Post-hospitalisation expenses (Rs.)",
            "Ambulance charges (Rs.)",
            "Total claimed (Rs.)",
        ],
        "E. Bank details for payment": ["Account holder name", "Bank and branch", "Account number", "IFSC code"],
    }
    for heading, fields in form_sections.items():
        rows = [[heading, ""]] + [[f, ""] for f in fields]
        t = table(rows, (70, 96), zebra=False)
        t.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0)), ("ROWHEIGHT", (0, 1), (-1, -1), 16)]))
        out += [t, Spacer(1, 3 * mm)]
    out.append(
        Paragraph(
            "Declaration: I declare that the information given in this form is true and correct to the best of my "
            "knowledge, and that I have not made or withheld any statement that could affect this claim. I agree "
            "that the Company may obtain my medical records from the Hospital and any Medical Practitioner who "
            "treated me.",
            ST["body"],
        )
    )
    out.append(
        table(
            [["Place", "", "Date", ""], ["Signature of the primary insured", "", "", ""]],
            (40, 50, 26, 50),
            header=False,
            zebra=False,
        )
    )
    return out


class NumberedCanvas(rl_canvas.Canvas):
    """Draws the running header and "Page x of y" footer once the page count is known."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []

    def showPage(self):  # noqa: N802 - reportlab API
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total: int) -> None:
        # No diagonal watermark: real wordings rarely carry one, and it scrambles layout analysis. The cover
        # disclaimer and the footer on every page mark the document as a specimen.
        page = self._pageNumber
        if page == 1:
            return
        self.saveState()
        self.setStrokeColor(TEAL)
        self.setLineWidth(0.8)
        self.line(MARGIN, PAGE_H - 13 * mm, PAGE_W - MARGIN, PAGE_H - 13 * mm)
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(TEAL)
        self.drawString(MARGIN, PAGE_H - 11.5 * mm, INSURER)
        self.setFont("Helvetica", 8)
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 11.5 * mm, f"{PRODUCT} - Policy Wording")
        self.setFillColor(colors.HexColor("#4a5a66"))
        self.setFont("Helvetica", 7.5)
        self.drawString(MARGIN, 10 * mm, f"UIN: {UIN} | Version {VERSION} | Specimen - not an offer of insurance")
        self.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {page} of {total}")
        self.restoreState()


def build(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"{PRODUCT} - Policy Wording",
        author=f"{INSURER} (fictional)",
        subject=f"UIN {UIN} - specimen",
    )
    w, h = doc.width, doc.height
    gap = 7 * mm
    col = (w - gap) / 2
    top = 40 * mm  # band and introduction of a two-column section
    y0 = doc.bottomMargin
    doc.addPageTemplates(
        [
            PageTemplate(id="one", frames=[Frame(MARGIN, y0, w, h, id="f")]),
            PageTemplate(
                id="two_start",
                frames=[
                    Frame(MARGIN, y0 + h - top, w, top, id="t"),
                    Frame(MARGIN, y0, col, h - top, id="s1"),
                    Frame(MARGIN + col + gap, y0, col, h - top, id="s2"),
                ],
            ),
            PageTemplate(
                id="two",
                frames=[Frame(MARGIN, y0, col, h, id="c1"), Frame(MARGIN + col + gap, y0, col, h, id="c2")],
            ),
        ]
    )
    secs = sections()
    story: list = cover() + policy_schedule() + schedule() + contents(secs)
    for s in secs:
        story += section_flowables(s)
    story += annexures()
    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    path = build(a.out)
    pdf = pdfium.PdfDocument(str(path))
    print(f"{path} ({len(pdf)} pages)")
    pdf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
