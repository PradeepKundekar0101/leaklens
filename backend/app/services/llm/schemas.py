"""Pydantic schemas for every LLM output."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    action: str = Field(description="Ignored: copied from the deterministic action policy")
    payable_amount: str = Field(description="Ignored: copied from the payable calculator")
    leakage_amount: str = Field(description="Ignored: copied from the payable calculator")
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(description="3-6 sentences for the adjuster. Only numbers present in the input.")
    key_findings: list[str] = Field(description="Up to 6 short bullet findings, each traceable to the input")


class BillLineItem(BaseModel):
    description: str
    category: Literal[
        "room", "icu", "nursing", "ot", "surgeon", "pharmacy", "consumables", "investigations", "implants", "other"
    ]
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    service_date: str | None = Field(default=None, description="YYYY-MM-DD")
    page: int = 1


class BillExtraction(BaseModel):
    hospital_name: str | None = None
    bill_no: str | None = None
    bill_date: str | None = None
    patient_name: str | None = None
    admission_date: str | None = None
    discharge_date: str | None = None
    line_items: list[BillLineItem] = Field(default_factory=list)
    total: Decimal | None = None


class DocumentClass(BaseModel):
    doc_type: Literal["bill", "discharge_summary", "prescription", "preauth_letter", "other"]
    confidence: float = Field(ge=0, le=1)


class CategoryGuess(BaseModel):
    category: Literal[
        "pharmacy", "consumables", "investigations", "implants", "nursing", "ot", "surgeon", "room", "icu", "other"
    ]


class CoverageVerdict(BaseModel):
    line_item_id: int
    verdict: Literal["payable", "not_payable", "partially_payable", "needs_review"]
    clause_no: str | None = Field(default=None, description="Clause number of the quoted chunk")
    quote: str | None = Field(default=None, description="Verbatim quote from a retrieved chunk with that clause_no")
    reason: str
    confidence: float = Field(ge=0, le=1)


class CoverageVerdicts(BaseModel):
    verdicts: list[CoverageVerdict]


class ClauseType(BaseModel):
    clause_type: Literal["definition", "benefit", "exclusion", "waiting_period", "sub_limit", "procedure", "general"]


class SubLimit(BaseModel):
    procedure_code: str
    limit: Decimal = Field(description="Rupee limit, digits only")
    clause_no: str


class ClauseRef(BaseModel):
    param: str = Field(description="Parameter name, e.g. room_rent_cap_pct")
    clause_no: str


class ExtractedParams(BaseModel):
    """Lists instead of maps: strict structured outputs cannot express free-form object keys."""

    room_rent_cap_pct: Decimal | None = None
    icu_cap_pct: Decimal | None = None
    copay_pct: Decimal = Decimal("0")
    deductible: Decimal = Decimal("0")
    sub_limits: list[SubLimit] = Field(default_factory=list)
    initial_days: int | None = None
    listed_conditions_months: int | None = None
    pre_existing_months: int | None = None
    clause_refs: list[ClauseRef] = Field(default_factory=list)

    def as_params(self) -> dict:
        refs = {r.param: r.clause_no for r in self.clause_refs}
        for s in self.sub_limits:
            refs.setdefault(f"sub_limits.{s.procedure_code}", s.clause_no)
        return {
            "room_rent_cap_pct": self.room_rent_cap_pct,
            "icu_cap_pct": self.icu_cap_pct,
            "copay_pct": self.copay_pct,
            "deductible": self.deductible,
            "sub_limits": {s.procedure_code: s.limit for s in self.sub_limits},
            "initial_days": self.initial_days,
            "listed_conditions_months": self.listed_conditions_months,
            "pre_existing_months": self.pre_existing_months,
            "clause_refs": refs,
        }


class InvestigationFinding(BaseModel):
    statement: str
    evidence_tool: str = Field(description="Name of the tool whose result supports this statement")
    evidence: str = Field(description="The specific fact from that tool result")


class InvestigationReport(BaseModel):
    summary: str
    findings: list[InvestigationFinding]
    suggested_action: Literal["approve", "approve_with_deductions", "investigate", "refer_siu", "query"]
    open_questions: list[str] = Field(default_factory=list)
