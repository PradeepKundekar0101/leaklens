"""Hand-computed expectations for every rule and the payable calculator.

Sum insured 5,00,000 with a 1% room cap gives 5,000 per day; ICU cap 2% gives 10,000 per day.
"""

from datetime import date, timedelta
from decimal import Decimal as D

from app.services.rules.context import DocumentMatch
from app.services.rules.engine import REGISTRY, run_rules
from app.services.rules.payable import compute_payable
from tests.rule_fixtures import ADM, DIS, ctx, line, params, prior


def codes(c) -> dict[str, list[D]]:
    out: dict[str, list[D]] = {}
    for f in run_rules(c).findings:
        out.setdefault(f.rule_code, []).append(f.amount_impact)
    return out


def surgical(room_unit: str = "7000") -> list:
    return [
        line(1, "room", str(D(room_unit) * 3), qty="3", unit=room_unit),
        line(2, "nursing", "6000"),
        line(3, "ot", "20000"),
        line(4, "surgeon", "30000"),
        line(5, "pharmacy", "10000", code="DRUGX"),
    ]


def test_registry_has_all_rules():
    run_rules(ctx([]))
    assert sorted(REGISTRY) == [f"R{n:02d}" for n in range(1, 12)]


# R01
def test_r01_excess_rent_plus_proportional_deduction():
    found = run_rules(ctx(surgical())).findings
    r01 = [f for f in found if f.rule_code == "R01"]
    assert len(r01) == 1
    # excess 2,000 x 3 = 6,000; associated x 2/7: 1,714.29 + 5,714.29 + 8,571.43
    assert r01[0].amount_impact == D("22000.01")
    assert r01[0].evidence["excess_rent"] == D("6000.00")
    assert r01[0].clause_ref == "4.2"
    assert {f.rule_code for f in found} == {"R01"}


def test_r01_rent_exactly_at_cap_is_clean():
    assert codes(ctx(surgical("5000"))) == {}


def test_r01_no_cap():
    assert codes(ctx(surgical(), params=params(room_rent_cap_pct=None))) == {}


def test_r01_zero_items():
    result = run_rules(ctx([]))
    assert result.findings == []
    assert result.payable.payable == D("0")


# R02
def test_r02_icu_above_cap():
    lines = [line(1, "icu", "24000", qty="2", unit="12000"), line(2, "nursing", "6000")]
    assert codes(ctx(lines)) == {"R02": [D("5000.00")]}  # 4,000 excess + 6,000 x 1/6


def test_r02_does_not_double_deduct_when_room_ratio_is_stricter():
    lines = [
        line(1, "room", "21000", qty="3", unit="7000"),  # ratio 5/7
        line(2, "icu", "11000", qty="1", unit="11000"),  # ratio 10/11, less strict
        line(3, "nursing", "7000"),
    ]
    found = codes(ctx(lines))
    assert found["R02"] == [D("1000.00")]  # excess only
    assert found["R01"] == [D("8000.00")]  # 6,000 + 7,000 x 2/7


# R03
def test_r03_above_tariff():
    lines = [line(3, "ot", "20000"), line(4, "surgeon", "30000")]
    assert codes(ctx(lines, tariff=D("40000"))) == {"R03": [D("10000.00")]}


def test_r03_at_tariff_and_without_tariff():
    lines = [line(3, "ot", "20000"), line(4, "surgeon", "30000")]
    assert codes(ctx(lines, tariff=D("50000"))) == {}
    assert codes(ctx(lines, tariff=None)) == {}


# R04 / R05
def test_r04_above_mrp():
    lines = [line(1, "pharmacy", "1200", code="DRUG1", qty="10", unit="120")]
    assert codes(ctx(lines)) == {"R04": [D("200.00")]}


def test_r04_at_mrp_is_clean():
    lines = [line(1, "pharmacy", "1000", code="DRUG1", qty="10", unit="100")]
    assert codes(ctx(lines)) == {}


def test_r05_non_payable_full_amount_not_also_r04():
    lines = [line(1, "consumables", "300", code="GLOVES", qty="3", unit="100")]  # above MRP too
    assert codes(ctx(lines)) == {"R05": [D("300")]}


# R06
def test_r06_initial_waiting_period():
    c = ctx(surgical("5000"), policy_start=ADM - timedelta(days=10))
    result = run_rules(c)
    assert [f.rule_code for f in result.findings] == ["R06"]
    assert result.findings[0].severity == "high"
    assert result.findings[0].clause_ref == "5.1"
    assert result.payable.payable == D("0")
    assert result.payable.leakage == c.claimed_amount


def test_r06_day_30_is_outside_initial_period():
    assert codes(ctx(surgical("5000"), policy_start=ADM - timedelta(days=30))) == {}


def test_r06_listed_condition_and_pre_existing():
    listed = ctx(surgical("5000"), procedure_code="PR_CATARACT", policy_start=date(2025, 6, 1))
    assert "R06" in codes(listed)
    ped = ctx(surgical("5000"), declared_conditions=frozenset({"K35"}), policy_start=date(2024, 6, 1))
    assert "R06" in codes(ped)
    old = ctx(surgical("5000"), declared_conditions=frozenset({"K35"}), policy_start=date(2023, 6, 1))
    assert "R06" not in codes(old)


# R07
def test_r07_sub_limit():
    c = ctx(surgical("5000"), procedure_code="PR_CATARACT", params=params(sub_limits={"PR_CATARACT": D("40000")}))
    assert codes(c)["R07"] == [D(c.claimed_amount - D("40000")).quantize(D("0.01"))]


# R08
def test_r08_exact_duplicate_flags_only_the_later_claim():
    lines = surgical("5000")
    total = sum((li.amount for li in lines), D("0"))
    later = ctx(lines, prior_claims=[prior("C0", str(total))])
    assert codes(later) == {"R08": [total]}
    earlier = ctx(lines, prior_claims=[prior("C9", str(total), created=later.created_at + timedelta(hours=1))])
    assert codes(earlier) == {}
    different_amount = ctx(lines, prior_claims=[prior("C0", "1.00")])
    assert codes(different_amount) == {}


# R09
def test_r09_service_date_after_discharge():
    lines = [line(1, "investigations", "2500", code="LAB1", day=DIS + timedelta(days=2)), line(2, "nursing", "100")]
    assert codes(ctx(lines)) == {"R09": [D("2500")]}


def test_r09_on_admission_and_discharge_day_is_clean():
    lines = [line(1, "investigations", "2500", code="LAB1", day=ADM), line(2, "nursing", "100", day=DIS)]
    assert codes(ctx(lines)) == {}


# R10
def test_r10_exceeds_remaining_sum_insured():
    c = ctx(surgical("5000"), balance=D("30000"))
    assert codes(c) == {"R10": [c.claimed_amount - D("30000")]}


# R11
def test_r11_reused_document_has_no_rupee_impact():
    c = ctx(surgical("5000"), document_matches=[DocumentMatch(7, "C42", 9, "phash", 3)])
    assert codes(c) == {"R11": [D("0")]}


# Payable calculator - full order on one worked claim
def worked_claim(balance: str):
    lines = [
        line(1, "room", "21000", qty="3", unit="7000"),
        line(2, "nursing", "6000"),
        line(3, "ot", "20000"),
        line(4, "surgeon", "30000"),
        line(5, "pharmacy", "1200", code="DRUG1", qty="10", unit="120"),
        line(6, "consumables", "300", code="GLOVES", qty="3", unit="100"),
        line(7, "pharmacy", "100", code="DRUG1", day=DIS + timedelta(days=1)),
    ]
    return ctx(
        lines,
        tariff=D("45000"),
        balance=D(balance),
        params=params(copay_pct=D("10"), deductible=D("5000")),
    )


def test_payable_full_order():
    result = compute_payable(worked_claim("60000"))
    after = {s.step: s.after for s in result.steps}
    assert result.claimed == D("78600")
    assert after[1] == D("78200")  # gloves 300 and the out-of-stay 100 removed
    assert after[2] == D("73000")  # MRP -200, tariff 50,000 -> 45,000
    assert after[3] == D("52428.56")  # room 15,000; nursing 4,285.71; OT 12,857.14; surgeon 19,285.71; drug 1,000
    assert after[4] == D("52428.56")  # no sub-limit
    assert after[5] == D("42685.70")  # deductible 5,000 then 10% co-pay 4,742.86
    assert result.member_share == D("9742.86")
    assert result.payable == D("42685.70")
    assert result.leakage == D("26171.44")
    assert result.claimed == result.payable + result.member_share + result.leakage


def test_payable_capped_at_remaining_sum_insured():
    result = compute_payable(worked_claim("40000"))
    assert result.payable == D("40000.00")
    assert result.leakage == D("28857.14")


def test_clean_claim_has_zero_leakage_with_copay():
    c = ctx(surgical("5000"), params=params(copay_pct=D("10")))
    result = run_rules(c)
    assert result.findings == []
    assert result.payable.leakage == D("0")
    assert result.payable.member_share == D("8100.00")  # 10% of 81,000
