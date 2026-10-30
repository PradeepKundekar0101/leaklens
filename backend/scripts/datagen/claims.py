"""Claims, line items and planted leakage (plan pages 12-13, rules per docs/decisions.md).

Pipeline:
  1. claim skeletons: procedure by frequency, patient age from the procedure profile, admission date, LOS;
  2. early-claim policies, then rejection-sampled policy assignment honouring waiting periods and sum insured;
  3. provider, claim type, room category / rent (within cap), expected cost, target claimed amount;
  4. normal line items for every claim (all clean by construction);
  5. scenario transforms on the line items, clones for duplicates and reused documents;
  6. validation with the vectorised rule engine (payable.py) and ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from scripts.datagen.common import (
    CAT,
    CATEGORIES,
    TEMPLATES,
    Product,
    Reference,
    add_months,
    fmt_paise,
    half_up_div,
)
from scripts.datagen.entities import GENERAL_RENT, ICU_RENT
from scripts.datagen.payable import ClaimArrays, LineArrays, evaluate, flag_sets

SCENARIO_RATES: dict[str, float] = {
    "room_rent_above_cap": 0.05,
    "non_payable_billed": 0.06,
    "item_above_mrp": 0.04,
    "above_tariff": 0.03,
    "exact_duplicate": 0.005,
    "service_date_outside_stay": 0.005,
    "inflated_pharmacy": 0.01,
    "stretched_stay": 0.01,
    "preauth_escalation": 0.01,
    "early_claim": 0.005,
    "combination": 0.005,
}
EXPECTED_RULES: dict[str, frozenset[str]] = {
    "room_rent_above_cap": frozenset({"R01"}),
    "non_payable_billed": frozenset({"R05"}),
    "item_above_mrp": frozenset({"R04"}),
    "above_tariff": frozenset({"R03"}),
    "exact_duplicate": frozenset({"R08"}),
    "service_date_outside_stay": frozenset({"R09"}),
}
RULE_SCENARIOS = frozenset(EXPECTED_RULES)
ANOMALY_SCENARIOS = frozenset(
    {"inflated_pharmacy", "stretched_stay", "preauth_escalation", "early_claim", "combination", "overbilling_provider"}
)
OB_TARGET_SHARE = 0.04
REUSED_PAIRS = 10


def _day(iso: str) -> int:
    """Dates are int64 day numbers (days since 1970-01-01) internally; converted to ISO strings on output."""
    return int(np.datetime64(iso, "D").astype(np.int64))


def _iso(days: np.ndarray) -> np.ndarray:
    return np.asarray(days, dtype=np.int64).astype("datetime64[D]").astype(str)


TRAIN_LO, TRAIN_HI = _day("2026-01-01"), _day("2026-08-31")
TEST_LO, TEST_HI = _day("2026-09-01"), _day("2026-10-31")
TEST_LAST_DISCHARGE = _day("2026-10-28")
NEW_POLICY_FROM = _day("2026-01-01")
NOW_CAP = np.datetime64("2026-10-30T18:00:00")
TENURE_MARGIN = 21  # days of slack when checking waiting periods, so later date shifts never break them
SI_ELIGIBILITY = 0.45
POLICY_BUDGET = 0.6  # sum of base rates of all claims placed on a policy stays within 60% of its sum insured
MAX_CLAIMS_PER_POLICY = 4  # a member is eligible for a procedure if base_rate <= 45% of sum insured

ROOM_PROBS = {
    "SILVER": {"general": 0.65, "semi_private": 0.35},
    "GOLD": {"general": 0.15, "semi_private": 0.45, "private": 0.40},
    "PLATINUM": {"semi_private": 0.15, "private": 0.55, "deluxe": 0.30},
}
ROOM_LABEL = {
    "general": "General ward",
    "semi_private": "Semi-private room",
    "private": "Private room",
    "deluxe": "Deluxe room",
}


@dataclass
class World:
    ref: Reference
    products: list[Product]
    providers: pd.DataFrame
    tariffs: pd.DataFrame
    members: pd.DataFrame
    policies: pd.DataFrame


@dataclass
class ClaimsResult:
    claims: pd.DataFrame  # output-ready claims
    lines: pd.DataFrame  # output-ready line items
    ground_truth: pd.DataFrame
    balance_paise: np.ndarray  # per policy
    ob_providers: list[tuple[str, float]]
    report: dict = field(default_factory=dict)
    reused_pairs: list[tuple[str, str]] = field(default_factory=list)  # (original claim id, clone claim id)


def _d64(dates) -> np.ndarray:
    return pd.to_datetime(pd.Series(list(dates))).to_numpy().astype("datetime64[D]").astype(np.int64)


def _rint(x) -> np.ndarray:
    return np.rint(x).astype(np.int64)


def _floor_to(paise: np.ndarray, rupees: int) -> np.ndarray:
    step = rupees * 100
    return (np.asarray(paise, dtype=np.int64) // step) * step


def _round_to(paise, rupees: int) -> np.ndarray:
    step = rupees * 100
    return _rint(np.asarray(paise, dtype=float) / step) * step


class Generator:
    def __init__(self, rng: np.random.Generator, world: World, n_train: int, n_test: int) -> None:
        self.rng = rng
        self.w = world
        self.n_train, self.n_test = n_train, n_test
        self.procs = world.ref.procedures
        self.items = world.ref.items.reset_index(drop=True)
        self.item_index = {c: i for i, c in enumerate(self.items.item_code)}
        self.report: dict = {}

    # ------------------------------------------------------------------ setup
    def _policy_arrays(self) -> None:
        w, procs = self.w, self.procs
        pol = w.policies
        self.pol_start = _d64(pol.start_date)
        prod_idx = pol.product_idx.to_numpy()
        self.pol_prod = prod_idx
        self.pol_si = pol.si_paise.to_numpy(np.int64)
        starts = list(pol.start_date)
        listed_m = [w.products[k].waiting_periods["listed_conditions_months"] for k in prod_idx]
        ped_m = [w.products[k].waiting_periods["pre_existing_months"] for k in prod_idx]
        self.pol_initial = np.array([w.products[k].waiting_periods["initial_days"] for k in prod_idx])
        self.pol_listed_end = _d64([add_months(s, m) for s, m in zip(starts, listed_m, strict=True)])
        self.pol_ped_end = _d64([add_months(s, m) for s, m in zip(starts, ped_m, strict=True)])
        mem = w.members
        self.mem_age = mem.age.to_numpy()
        self.mem_gender = np.where(mem.gender.to_numpy() == "F", 0, 1)
        self.mem_ncond = mem.n_conditions.to_numpy()
        # has_cond[policy, procedure]: the member declared the procedure's diagnosis as pre-existing
        icd = procs.icd10.to_numpy()
        self.has_cond = np.zeros((len(mem), len(procs)), dtype=bool)
        for i, dc in enumerate(mem.declared_conditions):
            if dc != "[]":
                codes = {c.strip().strip('"') for c in dc.strip("[]").split(",")}
                self.has_cond[i] = np.isin(icd, list(codes))
        self.proc_listed = (procs.waiting_category == "listed_condition").to_numpy()
        self.proc_gender = np.select([procs.gender == "F", procs.gender == "M"], [0, 1], -1)
        self.proc_base = procs.base_rate_paise.to_numpy(np.int64)
        self.proc_template = procs.template.to_numpy()
        # sub-limit matrix [product, procedure] in paise, -1 = none
        codes = list(procs.code)
        self.sub_matrix = np.full((len(w.products), len(procs)), -1, dtype=np.int64)
        for k, p in enumerate(w.products):
            for code, v in p.sub_limits.items():
                self.sub_matrix[k, codes.index(code)] = int(round(float(v) * 100))

    def _eligible(self, ci: np.ndarray, pj: np.ndarray, adm: np.ndarray) -> np.ndarray:
        a = adm - TENURE_MARGIN
        p = self.proc[ci]
        ok = a >= self.pol_start[pj] + self.pol_initial[pj]
        ok &= ~self.proc_listed[p] | (a >= self.pol_listed_end[pj])
        ok &= ~self.has_cond[pj, p] | (a >= self.pol_ped_end[pj])
        ok &= self.proc_base[p] <= SI_ELIGIBILITY * self.pol_si[pj]
        g = self.proc_gender[p]
        ok &= (g < 0) | (self.mem_gender[pj] == g)
        return ok

    # ------------------------------------------------------------------ 1. skeletons
    def skeletons(self) -> None:
        rng, procs = self.rng, self.procs
        n = self.n_train + self.n_test
        self.n = n
        self.is_test = np.arange(n) >= self.n_train
        freq = procs.frequency.to_numpy(float)
        self.proc = rng.choice(len(procs), size=n, p=freq / freq.sum())
        prof = procs.age
        mean = np.array([a["mean"] for a in prof])[self.proc]
        sd = np.array([a["sd"] for a in prof])[self.proc]
        amin = np.array([a["min"] for a in prof])[self.proc]
        amax = np.array([a["max"] for a in prof])[self.proc]
        self.age_s = np.clip(np.rint(rng.normal(mean, sd)), amin, amax).astype(int)
        lo = np.where(self.is_test, TEST_LO, TRAIN_LO)
        hi = np.where(self.is_test, TEST_LAST_DISCHARGE, TRAIN_HI)
        span = (hi - lo).astype(int)
        self.adm = lo + (rng.random(n) * (span + 1)).astype(int)
        typ = procs.typical_los.to_numpy()[self.proc]
        lam = typ * (1 + 0.012 * np.maximum(0, self.age_s - 50))
        los = np.maximum(1, rng.poisson(lam))
        los = np.where(typ <= 1, 1 + (rng.random(n) < 0.08), los)
        icu_typ = procs.icu_days_typical.to_numpy()[self.proc]
        icu = np.where(icu_typ > 0, rng.poisson(icu_typ * 0.9), 0)
        icu = np.where(self.proc_template[self.proc] == "cardiac", np.maximum(icu, 1), icu)
        icu = np.where(icu_typ > 0, np.minimum(icu, 6), 0)
        self.icu_days = icu.astype(int)
        self.los = np.maximum(los, self.icu_days + 1).astype(int)
        self.scenario = np.full(n, "", dtype=object)
        self.active = np.ones(n, dtype=bool)
        self.parent = np.full(n, -1)

    # ------------------------------------------------------------------ 2. policies
    def assign_policies(self) -> None:
        rng = self.rng
        n = self.n
        npol = len(self.pol_start)
        self.pol = np.full(n, -1)
        is_new = self.pol_start >= NEW_POLICY_FROM
        new_idx = np.flatnonzero(is_new)
        used = np.zeros(npol, dtype=bool)
        load = np.zeros(npol, dtype=np.int64)  # sum of base rates already placed on the policy
        nclaims = np.zeros(npol, dtype=np.int64)

        # early claims: admission 31-45 days after a new policy's start (just past the 30-day wait)
        early_ok = ~self.proc_listed[self.proc]
        for split_test in (False, True):
            n_split = self.n_test if split_test else self.n_train
            k = int(round(SCENARIO_RATES["early_claim"] * n_split))
            pool = np.flatnonzero(early_ok & (self.is_test == split_test))
            chosen = rng.choice(pool, size=min(k, len(pool)), replace=False)
            for ci in chosen:
                d = int(rng.integers(31, 46))
                lo = TEST_LO if split_test else TRAIN_LO
                hi = (TEST_LAST_DISCHARGE - int(self.los[ci])) if split_test else TRAIN_HI
                st = self.pol_start[new_idx]
                p = self.proc[ci]
                cand = (
                    (st + d >= lo)
                    & (st + d <= hi)
                    & ~used[new_idx]
                    & ~self.has_cond[new_idx, p]
                    & (self.proc_base[p] <= SI_ELIGIBILITY * self.pol_si[new_idx])
                    & (self.sub_matrix[self.pol_prod[new_idx], p] < 0)
                    & ((self.proc_gender[p] < 0) | (self.mem_gender[new_idx] == self.proc_gender[p]))
                )
                cidx = new_idx[cand]
                if len(cidx) == 0:
                    continue
                pj = int(cidx[rng.integers(len(cidx))])
                used[pj] = True
                load[pj] += self.proc_base[p]
                nclaims[pj] += 1
                self.pol[ci] = pj
                self.adm[ci] = self.pol_start[pj] + d
                self.scenario[ci] = "early_claim"

        # everyone else: rejection sampling within (5-year age bucket, gender)
        bucket = np.clip(self.mem_age // 5, 0, 18)
        key_pol = bucket * 2 + self.mem_gender
        order = np.argsort(key_pol, kind="stable")
        counts = np.bincount(key_pol, minlength=38)
        starts = np.cumsum(counts) - counts
        todo = np.flatnonzero(self.pol < 0)
        for r in range(90):
            if len(todo) == 0:
                break
            age = self.age_s[todo]
            if r >= 20:
                age = age + rng.integers(-7, 8, len(todo))
            g_req = self.proc_gender[self.proc[todo]]
            g = np.where(g_req < 0, rng.integers(0, 2, len(todo)), g_req)
            k = np.clip(age // 5, 0, 18) * 2 + g
            cnt = counts[k]
            pick = order[np.minimum(starts[k] + (rng.random(len(todo)) * cnt).astype(int), npol - 1)]
            if r >= 50:
                pick = rng.integers(0, npol, len(todo))
                cnt = np.ones(len(todo), dtype=int)
            base = self.proc_base[self.proc[todo]]
            ok = (cnt > 0) & self._eligible(todo, pick, self.adm[todo])
            # spread claims: cumulative base cost within POLICY_BUDGET of SI and at most MAX_CLAIMS per policy
            ok &= (load[pick] + base <= POLICY_BUDGET * self.pol_si[pick]) & (nclaims[pick] < MAX_CLAIMS_PER_POLICY)
            # one acceptance per policy per round, so the budget check stays exact
            cand = np.flatnonzero(ok)
            _, first = np.unique(pick[cand], return_index=True)
            acc = np.zeros(len(todo), dtype=bool)
            acc[cand[first]] = True
            self.pol[todo[acc]] = pick[acc]
            np.add.at(load, pick[acc], base[acc])
            np.add.at(nclaims, pick[acc], 1)
            todo = todo[~acc]
        self.report["unassigned_claims"] = len(todo)
        self.active[todo] = False
        self.pol[todo] = 0

        # LOS nudged up by declared conditions (not for early claims, whose dates are pinned)
        nudge = rng.binomial(self.mem_ncond[self.pol], 0.3)
        early = self.scenario == "early_claim"
        self.los = np.where(early, self.los, self.los + nudge)
        over = (self.adm + self.los - TEST_LAST_DISCHARGE).astype(int)
        shift = np.where(self.is_test & ~early, np.maximum(0, over), 0)
        self.adm = self.adm - shift
        self.age = self.mem_age[self.pol]

    # ------------------------------------------------------------------ 3. provider and money context
    def assign_providers(self) -> None:
        rng, prov = self.rng, self.w.providers
        n = self.n
        mem_city = self.w.members.city.to_numpy()[self.pol]
        beds = prov.beds.to_numpy(float)
        self.prov = rng.choice(len(prov), size=n, p=beds / beds.sum())
        local = rng.random(n) < 0.9
        for city, grp in prov.groupby("city"):
            m = local & (mem_city == city)
            idx = grp.index.to_numpy()
            b = beds[idx]
            self.prov[m] = rng.choice(idx, size=int(m.sum()), p=b / b.sum())
        # the two over-billing providers: non-network pair whose combined share is closest to 4%
        share = np.bincount(self.prov[self.active], minlength=len(prov)) / self.active.sum()
        nn = np.flatnonzero(~prov.network.to_numpy())
        best, pair = 9.0, (int(nn[0]), int(nn[1]))
        for a in range(len(nn)):
            for b in range(a + 1, len(nn)):
                d = abs(share[nn[a]] + share[nn[b]] - OB_TARGET_SHARE)
                if d < best:
                    best, pair = d, (int(nn[a]), int(nn[b]))
        self.ob_idx = pair
        self.ob_factor = {pair[0]: float(rng.uniform(1.38, 1.46)), pair[1]: float(rng.uniform(1.38, 1.46))}
        non_ob = np.setdiff1d(np.arange(len(prov)), pair)
        bad = (self.scenario == "early_claim") & np.isin(self.prov, pair)
        for ci in np.flatnonzero(bad):
            same = non_ob[prov.city.to_numpy()[non_ob] == mem_city[ci]]
            self.prov[ci] = int(rng.choice(same if len(same) else non_ob))
        self.ob = np.isin(self.prov, pair)
        self.network = prov.network.to_numpy()[self.prov]
        self.cashless = self.network & (rng.random(n) < 0.8)

    def money_context(self) -> None:
        rng, w = self.rng, self.w
        n = self.n
        prov = w.providers
        prods = w.products
        pk = self.pol_prod[self.pol]
        self.pk = pk
        self.si = self.pol_si[self.pol]
        rr = np.array([p.pct_milli(p.room_rent_cap_pct) for p in prods])[pk]
        ic = np.array([p.pct_milli(p.icu_cap_pct) for p in prods])[pk]
        self.room_cap = np.where(rr >= 0, half_up_div(self.si * np.maximum(rr, 0), 100_000), -1)
        self.icu_cap = np.where(ic >= 0, half_up_div(self.si * np.maximum(ic, 0), 100_000), -1)
        self.copay_milli = np.array([p.pct_milli(p.copay_pct) for p in prods])[pk]
        self.deductible = np.array([int(round(float(p.deductible) * 100)) for p in prods])[pk]
        self.sub_limit = self.sub_matrix[pk, self.proc]
        tmap = {
            (pid, code): pz
            for pid, code, pz in zip(
                w.tariffs.provider_id, w.tariffs.procedure_code, w.tariffs.package_paise, strict=True
            )
        }
        pids = prov.id.to_numpy()[self.prov]
        codes = self.procs.code.to_numpy()[self.proc]
        self.tariff = np.array([tmap.get((a, b), -1) for a, b in zip(pids, codes, strict=True)], dtype=np.int64)

        city_tier = prov.city_tier.to_numpy()[self.prov]
        hosp_tier = prov.hospital_tier.to_numpy()[self.prov]
        nabh = prov.nabh.to_numpy()[self.prov]
        m = w.ref.multipliers
        city_f = np.array([m[("city_tier", str(t))] for t in (1, 2, 3)])[city_tier - 1]
        hosp_f = np.array([m[("hospital_tier", str(t))] for t in (1, 2, 3)])[hosp_tier - 1]
        nabh_f = np.where(nabh, m[("nabh", "true")], m[("nabh", "false")])

        cats = np.empty(n, dtype=object)
        for k, p in enumerate(prods):
            sel = pk == k
            names = list(ROOM_PROBS[p.id])
            probs = np.array(list(ROOM_PROBS[p.id].values()))
            cats[sel] = np.array(names, dtype=object)[rng.choice(len(names), size=int(sel.sum()), p=probs)]
        self.room_cat = cats
        room_f = np.array([m[("room_category", c)] for c in cats])
        gen = np.array([GENERAL_RENT[t] for t in (1, 2, 3)])[hosp_tier - 1]
        icu_base = np.array([ICU_RENT[t] for t in (1, 2, 3)])[hosp_tier - 1]
        rent = _round_to(gen * room_f * city_f * rng.uniform(0.9, 1.12, n) * 100, 50)
        over = (self.room_cap >= 0) & (rent > self.room_cap)
        rent = np.where(over, _floor_to(self.room_cap * rng.uniform(0.8, 1.0, n), 50), rent)
        self.rent = np.maximum(rent, 50_000)
        icu_rent = _round_to(icu_base * city_f * rng.uniform(0.9, 1.1, n) * 100, 100)
        over = (self.icu_cap >= 0) & (icu_rent > self.icu_cap)
        self.icu_rent = np.where(over, _floor_to(self.icu_cap * rng.uniform(0.8, 1.0, n), 100), icu_rent)

        typ = self.procs.typical_los.to_numpy()[self.proc]
        age_adj = 1 + 0.004 * np.maximum(0, self.age - 45)
        los_adj = np.clip(1 + 0.4 * (self.los - typ) / np.maximum(typ, 1), 0.8, 2.0)
        expected = self.proc_base[self.proc] / 100 * city_f * hosp_f * nabh_f * age_adj * los_adj
        target = expected * rng.lognormal(0.0, 0.18, n)
        # keep claims under procedure sub-limits (over-billing claims get room for their inflation)
        ob_f = np.ones(n)
        for pi, f in self.ob_factor.items():
            ob_f[self.prov == pi] = f * 1.03
        has_sub = self.sub_limit >= 0
        cap_t = self.sub_limit / 100 * rng.uniform(0.80, 0.90, n) / ob_f
        self.target = np.where(has_sub, np.minimum(target, cap_t), target)
        self.preauth = np.where(self.cashless, _round_to(self.target * rng.normal(1.0, 0.05, n) * 100, 100), -1)

    # ------------------------------------------------------------------ scenario selection
    def choose_scenarios(self) -> None:
        rng = self.rng
        base = self.active & ~self.ob & (self.scenario == "") & (self.sub_limit < 0)
        share = self.procs.typical_pharmacy_share.to_numpy()[self.proc]
        extra = {
            "room_rent_above_cap": self.room_cap >= 0,
            "above_tariff": self.tariff >= 0,
            "inflated_pharmacy": share <= 0.15,
            "preauth_escalation": self.cashless,
        }
        order = [
            "room_rent_above_cap",
            "above_tariff",
            "non_payable_billed",
            "item_above_mrp",
            "service_date_outside_stay",
            "inflated_pharmacy",
            "stretched_stay",
            "preauth_escalation",
            "combination",
        ]
        for split_test in (False, True):
            n_split = self.n_test if split_test else self.n_train
            for name in order:
                pool = base & (self.scenario == "") & (self.is_test == split_test) & extra.get(name, True)
                idx = np.flatnonzero(pool)
                k = min(int(round(SCENARIO_RATES[name] * n_split)), len(idx))
                self.scenario[rng.choice(idx, size=k, replace=False)] = name
        self.scenario[self.ob & self.active] = "overbilling_provider"

    # ------------------------------------------------------------------ 4. normal line items
    def _pools(self) -> dict[tuple[int, str], np.ndarray]:
        items = self.items
        tags = [set(t.split("|")) for t in items.tags]
        pools = {}
        for p, (code, tpl) in enumerate(zip(self.procs.code, self.procs.template, strict=True)):
            for cat in ("pharmacy", "consumables", "investigations"):
                sel = [
                    i
                    for i in range(len(items))
                    if items.category[i] == cat and not items.non_payable[i] and (tpl in tags[i] or code in tags[i])
                ]
                pools[(p, cat)] = np.array(sel, dtype=int)
                if len(sel) < 2:
                    raise ValueError(f"item pool too small for {code}/{cat}")
        return pools

    def _sample_items(self, cids: np.ndarray, k: np.ndarray, pool_of) -> tuple[np.ndarray, np.ndarray]:
        """Pick k distinct items per claim from that claim's pool. Returns (claim index per line, item index)."""
        rng = self.rng
        out_c, out_i = [], []
        groups = pool_of(cids)
        for key in sorted(groups):
            sel, pool = groups[key]
            if len(sel) == 0:
                continue
            m = len(pool)
            kk = np.minimum(k[cids[sel]], m)
            order = np.argsort(rng.random((len(sel), m)), axis=1)
            mask = np.arange(m)[None, :] < kk[:, None]
            out_c.append(np.repeat(cids[sel], kk))
            out_i.append(pool[order[mask]])
        if not out_c:
            return np.array([], dtype=int), np.array([], dtype=int)
        return np.concatenate(out_c), np.concatenate(out_i)

    def build_lines(self) -> None:
        rng = self.rng
        n = self.n
        ids = np.flatnonzero(self.active)
        tpl = self.proc_template[self.proc]
        w = np.array([TEMPLATES[t] for t in tpl])
        ward = self.los - self.icu_days
        room_amt = self.rent * ward
        icu_amt = self.icu_rent * self.icu_days
        imp_code = self.procs.implant_item.to_numpy()[self.proc]
        has_imp = imp_code != ""
        imp_item = np.array([self.item_index[c] if c else -1 for c in imp_code])
        mrp_all = self.items.mrp_paise.to_numpy(np.int64)
        imp_unit = np.where(has_imp, _rint(mrp_all[imp_item] * rng.uniform(0.55, 0.65, n)), 0)
        m_share = self.procs.typical_pharmacy_share.to_numpy()[self.proc]
        share = rng.beta(m_share * 80, (1 - m_share) * 80)
        t_p = self.target * 100
        pharm_t = share * t_p
        rest = np.maximum(t_p - room_amt - icu_amt - pharm_t - imp_unit, 0.3 * t_p)
        g = np.where(w > 0, rng.gamma(np.where(w > 0, w * 40, 1.0)), 0.0)
        g = g / g.sum(axis=1, keepdims=True)
        parts = rest[:, None] * g
        nursing_unit = np.maximum(200, _rint(parts[:, 0] / 100 / self.los)) * 100
        ot = np.where(w[:, 1] > 0, np.maximum(100, _rint(parts[:, 1] / 1000)) * 1000, 0)
        surgeon = np.maximum(100, _rint(parts[:, 2] / 1000)) * 1000
        # clean procedure charges stay within the contracted package rate
        proc_sum = ot + surgeon
        net = self.active & (self.tariff >= 0)
        self.report["proc_to_tariff_p50_p90"] = (
            np.percentile(proc_sum[net] / self.tariff[net], [50, 90]).round(3).tolist()
        )
        clip = (self.tariff >= 0) & (proc_sum > 0.98 * self.tariff)
        f = np.where(clip, self.tariff * rng.uniform(0.85, 0.97, n) / np.maximum(proc_sum, 1), 1.0)
        ot = np.where(clip, _floor_to(ot * f, 10), ot)
        surgeon = np.where(clip, _floor_to(surgeon * f, 10), surgeon)
        self.report["tariff_clipped_share"] = float(clip[self.active & (self.tariff >= 0)].mean())

        surg_like = np.isin(tpl, ["surgical", "cardiac"])
        proc_day = self.adm + np.where(surg_like & (self.los >= 3) & (rng.random(n) < 0.4), 1, 0)
        cards = {
            "cardiac": ("Cath lab / OT charges", "Cardiologist and anaesthetist fees"),
            "medical": ("", "Consultant physician fees"),
            "maternity": ("Labour room / OT charges", "Obstetrician and anaesthetist fees"),
        }
        ot_desc = np.array([cards.get(t, ("Operation theatre charges",))[0] for t in tpl], dtype=object)
        sg_desc = np.array([cards.get(t, ("", "Surgeon and anaesthetist fees"))[1] for t in tpl], dtype=object)

        frames = []

        def svc(sel, cat, code, desc, qty, unit, sdate):
            frames.append(
                pd.DataFrame(
                    {
                        "cid": ids[sel[ids]],
                        "cat": CAT[cat],
                        "item_code": code,
                        "description": desc[ids][sel[ids]] if isinstance(desc, np.ndarray) else desc,
                        "qty": qty[ids][sel[ids]],
                        "unit": unit[ids][sel[ids]],
                        "sdate": sdate[ids][sel[ids]],
                        "mrp": -1,
                        "np": False,
                        "item": -1,
                    }
                )
            )

        allc = np.ones(n, dtype=bool)
        room_desc = np.array([f"Room rent - {ROOM_LABEL[c]}" for c in self.room_cat], dtype=object)
        svc(allc, "room", "ROOM", room_desc, ward, self.rent, self.adm)
        svc(self.icu_days > 0, "icu", "ICU", "ICU charges", self.icu_days, self.icu_rent, self.adm)
        svc(allc, "nursing", "NURSING", "Nursing charges", self.los, nursing_unit, self.adm)
        svc(ot > 0, "ot", "OT", ot_desc, np.ones(n, dtype=np.int64), ot, proc_day)
        svc(allc, "surgeon", "SURGEON", sg_desc, np.ones(n, dtype=np.int64), surgeon, proc_day)

        # implant (one unit, billed under its MRP)
        sel = ids[has_imp[ids]]
        frames.append(
            self._item_frame(sel, imp_item[sel], np.ones(len(sel), dtype=np.int64), imp_unit[sel], proc_day[sel])
        )

        pools = self._pools()
        targets = {"pharmacy": pharm_t, "consumables": parts[:, 3], "investigations": parts[:, 4]}
        spec = {"pharmacy": (5, 14, 2500.0), "consumables": (3, 8, 3000.0), "investigations": (3, 8, 1500.0)}
        qfix = self.items.qty_fixed.to_numpy(float)
        qday = self.items.qty_per_day.to_numpy(float)
        for cat, (kmin, kmax, per_k) in spec.items():
            tgt = targets[cat]
            k = np.clip(_rint(tgt / 100 / per_k) + kmin, kmin, kmax)

            def pool_of(cids, cat=cat):
                groups = {}
                for p in np.unique(self.proc[cids]):
                    groups[int(p)] = (np.flatnonzero(self.proc[cids] == p), pools[(int(p), cat)])
                return groups

            cid, item = self._sample_items(ids, k, pool_of)
            unit = _rint(mrp_all[item] * rng.uniform(0.55, 0.65, len(item)))
            gw = rng.gamma(2.0, size=len(item)) * unit
            tot = np.zeros(n)
            np.add.at(tot, cid, gw)
            t_line = tgt[cid] * gw / tot[cid]
            # clinically plausible quantity: fixed allowance plus a per-day allowance over the stay
            qcap = np.maximum(1, np.floor(qfix[item] + qday[item] * self.los[cid])).astype(np.int64)
            qty = np.clip(_rint(t_line / unit), 1, qcap)
            sdate = self.adm[cid] + (rng.random(len(cid)) * (self.los[cid] + 1)).astype(int)
            frames.append(self._item_frame(cid, item, qty, unit, sdate))

        L = pd.concat(frames, ignore_index=True)
        L["qty"] = L.qty.astype(np.int64)
        L["unit"] = L.unit.astype(np.int64)
        L = L.sort_values(["cid", "cat"], kind="stable").reset_index(drop=True)
        L["amount"] = L.qty * L.unit
        self.L = L
        self.normal_total = self._totals(L)

    def _item_frame(self, cid, item, qty, unit, sdate) -> pd.DataFrame:
        it = self.items
        return pd.DataFrame(
            {
                "cid": cid,
                "cat": [CAT[c] for c in it.category.to_numpy()[item]],
                "item_code": it.item_code.to_numpy()[item],
                "description": it.name.to_numpy()[item],
                "qty": qty,
                "unit": unit,
                "sdate": sdate,
                "mrp": it.mrp_paise.to_numpy()[item],
                "np": it.non_payable.to_numpy()[item],
                "item": item,
            }
        )

    def _totals(self, L: pd.DataFrame) -> np.ndarray:
        tot = np.zeros(self.n, dtype=np.int64)
        np.add.at(tot, L.cid.to_numpy(), (L.qty * L.unit).to_numpy())
        return tot

    # ------------------------------------------------------------------ 5. scenario transforms
    def _lines_of(self, name: str, cats: tuple[str, ...] | None = None) -> np.ndarray:
        L = self.L
        m = self.scenario[L.cid.to_numpy()] == name
        if cats is not None:
            m &= L.cat.isin([CAT[c] for c in cats]).to_numpy()
        return m

    def _pick_per_claim(self, mask: np.ndarray, kmin: int, kmax: int) -> np.ndarray:
        """Randomly choose between kmin and kmax of the masked lines in each claim."""
        rng = self.rng
        idx = np.flatnonzero(mask)
        cid = self.L.cid.to_numpy()[idx]
        key = rng.random(len(idx))
        order = np.lexsort((key, cid))
        idx, cid = idx[order], cid[order]
        _, first = np.unique(cid, return_index=True)
        rank = np.arange(len(idx)) - np.repeat(first, np.diff(np.append(first, len(idx))))
        want = rng.integers(kmin, kmax + 1, self.n)
        return idx[rank < want[cid]]

    def _shift_test_claims(self, cids: np.ndarray) -> None:
        """Move a test claim (and its line dates) earlier so discharge stays on or before the cut-off."""
        over = (self.adm[cids] + self.los[cids] - TEST_LAST_DISCHARGE).astype(int)
        shift = np.where(self.is_test[cids], np.maximum(0, over), 0)
        if not shift.any():
            return
        s = np.zeros(self.n, dtype=int)
        s[cids] = shift
        self.adm = self.adm - s
        L = self.L
        L["sdate"] = L.sdate.to_numpy() - s[L.cid.to_numpy()]

    def _scale_qty(self, mask: np.ndarray, factor: np.ndarray) -> None:
        L = self.L
        f = factor[L.cid.to_numpy()[mask]]
        L.loc[mask, "qty"] = np.maximum(1, _rint(L.qty.to_numpy()[mask] * f))

    def _extend_stay(self, cids: np.ndarray, extra: np.ndarray) -> None:
        """Add `extra` ward days to the given claims (room qty, nursing qty, LOS)."""
        L = self.L
        e = np.zeros(self.n, dtype=int)
        e[cids] = extra
        cl = L.cid.to_numpy()
        room = (L.cat == CAT["room"]).to_numpy() & (e[cl] > 0)
        L.loc[room, "qty"] = L.qty.to_numpy()[room] + e[cl[room]]
        nursing = (L.cat == CAT["nursing"]).to_numpy() & (e[cl] > 0)
        L.loc[nursing, "qty"] = L.qty.to_numpy()[nursing] + e[cl[nursing]]
        self.los = self.los + e
        self._shift_test_claims(cids)

    def apply_scenarios(self) -> None:
        rng, L = self.rng, self.L
        n = self.n
        cl = L.cid.to_numpy()
        sc = self.scenario

        # room rent above cap: 15-80% over the cap
        m = self._lines_of("room_rent_above_cap", ("room",))
        cap = self.room_cap[cl[m]]
        new = _round_to(cap * rng.uniform(1.15, 1.8, m.sum()), 50)
        L.loc[m, "unit"] = np.maximum(new, cap + 5000)

        # above contracted tariff: OT + surgeon pushed 12-50% over the package rate
        ids = np.flatnonzero((sc == "above_tariff") & self.active)
        goal = _round_to(self.tariff[ids] * rng.uniform(1.12, 1.5, len(ids)), 10)
        goal_of = np.zeros(n, dtype=np.int64)
        goal_of[ids] = goal
        pm = self._lines_of("above_tariff", ("ot", "surgeon"))
        cur = np.zeros(n, dtype=np.int64)
        np.add.at(cur, cl[pm], L.unit.to_numpy()[pm])
        f = goal_of[cl[pm]] / np.maximum(cur[cl[pm]], 1)
        L.loc[pm, "unit"] = np.maximum(_round_to(L.unit.to_numpy()[pm] * f, 10), 100_000)

        # item above MRP: 1-2 pharmacy / consumable lines billed at 112-160% of MRP
        cand = self._lines_of("item_above_mrp", ("pharmacy", "consumables")) & ~L.np.to_numpy()
        pick = self._pick_per_claim(cand, 1, 2)
        mrp = L.mrp.to_numpy()[pick]
        L.loc[pick, "unit"] = np.ceil(mrp * rng.uniform(1.12, 1.6, len(pick))).astype(np.int64)

        # service date outside the stay: 1-2 pharmacy / investigation lines dated before admission or after discharge
        cand = self._lines_of("service_date_outside_stay", ("pharmacy", "investigations"))
        pick = self._pick_per_claim(cand, 1, 2)
        c = cl[pick]
        before = rng.random(len(pick)) < 0.5
        off = rng.integers(1, 8, len(pick))
        L.loc[pick, "sdate"] = np.where(before, self.adm[c] - off, self.adm[c] + self.los[c] + off)

        # inflated pharmacy share: pharmacy grows to 30-45% of the bill
        ids = np.flatnonzero((sc == "inflated_pharmacy") & self.active)
        ph = (L.cat == CAT["pharmacy"]).to_numpy()
        amt = (L.qty * L.unit).to_numpy()
        p_tot = np.zeros(n)
        np.add.at(p_tot, cl[ph], amt[ph])
        all_tot = np.zeros(n)
        np.add.at(all_tot, cl, amt)
        s = rng.uniform(0.30, 0.45, n)
        k = np.ones(n)
        k[ids] = (s[ids] / (1 - s[ids]) * (all_tot[ids] - p_tot[ids])) / np.maximum(p_tot[ids], 1)
        self._scale_qty(ph & (sc[cl] == "inflated_pharmacy"), k)

        # stretched stay: LOS 2-3x with matching room / nursing days and more medication
        ids = np.flatnonzero((sc == "stretched_stay") & self.active)
        new_los = np.maximum(self.los[ids] + 2, _rint(self.los[ids] * rng.uniform(2.0, 3.0, len(ids))))
        extra = np.minimum(new_los - self.los[ids], 20)
        kph = np.ones(n)
        kph[ids] = ((self.los[ids] + extra) / self.los[ids]) ** 0.6
        self._extend_stay(ids, extra)
        cl = self.L.cid.to_numpy()
        self._scale_qty((self.L.cat == CAT["pharmacy"]).to_numpy() & (sc[cl] == "stretched_stay"), kph)

        # combination of 2-3 mild signals
        ids = np.flatnonzero((sc == "combination") & self.active)
        kk = rng.integers(2, 4, len(ids))
        sig = np.argsort(rng.random((len(ids), 4)), axis=1) < kk[:, None]
        # signal 0: one or two extra days
        sel = ids[sig[:, 0]]
        self._extend_stay(sel, rng.integers(1, 3, len(sel)))
        L = self.L
        cl = L.cid.to_numpy()
        for j, (cat, lo, hi) in enumerate(
            (("pharmacy", 1.25, 1.4), ("investigations", 1.4, 1.8), ("consumables", 1.2, 1.35)), start=1
        ):
            f = np.ones(n)
            f[ids[sig[:, j]]] = rng.uniform(lo, hi, int(sig[:, j].sum()))
            self._scale_qty((L.cat == CAT[cat]).to_numpy() & (f[cl] > 1), f)

        # pre-auth escalation: final bill 1.4-2x the pre-auth, via nursing, pharmacy, consumables, investigations
        ids = np.flatnonzero((sc == "preauth_escalation") & self.active)
        amt = (L.qty * L.unit).to_numpy()
        scal = L.cat.isin([CAT[c] for c in ("nursing", "pharmacy", "consumables", "investigations")]).to_numpy()
        s_tot = np.zeros(n)
        np.add.at(s_tot, cl[scal], amt[scal])
        all_tot = np.zeros(n)
        np.add.at(all_tot, cl, amt)
        goal = self.preauth * rng.uniform(1.4, 2.0, n)
        k = np.ones(n)
        k[ids] = np.maximum(1.0, (goal[ids] - (all_tot[ids] - s_tot[ids])) / np.maximum(s_tot[ids], 1))
        nm = (L.cat == CAT["nursing"]).to_numpy() & (sc[cl] == "preauth_escalation")
        L.loc[nm, "unit"] = _round_to(L.unit.to_numpy()[nm] * k[cl[nm]], 1)
        self._scale_qty(scal & ~nm & (sc[cl] == "preauth_escalation"), k)

        # non-payable items billed: 1-3 IRDAI non-payable items appended
        ids = np.flatnonzero((sc == "non_payable_billed") & self.active)
        np_pool = np.flatnonzero(self.items.non_payable.to_numpy())
        k = rng.integers(1, 4, n)
        cid, item = self._sample_items(ids, k, lambda c: {0: (np.arange(len(c)), np_pool)})
        mrp_all = self.items.mrp_paise.to_numpy(np.int64)
        codes = self.items.item_code.to_numpy()[item]
        per_day = np.isin(codes, ["NP_ATTENDANT", "NP_TV"])
        cheap = mrp_all[item] < 10_000
        qty = np.where(
            per_day, self.los[cid], np.where(cheap, rng.integers(4, 17, len(item)), rng.integers(1, 3, len(item)))
        )
        unit = _rint(mrp_all[item] * rng.uniform(0.85, 1.0, len(item)))
        sdate = self.adm[cid] + (rng.random(len(cid)) * (self.los[cid] + 1)).astype(int)
        add = self._item_frame(cid, item, qty.astype(np.int64), unit, sdate)
        self.L = pd.concat([self.L, add], ignore_index=True).sort_values(["cid", "cat"], kind="stable")
        self.L = self.L.reset_index(drop=True)

        # over-billing providers: every line inflated 1.35-1.5x; room / ICU stay under their caps, items under MRP
        L = self.L
        cl = L.cid.to_numpy()
        f = np.ones(n)
        for pi, fac in self.ob_factor.items():
            sel = self.prov == pi
            f[sel] = np.clip(fac * rng.uniform(0.98, 1.02, int(sel.sum())), 1.35, 1.5)
        obl = self.ob[cl]
        fl = f[cl]
        unit = L.unit.to_numpy().astype(float)
        cat = L.cat.to_numpy()
        new = unit * fl
        room = obl & (cat == CAT["room"])
        rc = self.room_cap[cl]
        new_room = _round_to(new, 50)
        new_room = np.where(rc >= 0, np.minimum(new_room, np.maximum(_floor_to(rc * 0.98, 50), unit)), new_room)
        icu = obl & (cat == CAT["icu"])
        icap = self.icu_cap[cl]
        new_icu = _round_to(new, 100)
        new_icu = np.where(icap >= 0, np.minimum(new_icu, np.maximum(_floor_to(icap * 0.98, 100), unit)), new_icu)
        svc10 = obl & np.isin(cat, [CAT["ot"], CAT["surgeon"]])
        nurse = obl & (cat == CAT["nursing"])
        itm = obl & (L.mrp.to_numpy() >= 0)
        out = L.unit.to_numpy().copy()
        out[room] = new_room[room]
        out[icu] = new_icu[icu]
        out[svc10] = _round_to(new[svc10], 10)
        out[nurse] = _round_to(new[nurse], 1)
        out[itm] = np.minimum(_rint(new[itm]), L.mrp.to_numpy()[itm])
        L["unit"] = out
        L["amount"] = L.qty * L.unit
        self.L = L

    # ------------------------------------------------------------------ clones
    def _clone(self, src: np.ndarray, scenario: str, new_pol: np.ndarray | None = None) -> np.ndarray:
        """Append copies of claims `src` (same lines). Returns new claim indices."""
        k = len(src)
        new_ids = np.arange(self.n, self.n + k)
        per_claim = [
            "proc",
            "age_s",
            "adm",
            "los",
            "icu_days",
            "pol",
            "prov",
            "is_test",
            "active",
            "age",
            "ob",
            "network",
            "cashless",
            "pk",
            "si",
            "room_cap",
            "icu_cap",
            "copay_milli",
            "deductible",
            "sub_limit",
            "tariff",
            "room_cat",
            "rent",
            "icu_rent",
            "target",
            "preauth",
            "normal_total",
        ]
        for name in per_claim:
            arr = getattr(self, name)
            setattr(self, name, np.concatenate([arr, arr[src]]))
        self.scenario = np.concatenate([self.scenario, np.full(k, scenario, dtype=object)])
        self.parent = np.concatenate([self.parent, src])
        if new_pol is not None:
            self.pol[new_ids] = new_pol
            self.si[new_ids] = self.pol_si[new_pol]
            self.age[new_ids] = self.mem_age[new_pol]
        L = self.L
        add = L[np.isin(L.cid.to_numpy(), src)].copy()
        remap = np.full(self.n, -1)
        remap[src] = new_ids
        add["cid"] = remap[add.cid.to_numpy()]
        self.L = (
            pd.concat([L, add], ignore_index=True).sort_values(["cid", "cat"], kind="stable").reset_index(drop=True)
        )
        self.n += k
        return new_ids

    def make_clones(self) -> None:
        rng = self.rng
        clean = (self.scenario == "") & self.active & ~self.ob
        dup_src = []
        for split_test in (False, True):
            n_split = self.n_test if split_test else self.n_train
            k = int(round(SCENARIO_RATES["exact_duplicate"] * n_split))
            pool = np.flatnonzero(clean & (self.is_test == split_test))
            src = rng.choice(pool, size=min(k, len(pool)), replace=False)
            clean[src] = False
            dup_src.append(src)
        # reused bill image: a clean test claim's bill attached to a second claim on another member's policy
        pool = np.flatnonzero(clean & self.is_test & (self.adm <= TEST_HI - 25))
        src = np.sort(rng.choice(pool, size=min(REUSED_PAIRS, len(pool)), replace=False))
        new_pol = []
        keep = []
        taken = set(self.pol[self.active].tolist())
        for ci in src:
            cand = np.flatnonzero(
                (self.pol_prod == self.pk[ci])
                & (self.pol_si >= self.si[ci])
                & (self.pol_ped_end <= self.adm[ci] - TENURE_MARGIN)
                & ((self.proc_gender[self.proc[ci]] < 0) | (self.mem_gender == self.proc_gender[self.proc[ci]]))
            )
            cand = np.array([c for c in cand if c not in taken])
            if len(cand) == 0:
                continue
            pj = int(rng.choice(cand))
            taken.add(pj)
            new_pol.append(pj)
            keep.append(ci)
        self._clone(np.sort(np.concatenate(dup_src)), "exact_duplicate")
        self.reused_src = np.array(keep, dtype=int)
        self.reused_new = self._clone(self.reused_src, "reused_document", np.array(new_pol, dtype=int))
        # caps follow the clone policy's own sum insured (same product, SI >= source)
        prods = self.w.products
        rr = np.array([p.pct_milli(p.room_rent_cap_pct) for p in prods])[self.pk[self.reused_new]]
        ic = np.array([p.pct_milli(p.icu_cap_pct) for p in prods])[self.pk[self.reused_new]]
        si = self.si[self.reused_new]
        self.room_cap[self.reused_new] = np.where(rr >= 0, half_up_div(si * np.maximum(rr, 0), 100_000), -1)
        self.icu_cap[self.reused_new] = np.where(ic >= 0, half_up_div(si * np.maximum(ic, 0), 100_000), -1)

    # ------------------------------------------------------------------ 6. validation
    def _waiting_violation(self) -> np.ndarray:
        p, pj, adm = self.proc, self.pol, self.adm
        v = (adm - self.pol_start[pj]).astype(int) < self.pol_initial[pj]
        v |= self.proc_listed[p] & (adm < self.pol_listed_end[pj])
        v |= self.has_cond[pj, p] & (adm < self.pol_ped_end[pj])
        return v

    def _duplicates(self, claimed: np.ndarray, created: np.ndarray) -> np.ndarray:
        df = pd.DataFrame(
            {
                "pol": self.pol,
                "prov": self.prov,
                "adm": self.adm,
                "amt": claimed,
                "created": created,
                "i": np.arange(self.n),
            }
        )[self.active]
        df = df.sort_values(["created", "i"])
        dup = df.duplicated(["pol", "prov", "adm", "amt"], keep="first")
        out = np.zeros(self.n, dtype=bool)
        out[df.i.to_numpy()[dup.to_numpy()]] = True
        return out

    def evaluate(self, created: np.ndarray):
        L = self.L[self.active[self.L.cid.to_numpy()]]
        claimed = self._totals(L)
        train_amt = np.where(self.active & ~self.is_test & (self.scenario != "exact_duplicate"), claimed, 0)
        spent = np.zeros(len(self.pol_si), dtype=np.int64)
        np.add.at(spent, self.pol, train_amt)
        self.balance_pol = self.pol_si - spent
        ca = ClaimArrays(
            admission=self.adm,
            discharge=self.adm + self.los,
            claimed=claimed,
            room_cap=self.room_cap,
            icu_cap=self.icu_cap,
            tariff=self.tariff,
            sub_limit=self.sub_limit,
            deductible=self.deductible,
            copay_milli=self.copay_milli,
            balance=self.balance_pol[self.pol],
            waiting_violation=self._waiting_violation(),
            duplicate=self._duplicates(claimed, created),
        )
        la = LineArrays(
            cid=L.cid.to_numpy(),
            cat=L.cat.to_numpy(),
            qty=L.qty.to_numpy(np.int64),
            unit=L.unit.to_numpy(np.int64),
            amount=(L.qty * L.unit).to_numpy(np.int64),
            service_date=L.sdate.to_numpy(np.int64),
            mrp=L.mrp.to_numpy(np.int64),
            non_payable=L.np.to_numpy(bool),
        )
        leak, flags = evaluate(ca, la)
        return claimed, leak, flags

    def created_at(self) -> np.ndarray:
        rng = self.rng
        dis = (self.adm + self.los).astype("datetime64[D]").astype("datetime64[s]")
        delay = np.where(self.cashless, rng.integers(0, 2, self.n), rng.integers(2, 21, self.n))
        secs = delay * 86400 + rng.integers(8 * 3600, 20 * 3600, self.n)
        created = dis + secs.astype("timedelta64[s]")
        created = np.minimum(created, NOW_CAP)
        clone = self.parent >= 0
        later = created[self.parent[clone]] + (rng.integers(3, 31, clone.sum()) * 86400).astype("timedelta64[s]")
        later = np.minimum(later, NOW_CAP)
        later = np.where(
            later <= created[self.parent[clone]], created[self.parent[clone]] + np.timedelta64(3600, "s"), later
        )
        created[clone] = later
        return created

    def validate(self) -> None:
        created = self.created_at()
        self.created = created
        dropped = {"R07/R10 fit": 0, "construction": 0}
        errors: list[str] = []
        for _ in range(8):
            claimed, leak, flags = self.evaluate(created)
            fs = flag_sets(flags)
            bad = np.zeros(self.n, dtype=bool)
            for i in np.flatnonzero(self.active):
                exp = EXPECTED_RULES.get(self.scenario[i], frozenset())
                got = fs[i]
                if got == exp and (self.scenario[i] not in RULE_SCENARIOS or leak[i] > 0):
                    continue
                bad[i] = True
                if (got - exp) <= {"R07", "R10"} and exp <= got:
                    dropped["R07/R10 fit"] += 1
                else:
                    dropped["construction"] += 1
                    if len(errors) < 10:
                        errors.append(
                            f"claim {i} scenario={self.scenario[i] or 'clean'} expected={set(exp)} got={set(got)}"
                        )
            # anything whose source claim was dropped goes too
            if not bad.any():
                break
            self.active &= ~bad
            clone = self.parent >= 0
            self.active[clone] &= self.active[self.parent[clone]]
        self.claimed, self.leak, self.flags = claimed, leak, flags
        self.report["dropped"] = dropped
        self.report["construction_errors"] = errors

    # ------------------------------------------------------------------ outputs
    def outputs(self) -> ClaimsResult:
        w = self.w
        act = np.flatnonzero(self.active)
        order = act[np.lexsort((act, self.created[act]))]
        cid_of = np.full(self.n, "", dtype=object)
        cid_of[order] = [f"C{i + 1:07d}" for i in range(len(order))]

        prov_ids = w.providers.id.to_numpy()
        # bill numbers: running sequence per provider in discharge order; clones reuse the source's bill
        dis = self.adm + self.los
        bill = np.full(self.n, "", dtype=object)
        base = act[self.parent[act] < 0]
        dfb = pd.DataFrame({"i": base, "p": self.prov[base], "d": dis[base]}).sort_values(["p", "d", "i"])
        dfb["seq"] = dfb.groupby("p").cumcount()
        start = self.rng.integers(1000, 6000, len(prov_ids))
        for i, p, s in zip(dfb.i, dfb.p, dfb.seq, strict=True):
            bill[i] = f"B-{prov_ids[p]}-{start[p] + s:06d}"
        clones = act[self.parent[act] >= 0]
        bill[clones] = bill[self.parent[clones]]

        L = self.L[self.active[self.L.cid.to_numpy()]].copy()
        cat = L.cat.to_numpy()
        room_unit = np.zeros(self.n, dtype=np.int64)
        rm = cat == CAT["room"]
        room_unit[L.cid.to_numpy()[rm]] = L.unit.to_numpy()[rm]
        pharm = np.zeros(self.n, dtype=np.int64)
        pm = cat == CAT["pharmacy"]
        np.add.at(pharm, L.cid.to_numpy()[pm], (L.qty * L.unit).to_numpy()[pm])

        procs = self.procs
        claims = pd.DataFrame(
            {
                "id": cid_of[order],
                "member_policy_id": w.policies.id.to_numpy()[self.pol[order]],
                "provider_id": prov_ids[self.prov[order]],
                "procedure_code": procs.code.to_numpy()[self.proc[order]],
                "diagnosis_code": procs.icd10.to_numpy()[self.proc[order]],
                "admission_at": _iso(self.adm[order]),
                "discharge_at": _iso(dis[order]),
                "los": self.los[order],
                "room_category": self.room_cat[order],
                "room_rent_per_day": fmt_paise(room_unit[order]).to_numpy(),
                "preauth_amount": np.where(
                    self.preauth[order] >= 0, fmt_paise(np.maximum(self.preauth[order], 0)).to_numpy(), ""
                ),
                "claimed_amount": fmt_paise(self.claimed[order]).to_numpy(),
                "pharmacy_amount": fmt_paise(pharm[order]).to_numpy(),
                "claim_type": np.where(self.cashless[order], "cashless", "reimbursement"),
                "status": "received",
                "split": np.where(self.is_test[order], "test", "train"),
                "bill_no": bill[order],
                "created_at": [str(t).replace("T", " ") + "+00:00" for t in self.created[order]],
            }
        )
        rank = np.full(self.n, -1)
        rank[order] = np.arange(len(order))
        L["rank"] = rank[L.cid.to_numpy()]
        L["seq"] = np.arange(len(L))
        L = L.sort_values(["rank", "cat", "seq"], kind="stable")
        lines = pd.DataFrame(
            {
                "claim_id": cid_of[L.cid.to_numpy()],
                "category": np.array(CATEGORIES)[L.cat.to_numpy()],
                "item_code": L.item_code.to_numpy(),
                "description": L.description.to_numpy(),
                "qty": L.qty.to_numpy(),
                "unit_price": fmt_paise(L.unit.to_numpy()).to_numpy(),
                "amount": fmt_paise((L.qty * L.unit).to_numpy()).to_numpy(),
                "service_date": _iso(L.sdate.to_numpy(np.int64)),
            }
        )

        # ground truth
        gt_rows = []
        for i in order:
            s = self.scenario[i]
            if not s:
                continue
            if s in RULE_SCENARIOS or s in ("early_claim", "reused_document"):
                amt = int(self.leak[i]) if s in RULE_SCENARIOS else int(self.claimed[i])
            else:
                amt = max(0, int(self.claimed[i] - self.normal_total[i]))
            gt_rows.append((cid_of[i], s, amt))
        gt = pd.DataFrame(gt_rows, columns=["claim_id", "scenario", "leak_paise"])
        gt["leakage_amount"] = fmt_paise(gt.leak_paise.to_numpy()).to_numpy() if len(gt) else []

        reused = [
            (cid_of[a], cid_of[b]) for a, b in zip(self.reused_src, self.reused_new, strict=True) if self.active[b]
        ]
        ob = [(prov_ids[p], round(f, 3)) for p, f in self.ob_factor.items()]
        self.report["claims_total_paise"] = int(self.claimed[act].sum())
        self.report["n_train"] = int((~self.is_test[act]).sum())
        self.report["n_test"] = int(self.is_test[act].sum())
        self.report["ob_share"] = float(self.ob[act].mean())
        self.out_index = order
        self.cid_of = cid_of
        return ClaimsResult(claims, lines, gt, self.balance_pol, ob, self.report, reused)


def generate_claims(
    rng: np.random.Generator, world: World, n_train: int, n_test: int
) -> tuple[ClaimsResult, Generator]:
    g = Generator(rng, world, n_train, n_test)
    g._policy_arrays()
    g.skeletons()
    g.assign_policies()
    g.assign_providers()
    g.money_context()
    g.choose_scenarios()
    g.build_lines()
    g.apply_scenarios()
    g.make_clones()
    g.validate()
    return g.outputs(), g
