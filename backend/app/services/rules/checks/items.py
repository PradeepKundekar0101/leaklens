"""R03 above contracted tariff, R04 above MRP, R05 non-payable, R09 service date outside the stay."""

from app.services.rules.context import MRP_CATEGORIES, PROCEDURE_CHARGE_CATEGORIES, ZERO, ClaimContext, RuleFinding, q2
from app.services.rules.engine import rule
from app.services.rules.payable import is_out_of_stay


@rule("R03", "Procedure charges (OT + surgeon) above the provider's contracted package rate")
def above_tariff(ctx: ClaimContext) -> list[RuleFinding]:
    if ctx.tariff is None:
        return []
    lines = ctx.items(*PROCEDURE_CHARGE_CATEGORIES)
    total = sum((li.amount for li in lines), ZERO)
    if total <= ctx.tariff:
        return []
    return [
        RuleFinding(
            rule_code="R03",
            severity="medium",
            amount_impact=q2(total - ctx.tariff),
            clause_ref=ctx.params.clause("tariff"),
            evidence={
                "procedure_code": ctx.procedure_code,
                "package_rate": ctx.tariff,
                "procedure_charges": total,
                "lines": [{"line_item_id": li.id, "category": li.category, "amount": li.amount} for li in lines],
            },
        )
    ]


@rule("R04", "Item billed above its MRP")
def above_mrp(ctx: ClaimContext) -> list[RuleFinding]:
    findings = []
    for li in ctx.items(*MRP_CATEGORIES):
        mrp = ctx.item_mrp.get(li.item_code or "")
        if mrp is None or li.unit_price <= mrp:
            continue
        if li.item_code in ctx.non_payable_items or is_out_of_stay(ctx, li.service_date):
            continue  # already fully removed by R05 / R09
        findings.append(
            RuleFinding(
                rule_code="R04",
                severity="low",
                amount_impact=q2((li.unit_price - mrp) * li.qty),
                line_item_id=li.id,
                clause_ref=ctx.params.clause("mrp"),
                evidence={"item_code": li.item_code, "unit_price": li.unit_price, "mrp": mrp, "qty": li.qty},
            )
        )
    return findings


@rule("R05", "Non-payable item billed (IRDAI list)")
def non_payable(ctx: ClaimContext) -> list[RuleFinding]:
    return [
        RuleFinding(
            rule_code="R05",
            severity="low",
            amount_impact=li.amount,
            line_item_id=li.id,
            clause_ref=ctx.params.clause("non_payable"),
            evidence={"item_code": li.item_code, "description": li.description, "amount": li.amount},
        )
        for li in ctx.line_items
        if li.item_code and li.item_code in ctx.non_payable_items
    ]


@rule("R09", "Service date outside the admission-discharge window")
def outside_stay(ctx: ClaimContext) -> list[RuleFinding]:
    return [
        RuleFinding(
            rule_code="R09",
            severity="medium",
            amount_impact=li.amount,
            line_item_id=li.id,
            evidence={
                "service_date": li.service_date,
                "admission_at": ctx.admission_at,
                "discharge_at": ctx.discharge_at,
                "description": li.description,
            },
        )
        for li in ctx.line_items
        if is_out_of_stay(ctx, li.service_date) and not (li.item_code and li.item_code in ctx.non_payable_items)
    ]
