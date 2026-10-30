"""R01 room rent above cap, R02 ICU rent above ICU cap."""

from decimal import Decimal

from app.services.rules.context import ASSOCIATED_CATEGORIES, ICU, ROOM, ZERO, ClaimContext, RuleFinding, q2
from app.services.rules.engine import rule


def _associated_deduction(ctx: ClaimContext, ratio: Decimal) -> tuple[Decimal, list[dict]]:
    total = ZERO
    detail = []
    for li in ctx.items(*ASSOCIATED_CATEGORIES):
        cut = q2(li.amount * (1 - ratio))
        total += cut
        detail.append({"line_item_id": li.id, "category": li.category, "amount": li.amount, "deduction": cut})
    return total, detail


@rule("R01", "Room rent per day above the policy cap; excess rent plus proportional deduction")
def room_rent_cap(ctx: ClaimContext) -> list[RuleFinding]:
    cap = ctx.room_cap()
    if cap is None:
        return []
    findings = []
    for li in ctx.items(ROOM):
        if li.unit_price <= cap:
            continue
        excess_rent = q2((li.unit_price - cap) * li.qty)
        ratio = cap / li.unit_price
        proportional, detail = _associated_deduction(ctx, ratio)
        findings.append(
            RuleFinding(
                rule_code="R01",
                severity="medium",
                amount_impact=q2(excess_rent + proportional),
                line_item_id=li.id,
                clause_ref=ctx.params.clause("room_rent_cap_pct"),
                evidence={
                    "room_rent_per_day": li.unit_price,
                    "cap_per_day": cap,
                    "cap_pct_of_si": ctx.params.room_rent_cap_pct,
                    "sum_insured": ctx.sum_insured,
                    "days": li.qty,
                    "excess_rent": excess_rent,
                    "ratio": q2(ratio * 100) / 100,
                    "proportional_deduction": proportional,
                    "associated": detail,
                },
            )
        )
    return findings


@rule("R02", "ICU rent per day above the ICU cap; excess plus proportional deduction when R01 did not apply")
def icu_rent_cap(ctx: ClaimContext) -> list[RuleFinding]:
    cap = ctx.icu_cap()
    if cap is None:
        return []
    room_cap = ctx.room_cap()
    room_ratio = min(
        (room_cap / li.unit_price for li in ctx.items(ROOM) if room_cap is not None and li.unit_price > room_cap),
        default=Decimal(1),
    )
    findings = []
    for li in ctx.items(ICU):
        if li.unit_price <= cap:
            continue
        excess = q2((li.unit_price - cap) * li.qty)
        ratio = cap / li.unit_price
        proportional, detail = ZERO, []
        if ratio < room_ratio:  # only the stricter ratio's extra cut is attributed here
            full, detail = _associated_deduction(ctx, ratio)
            already, _ = _associated_deduction(ctx, room_ratio) if room_ratio < 1 else (ZERO, [])
            proportional = full - already
        findings.append(
            RuleFinding(
                rule_code="R02",
                severity="medium",
                amount_impact=q2(excess + proportional),
                line_item_id=li.id,
                clause_ref=ctx.params.clause("icu_cap_pct"),
                evidence={
                    "icu_rent_per_day": li.unit_price,
                    "cap_per_day": cap,
                    "days": li.qty,
                    "excess_rent": excess,
                    "proportional_deduction": proportional,
                    "associated": detail,
                },
            )
        )
    return findings
