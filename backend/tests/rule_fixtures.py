"""Builders for hand-computed rule tests."""

from datetime import date, datetime
from decimal import Decimal as D

from app.services.rules.context import ClaimContext, LineItemCtx, PolicyParamsCtx, PriorClaim

ADM, DIS = date(2026, 9, 10), date(2026, 9, 13)


def line(
    id: int,
    category: str,
    amount: str,
    *,
    code: str | None = None,
    qty: str = "1",
    unit: str | None = None,
    day: date | None = None,
) -> LineItemCtx:
    qty_d = D(qty)
    unit_d = D(unit) if unit is not None else D(amount) / qty_d
    return LineItemCtx(id, category, code or category.upper(), category, qty_d, unit_d, D(amount), day or ADM)


def params(**overrides) -> PolicyParamsCtx:
    base = dict(
        room_rent_cap_pct=D("1.0"),
        icu_cap_pct=D("2.0"),
        copay_pct=D("0"),
        deductible=D("0"),
        sub_limits={},
        waiting_periods={
            "initial_days": 30,
            "listed_conditions_months": 24,
            "pre_existing_months": 36,
            "listed_procedures": ["PR_CATARACT"],
        },
        clause_refs={
            "room_rent_cap_pct": "4.2",
            "icu_cap_pct": "4.3",
            "initial_days": "5.1",
            "listed_conditions_months": "5.2",
            "pre_existing_months": "5.3",
        },
    )
    base.update(overrides)
    return PolicyParamsCtx(**base)


def ctx(lines: list[LineItemCtx], **overrides) -> ClaimContext:
    claimed = sum((li.amount for li in lines), D("0"))
    base = dict(
        claim_id="C1",
        member_id="M1",
        member_policy_id="MP1",
        product_id="GOLD",
        provider_id="H001",
        procedure_code="PR_APPENDECTOMY",
        diagnosis_code="K35",
        admission_at=ADM,
        discharge_at=DIS,
        claimed_amount=claimed,
        room_rent_per_day=D("0"),
        created_at=datetime(2026, 9, 14, 10, 0),
        sum_insured=D("500000"),
        balance=D("500000"),
        policy_start=date(2023, 1, 1),
        params=params(),
        line_items=lines,
        item_mrp={"DRUG1": D("100"), "GLOVES": D("50")},
        non_payable_items=frozenset({"GLOVES"}),
        listed_procedures=frozenset({"PR_CATARACT"}),
    )
    base.update(overrides)
    return ClaimContext(**base)


def prior(
    id: str, amount: str, admission: date = ADM, provider: str = "H001", created: datetime = datetime(2026, 9, 14, 9, 0)
) -> PriorClaim:
    return PriorClaim(id, provider, admission, D(amount), created)
