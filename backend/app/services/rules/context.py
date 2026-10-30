"""Everything a rule needs, loaded up front. Rules never touch the database."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

ROOM, ICU = "room", "icu"
ASSOCIATED_CATEGORIES = frozenset({"nursing", "ot", "surgeon"})
PROCEDURE_CHARGE_CATEGORIES = frozenset({"ot", "surgeon"})
MRP_CATEGORIES = frozenset({"pharmacy", "consumables", "investigations", "implants"})


def q2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def dec(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class LineItemCtx:
    id: int
    category: str
    item_code: str | None
    description: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    service_date: date


@dataclass(frozen=True)
class PolicyParamsCtx:
    room_rent_cap_pct: Decimal | None
    icu_cap_pct: Decimal | None
    copay_pct: Decimal
    deductible: Decimal
    sub_limits: dict[str, Decimal]
    waiting_periods: dict[str, Any]
    clause_refs: dict[str, str]

    def clause(self, key: str) -> str | None:
        return self.clause_refs.get(key)


@dataclass(frozen=True)
class PriorClaim:
    id: str
    provider_id: str
    admission_at: date
    claimed_amount: Decimal
    created_at: datetime | None
    procedure_code: str = ""


@dataclass(frozen=True)
class DocumentMatch:
    document_id: int
    other_claim_id: str
    other_document_id: int
    method: str  # sha256 / phash
    distance: int


@dataclass
class ClaimContext:
    claim_id: str
    member_id: str
    member_policy_id: str
    product_id: str
    provider_id: str
    procedure_code: str
    diagnosis_code: str
    admission_at: date
    discharge_at: date
    claimed_amount: Decimal
    room_rent_per_day: Decimal
    created_at: datetime | None
    sum_insured: Decimal
    balance: Decimal
    policy_start: date
    params: PolicyParamsCtx
    line_items: list[LineItemCtx]
    tariff: Decimal | None = None
    item_mrp: dict[str, Decimal] = field(default_factory=dict)
    non_payable_items: frozenset[str] = frozenset()
    listed_procedures: frozenset[str] = frozenset()
    declared_conditions: frozenset[str] = frozenset()
    prior_claims: list[PriorClaim] = field(default_factory=list)
    document_matches: list[DocumentMatch] = field(default_factory=list)
    excluded_line_ids: frozenset[int] = frozenset()  # verified not_payable coverage verdicts (Phase 7)

    def items(self, *categories: str) -> list[LineItemCtx]:
        return [li for li in self.line_items if li.category in categories]

    def room_cap(self) -> Decimal | None:
        pct = self.params.room_rent_cap_pct
        return None if pct is None else q2(self.sum_insured * pct / 100)

    def icu_cap(self) -> Decimal | None:
        pct = self.params.icu_cap_pct
        return None if pct is None else q2(self.sum_insured * pct / 100)


@dataclass(frozen=True)
class RuleFinding:
    rule_code: str
    severity: str  # low / medium / high
    amount_impact: Decimal
    evidence: dict[str, Any]
    line_item_id: int | None = None
    clause_ref: str | None = None
    full_claim: bool = False
