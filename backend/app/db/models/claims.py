"""Claims, line items, documents and analysis results."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, Json, Money

CLAIM_STATUSES = (
    "received",
    "processing",
    "pending_review",
    "approved",
    "approved_with_deductions",
    "queried",
    "investigating",
    "rejected",
    "failed",
)


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        Index("ix_claims_status", "status"),
        Index("ix_claims_provider_id", "provider_id"),
        Index("ix_claims_member_policy_admission", "member_policy_id", "admission_at"),
        Index("ix_claims_split", "split"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    member_policy_id: Mapped[str] = mapped_column(ForeignKey("member_policies.id"))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"))
    procedure_code: Mapped[str] = mapped_column(ForeignKey("procedures.code"))
    diagnosis_code: Mapped[str] = mapped_column(String(32))
    admission_at: Mapped[date] = mapped_column(Date)
    discharge_at: Mapped[date] = mapped_column(Date)
    los: Mapped[int] = mapped_column(Integer)
    room_category: Mapped[str] = mapped_column(String(32))
    room_rent_per_day: Mapped[Money]
    preauth_amount: Mapped[Money | None]
    claimed_amount: Mapped[Money]
    pharmacy_amount: Mapped[Money]
    claim_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="received")
    split: Mapped[str] = mapped_column(String(8))
    bill_no: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[CreatedAt]


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    item_code: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Numeric(10, 2))
    unit_price: Mapped[Money]
    amount: Mapped[Money]
    service_date: Mapped[date] = mapped_column(Date)
    document_id: Mapped[int | None] = mapped_column(BigInteger)
    page: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[Json | None]


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(32), default="other")
    storage_key: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[str | None] = mapped_column(String(32))
    pages: Mapped[int | None] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    extracted: Mapped[Json | None]
    created_at: Mapped[CreatedAt]


class RuleFinding(Base):
    __tablename__ = "rule_findings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    line_item_id: Mapped[int | None] = mapped_column(BigInteger)
    rule_code: Mapped[str] = mapped_column(String(8))
    severity: Mapped[str] = mapped_column(String(8))
    amount_impact: Mapped[Money]
    clause_ref: Mapped[str | None] = mapped_column(String(32))
    evidence: Mapped[Json]
    rules_version: Mapped[str] = mapped_column(String(16))


class CoverageFinding(Base):
    __tablename__ = "coverage_findings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    line_item_id: Mapped[int | None] = mapped_column(BigInteger)
    verdict: Mapped[str] = mapped_column(String(20))
    clause_no: Mapped[str | None] = mapped_column(String(32))
    quote: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    overridden: Mapped[Json | None]


class AnomalyScore(Base):
    __tablename__ = "anomaly_scores"

    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(32))
    risk: Mapped[float] = mapped_column(Numeric(6, 5))
    tier: Mapped[str] = mapped_column(String(8))
    p_z: Mapped[float] = mapped_column(Numeric(6, 5))
    p_if: Mapped[float] = mapped_column(Numeric(6, 5))
    max_rz: Mapped[float] = mapped_column(Numeric(8, 3))
    feature_z: Mapped[Json]
    shap: Mapped[Json]
    reasons: Mapped[Json]
    created_at: Mapped[CreatedAt]


class Recommendation(Base):
    __tablename__ = "recommendations"

    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    action: Mapped[str] = mapped_column(String(32))
    claimed_amount: Mapped[Money]
    payable_amount: Mapped[Money]
    leakage_amount: Mapped[Money]
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    explanation: Mapped[str] = mapped_column(Text)
    key_findings: Mapped[Json]
    payable_steps: Mapped[Json]
    explanation_source: Mapped[str] = mapped_column(String(16), default="llm")  # llm / template
    run_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[CreatedAt]


class Investigation(Base):
    __tablename__ = "investigations"

    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    report: Mapped[Json]
    tool_calls: Mapped[Json]
    run_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[CreatedAt]


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))
    final_amount: Mapped[Money]
    notes: Mapped[str | None] = mapped_column(Text)
    overrides: Mapped[Json | None]
    created_at: Mapped[CreatedAt]


class ProviderStats(Base):
    __tablename__ = "provider_stats"

    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), primary_key=True)
    period: Mapped[date] = mapped_column(Date, primary_key=True)  # first day of month
    claims: Mapped[int] = mapped_column(Integer)
    claimed_total: Mapped[Money]
    leakage_total: Mapped[Money]
    flag_rate: Mapped[float] = mapped_column(Numeric(6, 4))
    oe_index: Mapped[float] = mapped_column(Numeric(8, 4))
    avg_pharmacy_share: Mapped[float] = mapped_column(Numeric(6, 4))
    peer_pharmacy_share: Mapped[float] = mapped_column(Numeric(6, 4))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GroundTruth(Base):
    """Used only by evaluation scripts. Detection code must never read this table."""

    __tablename__ = "ground_truth"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    scenario: Mapped[str] = mapped_column(String(48))
    leakage_amount: Mapped[Money]
