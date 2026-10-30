"""R06 waiting period, R07 sub-limit, R10 remaining sum insured."""

from datetime import date

from app.services.rules.context import ZERO, ClaimContext, RuleFinding, q2
from app.services.rules.engine import rule
from app.services.rules.payable import allowed_after_item_rules, apply_room_caps


def add_months(d: date, months: int) -> date:
    year, month = divmod(d.month - 1 + months, 12)
    year += d.year
    month += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


@rule("R06", "Admission within a waiting period for the diagnosis")
def waiting_period(ctx: ClaimContext) -> list[RuleFinding]:
    wp = ctx.params.waiting_periods
    start, adm = ctx.policy_start, ctx.admission_at
    reasons = []
    initial = int(wp.get("initial_days", 0))
    if initial and (adm - start).days < initial:
        reasons.append(("initial", f"admission {(adm - start).days} days after policy start (< {initial})"))
    listed_months = int(wp.get("listed_conditions_months", 0))
    if listed_months and ctx.procedure_code in ctx.listed_procedures and adm < add_months(start, listed_months):
        reasons.append(("listed_condition", f"{ctx.procedure_code} is a listed condition ({listed_months} months)"))
    ped_months = int(wp.get("pre_existing_months", 0))
    if ped_months and ctx.diagnosis_code in ctx.declared_conditions and adm < add_months(start, ped_months):
        reasons.append(("pre_existing", f"{ctx.diagnosis_code} declared pre-existing ({ped_months} months)"))
    if not reasons:
        return []
    kind = reasons[0][0]
    clause_key = {"initial": "initial_days", "listed_condition": "listed_conditions_months"}.get(
        kind, "pre_existing_months"
    )
    return [
        RuleFinding(
            rule_code="R06",
            severity="high",
            amount_impact=ctx.claimed_amount,
            clause_ref=ctx.params.clause(clause_key) or ctx.params.clause("waiting_periods"),
            full_claim=True,
            evidence={
                "policy_start": start,
                "admission_at": adm,
                "days_since_start": (adm - start).days,
                "reasons": [r[1] for r in reasons],
                "kind": kind,
            },
        )
    ]


@rule("R07", "Procedure sub-limit exceeded")
def sub_limit(ctx: ClaimContext) -> list[RuleFinding]:
    limit = ctx.params.sub_limits.get(ctx.procedure_code)
    if limit is None:
        return []
    running = sum(apply_room_caps(ctx, allowed_after_item_rules(ctx)).values(), ZERO)
    if running <= limit:
        return []
    return [
        RuleFinding(
            rule_code="R07",
            severity="medium",
            amount_impact=q2(running - limit),
            clause_ref=ctx.params.clause(f"sub_limits.{ctx.procedure_code}") or ctx.params.clause("sub_limits"),
            evidence={"procedure_code": ctx.procedure_code, "sub_limit": limit, "eligible_before_limit": running},
        )
    ]


@rule("R10", "Claim exceeds the remaining sum insured")
def remaining_sum_insured(ctx: ClaimContext) -> list[RuleFinding]:
    from app.services.rules.payable import compute_payable

    result = compute_payable(ctx)
    six = next((s for s in result.steps if s.step == 6), None)
    if six is None or six.delta <= 0:
        return []
    return [
        RuleFinding(
            rule_code="R10",
            severity="medium",
            amount_impact=q2(six.delta),
            clause_ref=ctx.params.clause("sum_insured"),
            evidence={"remaining_sum_insured": ctx.balance, "payable_before_cap": six.before},
        )
    ]
