"""Shared response models. Money is Decimal, serialised as a string in JSON."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int


class ClaimListItem(BaseModel):
    id: str
    member_id: str
    member_masked: str
    provider_id: str
    provider_name: str
    procedure_code: str
    procedure_name: str
    admission_at: date
    claimed_amount: Decimal
    payable_amount: Decimal | None
    leakage_amount: Decimal | None
    risk: float | None
    tier: str | None
    action: str | None
    status: str
    split: str


class LineItemOut(BaseModel):
    id: int
    category: str
    item_code: str | None
    description: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    service_date: date
    document_id: int | None
    page: int | None
    bbox: dict | None
    mrp: Decimal | None
    non_payable: bool
    allowed_amount: Decimal | None


class RuleFindingOut(BaseModel):
    id: int
    rule_code: str
    rule_name: str
    severity: str
    amount_impact: Decimal
    line_item_id: int | None
    clause_ref: str | None
    evidence: dict[str, Any]


class CoverageFindingOut(BaseModel):
    id: int
    line_item_id: int | None
    verdict: str
    clause_no: str | None
    quote: str | None
    reason: str
    confidence: float
    verified: bool
    overridden: dict | None


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    filename: str | None
    content_type: str
    pages: int | None
    parse_status: str
    sha256: str
    issues: list[str]
    route: str | None
    created_at: datetime


class RecommendationOut(BaseModel):
    action: str
    claimed_amount: Decimal
    payable_amount: Decimal
    leakage_amount: Decimal
    member_share: Decimal
    confidence: float
    explanation: str
    key_findings: list[str]
    payable_steps: list[dict[str, Any]]
    explanation_source: str
    created_at: datetime


class AnomalyOut(BaseModel):
    model_version: str
    risk: float
    tier: str
    p_z: float
    p_if: float
    max_rz: float
    feature_z: dict[str, Any]
    shap: list[dict[str, Any]]
    reasons: list[dict[str, Any]]


class ReviewOut(BaseModel):
    id: int
    reviewer_id: int
    reviewer_name: str | None
    decision: str
    final_amount: Decimal
    notes: str | None
    created_at: datetime


class ClaimDetail(BaseModel):
    id: str
    status: str
    split: str
    claim_type: str
    bill_no: str | None
    procedure_code: str
    procedure_name: str
    diagnosis_code: str
    admission_at: date
    discharge_at: date
    los: int
    room_category: str
    room_rent_per_day: Decimal
    preauth_amount: Decimal | None
    claimed_amount: Decimal
    pharmacy_amount: Decimal
    created_at: datetime
    member: dict[str, Any]
    policy: dict[str, Any]
    provider: dict[str, Any]
    line_items: list[LineItemOut]
    documents: list[DocumentOut]
    rule_findings: list[RuleFindingOut]
    coverage_findings: list[CoverageFindingOut]
    anomaly: AnomalyOut | None
    recommendation: RecommendationOut | None
    investigation: dict[str, Any] | None
    reviews: list[ReviewOut]
    awaiting_review: bool
    can_review: bool
