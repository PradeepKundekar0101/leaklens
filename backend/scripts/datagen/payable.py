"""Vectorised implementation of the docs/decisions.md rules R01-R10 and the payable calculation.

Used by the generator for two things:
  * ground-truth leakage of rule-type scenarios (leakage = claimed - payable - member_share), and
  * self-validation: clean and anomaly-only claims must trigger no rule at all.

Everything is integer paise. Rounding is ROUND_HALF_UP at each step, as in the contract.
This is written independently of backend/app so the generator does not depend on the engine under test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scripts.datagen.common import CAT, MRP_CATS, half_up_div

RULES = ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10")


@dataclass
class ClaimArrays:
    """Per-claim inputs (length n). -1 means 'none' for optional money values."""

    admission: np.ndarray  # int64 day numbers
    discharge: np.ndarray  # int64 day numbers
    claimed: np.ndarray  # int64 paise (== line total)
    room_cap: np.ndarray
    icu_cap: np.ndarray
    tariff: np.ndarray
    sub_limit: np.ndarray
    deductible: np.ndarray
    copay_milli: np.ndarray  # copay percent in thousandths (10.000% -> 10000)
    balance: np.ndarray
    waiting_violation: np.ndarray  # bool, R06
    duplicate: np.ndarray  # bool, R08


@dataclass
class LineArrays:
    cid: np.ndarray  # int claim index, lines sorted by (cid, line order)
    cat: np.ndarray
    qty: np.ndarray  # int64
    unit: np.ndarray  # int64 paise
    amount: np.ndarray  # int64 paise
    service_date: np.ndarray  # int64 day numbers
    mrp: np.ndarray  # int64 paise, -1 if not an MRP item
    non_payable: np.ndarray  # bool


def _sum(cid: np.ndarray, values: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros(n, dtype=np.int64)
    np.add.at(out, cid, values.astype(np.int64))
    return out


def _any(cid: np.ndarray, mask: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros(n, dtype=bool)
    out[cid[mask]] = True
    return out


def evaluate(c: ClaimArrays, li: LineArrays) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Return (leakage paise per claim, {rule_code: bool per claim})."""
    n = len(c.claimed)
    cid = li.cid
    oos = (li.service_date < c.admission[cid]) | (li.service_date > c.discharge[cid])
    is_mrp_cat = np.isin(li.cat, MRP_CATS) & (li.mrp >= 0)
    is_room = li.cat == CAT["room"]
    is_icu = li.cat == CAT["icu"]
    is_proc = (li.cat == CAT["ot"]) | (li.cat == CAT["surgeon"])
    is_assoc = is_proc | (li.cat == CAT["nursing"])

    flags: dict[str, np.ndarray] = {}
    room_cap_l = c.room_cap[cid]
    icu_cap_l = c.icu_cap[cid]
    room_over = is_room & (room_cap_l >= 0) & (li.unit > room_cap_l)
    icu_over = is_icu & (icu_cap_l >= 0) & (li.unit > icu_cap_l)
    flags["R01"] = _any(cid, room_over, n)
    flags["R02"] = _any(cid, icu_over, n)
    proc_raw = _sum(cid, np.where(is_proc, li.amount, 0), n)
    flags["R03"] = (c.tariff >= 0) & (proc_raw > c.tariff)
    flags["R04"] = _any(cid, is_mrp_cat & (li.unit > li.mrp) & ~li.non_payable & ~oos, n)
    flags["R05"] = _any(cid, li.non_payable, n)
    flags["R06"] = c.waiting_violation.copy()
    flags["R08"] = c.duplicate.copy()
    flags["R09"] = _any(cid, oos & ~li.non_payable, n)

    # Step 1: remove non-payable and out-of-stay lines.
    allowed = np.where(li.non_payable | oos, 0, li.amount).astype(np.int64)
    # Step 2a: cap MRP items at MRP x qty.
    allowed = np.where(is_mrp_cat, np.minimum(allowed, li.mrp * li.qty), allowed)
    # Step 2b: proportional cut of OT + surgeon to the package rate; the last procedure line takes the remainder.
    proc_allowed = _sum(cid, np.where(is_proc, allowed, 0), n)
    t_claim = (c.tariff >= 0) & (proc_allowed > c.tariff) & (proc_allowed > 0)
    t_line = is_proc & t_claim[cid]
    if t_line.any():
        idx = np.flatnonzero(t_line)
        last = np.zeros(len(li.cid), dtype=bool)
        # last procedure line of each affected claim (lines are sorted by claim, then line order)
        rev = idx[::-1]
        _, first_in_rev = np.unique(cid[rev], return_index=True)
        last[rev[first_in_rev]] = True
        scaled = half_up_div(allowed[idx] * c.tariff[cid[idx]], proc_allowed[cid[idx]])
        allowed[idx] = scaled
        nonlast = t_line & ~last
        others = _sum(cid, np.where(nonlast, allowed, 0), n)
        lidx = np.flatnonzero(last)
        allowed[lidx] = c.tariff[cid[lidx]] - others[cid[lidx]]

    # Step 3: room / ICU caps with proportional deduction (stricter ratio) on nursing, OT, surgeon.
    num = np.ones(n, dtype=np.int64)
    den = np.ones(n, dtype=np.int64)
    for over, cap_l in ((room_over, room_cap_l), (icu_over, icu_cap_l)):
        ix = np.flatnonzero(over)
        for i in ix:  # at most one room and one ICU line per claim; loop only over capped lines
            k = cid[i]
            cn, cd = int(cap_l[i]), int(li.unit[i])
            if cn * den[k] < num[k] * cd:
                num[k], den[k] = cn, cd
    ratio_lt1 = num < den
    allowed = np.where(room_over, np.minimum(allowed, room_cap_l * li.qty), allowed)
    allowed = np.where(icu_over, np.minimum(allowed, icu_cap_l * li.qty), allowed)
    assoc_cut = is_assoc & ratio_lt1[cid] & (allowed != 0)
    if assoc_cut.any():
        ix = np.flatnonzero(assoc_cut)
        allowed[ix] = half_up_div(allowed[ix] * num[cid[ix]], den[cid[ix]])
    after3 = _sum(cid, allowed, n)

    # Step 4: sub-limit.
    has_sub = c.sub_limit >= 0
    flags["R07"] = has_sub & (after3 > c.sub_limit)
    after4 = np.where(has_sub, np.minimum(after3, c.sub_limit), after3)
    # Step 5: deductible then co-pay (member share, not leakage).
    after_ded = np.maximum(0, after4 - c.deductible)
    copay = half_up_div(after_ded * c.copay_milli, 100_000)
    after5 = after_ded - copay
    member_share = after4 - after5
    # Step 6: remaining sum insured.
    bal = np.maximum(0, c.balance)
    flags["R10"] = after5 > bal
    payable = np.minimum(after5, bal)

    leakage = c.claimed - payable - member_share
    full = flags["R06"] | flags["R08"]
    leakage = np.where(full, c.claimed, leakage)
    return leakage, flags


def flag_sets(flags: dict[str, np.ndarray]) -> list[frozenset[str]]:
    n = len(next(iter(flags.values())))
    mat = np.column_stack([flags[r] for r in RULES])
    out: list[frozenset[str]] = []
    for i in range(n):
        row = mat[i]
        out.append(frozenset(RULES[j] for j in np.flatnonzero(row)) if row.any() else frozenset())
    return out
