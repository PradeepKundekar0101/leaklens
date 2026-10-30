"""Payable calculator. The single place that computes what the insurer pays.

Order (documented in the plan, Phase 2):
  1. Remove non-payable items (R05), out-of-stay items (R09) and verified coverage exclusions.
  2. Cap items at contracted tariff (R03) and at MRP (R04).
  3. Apply room and ICU caps with proportional deduction on associated charges (R01, R02).
  4. Apply procedure sub-limits (R07).
  5. Apply deductible, then co-pay (the member's share, not leakage).
  6. Cap at remaining sum insured (R10).
Full-claim findings (R06 waiting period, R08 duplicate) make the payable zero.

leakage = claimed - payable - member_share.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.services.money import inr, pct
from app.services.rules.context import (
    ASSOCIATED_CATEGORIES,
    ICU,
    MRP_CATEGORIES,
    PROCEDURE_CHARGE_CATEGORIES,
    ROOM,
    ZERO,
    ClaimContext,
    q2,
)


@dataclass
class PayableStep:
    step: int
    name: str
    rule_codes: list[str]
    before: Decimal
    after: Decimal
    detail: str

    @property
    def delta(self) -> Decimal:
        return self.before - self.after


@dataclass
class PayableResult:
    claimed: Decimal
    payable: Decimal
    member_share: Decimal
    leakage: Decimal
    steps: list[PayableStep] = field(default_factory=list)
    allowed_by_line: dict[int, Decimal] = field(default_factory=dict)


def is_out_of_stay(ctx: ClaimContext, service_date) -> bool:
    return not (ctx.admission_at <= service_date <= ctx.discharge_at)


def allowed_after_item_rules(ctx: ClaimContext) -> dict[int, Decimal]:
    """Steps 1-2: per-line allowed amounts after removals, tariff and MRP caps."""
    allowed: dict[int, Decimal] = {}
    for li in ctx.line_items:
        if (
            (li.item_code and li.item_code in ctx.non_payable_items)
            or is_out_of_stay(ctx, li.service_date)
            or li.id in ctx.excluded_line_ids
        ):
            allowed[li.id] = ZERO
            continue
        amount = li.amount
        if li.category in MRP_CATEGORIES and li.item_code in ctx.item_mrp:
            amount = min(amount, q2(ctx.item_mrp[li.item_code] * li.qty))
        allowed[li.id] = amount
    if ctx.tariff is not None:
        proc_lines = [li for li in ctx.line_items if li.category in PROCEDURE_CHARGE_CATEGORIES]
        proc_total = sum((allowed[li.id] for li in proc_lines), ZERO)
        if proc_total > ctx.tariff and proc_total > 0:
            ratio = ctx.tariff / proc_total
            running = ZERO
            for i, li in enumerate(proc_lines):
                if i == len(proc_lines) - 1:
                    allowed[li.id] = q2(ctx.tariff - running)  # exact: lines sum to the tariff
                else:
                    allowed[li.id] = q2(allowed[li.id] * ratio)
                    running += allowed[li.id]
    return allowed


def room_icu_ratio(ctx: ClaimContext) -> tuple[Decimal, Decimal | None, Decimal | None]:
    """Proportional-deduction ratio for associated charges: the stricter of the room and ICU ratios."""
    ratio = Decimal(1)
    room_cap, icu_cap = ctx.room_cap(), ctx.icu_cap()
    for li in ctx.items(ROOM):
        if room_cap is not None and li.unit_price > room_cap:
            ratio = min(ratio, room_cap / li.unit_price)
    for li in ctx.items(ICU):
        if icu_cap is not None and li.unit_price > icu_cap:
            ratio = min(ratio, icu_cap / li.unit_price)
    return ratio, room_cap, icu_cap


def apply_room_caps(ctx: ClaimContext, allowed: dict[int, Decimal]) -> dict[int, Decimal]:
    """Step 3."""
    allowed = dict(allowed)
    ratio, room_cap, icu_cap = room_icu_ratio(ctx)
    for li in ctx.line_items:
        if allowed[li.id] == ZERO:
            continue
        if li.category == ROOM and room_cap is not None and li.unit_price > room_cap:
            allowed[li.id] = min(allowed[li.id], q2(room_cap * li.qty))
        elif li.category == ICU and icu_cap is not None and li.unit_price > icu_cap:
            allowed[li.id] = min(allowed[li.id], q2(icu_cap * li.qty))
        elif li.category in ASSOCIATED_CATEGORIES and ratio < 1:
            allowed[li.id] = q2(allowed[li.id] * ratio)
    return allowed


def compute_payable(ctx: ClaimContext, full_claim_rules: list[str] | None = None) -> PayableResult:
    claimed = ctx.claimed_amount
    steps: list[PayableStep] = []
    total = claimed

    def record(step: int, name: str, codes: list[str], after: Decimal, detail: str) -> None:
        nonlocal total
        steps.append(PayableStep(step, name, codes, total, after, detail))
        total = after

    if full_claim_rules:
        record(0, "Full claim disallowed", sorted(full_claim_rules), ZERO, "Waiting-period or duplicate finding")
        return PayableResult(claimed, ZERO, ZERO, claimed, steps, {li.id: ZERO for li in ctx.line_items})

    # Line items may not sum exactly to the claimed amount for live claims; work from the line total.
    line_total = sum((li.amount for li in ctx.line_items), ZERO)
    if line_total and line_total != claimed:
        record(0, "Reconcile to line items", [], line_total, "Claimed amount differs from the sum of line items")

    allowed = {li.id: li.amount for li in ctx.line_items}
    step1 = dict(allowed)
    for li in ctx.line_items:
        if (
            (li.item_code and li.item_code in ctx.non_payable_items)
            or is_out_of_stay(ctx, li.service_date)
            or li.id in ctx.excluded_line_ids
        ):
            step1[li.id] = ZERO
    record(
        1,
        "Remove non-payable and out-of-stay items",
        ["R05", "R09"],
        sum(step1.values(), ZERO),
        "Non-payable consumables, items dated outside the stay, verified exclusions",
    )

    step2 = allowed_after_item_rules(ctx)
    record(
        2,
        "Cap at contracted tariff and MRP",
        ["R03", "R04"],
        sum(step2.values(), ZERO),
        "Procedure charges capped at the package rate; items capped at MRP",
    )

    step3 = apply_room_caps(ctx, step2)
    record(
        3,
        "Room and ICU caps with proportional deduction",
        ["R01", "R02"],
        sum(step3.values(), ZERO),
        "Excess rent removed; nursing, OT and surgeon fees scaled by cap / actual rent",
    )

    sub_limit = ctx.params.sub_limits.get(ctx.procedure_code)
    after4 = min(total, sub_limit) if sub_limit is not None else total
    record(
        4,
        "Procedure sub-limit",
        ["R07"],
        after4,
        f"Sub-limit {inr(sub_limit)}" if sub_limit is not None else "No sub-limit for this procedure",
    )

    eligible = total
    after_deductible = max(ZERO, eligible - ctx.params.deductible)
    copay = q2(after_deductible * ctx.params.copay_pct / 100)
    after5 = after_deductible - copay
    member_share = eligible - after5
    record(
        5,
        "Deductible, then co-pay (member share)",
        [],
        after5,
        f"Deductible {inr(ctx.params.deductible)}, co-pay {pct(ctx.params.copay_pct)}",
    )

    after6 = min(total, max(ZERO, ctx.balance))
    record(6, "Cap at remaining sum insured", ["R10"], after6, f"Remaining sum insured {inr(ctx.balance)}")

    payable = q2(total)
    leakage = q2(claimed - payable - member_share)
    return PayableResult(claimed, payable, q2(member_share), leakage, steps, step3)
