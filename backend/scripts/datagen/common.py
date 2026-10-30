"""Paths, money helpers, reference data and policy products shared by the generators.

Money is handled internally as int64 paise so every sum is exact and vectorisable;
it is formatted as a 2-decimal string only when written out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
POLICIES_DIR = DATA_DIR / "policies"
PRODUCTS_JSON = POLICIES_DIR / "products.json"
DEFAULT_OUT = DATA_DIR / "generated"

CATEGORIES = ("room", "icu", "nursing", "ot", "surgeon", "implants", "pharmacy", "consumables", "investigations")
CAT = {c: i for i, c in enumerate(CATEGORIES)}
MRP_CATS = (CAT["pharmacy"], CAT["consumables"], CAT["investigations"], CAT["implants"])
ASSOCIATED_CATS = (CAT["nursing"], CAT["ot"], CAT["surgeon"])
PROC_CATS = (CAT["ot"], CAT["surgeon"])

# Split of the remainder after room, ICU, pharmacy and implants:
# (nursing, ot, surgeon, consumables, investigations).
TEMPLATES: dict[str, tuple[float, float, float, float, float]] = {
    "surgical": (0.12, 0.28, 0.35, 0.14, 0.11),
    "daycare_eye": (0.04, 0.30, 0.46, 0.14, 0.06),
    "cardiac": (0.12, 0.30, 0.30, 0.16, 0.12),
    "maternity": (0.16, 0.22, 0.38, 0.14, 0.10),
    "medical": (0.32, 0.00, 0.26, 0.12, 0.30),
}


def to_paise(value: str | float | None) -> int:
    """Exact conversion of a decimal string (or float with <= 2dp) to integer paise."""
    if value is None:
        return -1
    s = str(value).strip()
    neg = s.startswith("-")
    s = s.lstrip("-")
    whole, _, frac = s.partition(".")
    p = int(whole or 0) * 100 + int((frac + "00")[:2])
    return -p if neg else p


def fmt_paise(arr: np.ndarray | pd.Series) -> pd.Series:
    """Vectorised int paise -> '1234.56' strings. Negative values are not expected for money columns."""
    a = np.asarray(arr, dtype=np.int64)
    if (a < 0).any():
        raise ValueError("negative money value")
    rupees = pd.Series(a // 100).astype(str)
    paise = pd.Series(a % 100).astype(str).str.zfill(2)
    return rupees + "." + paise


def fmt_one(p: int) -> str:
    return f"{p // 100}.{p % 100:02d}"


def half_up_div(num: np.ndarray, den: np.ndarray | int) -> np.ndarray:
    """round-half-up(num / den) for non-negative int64 arrays (mirrors Decimal ROUND_HALF_UP)."""
    num = np.asarray(num, dtype=np.int64)
    den = np.asarray(den, dtype=np.int64)
    return (2 * num + den) // (2 * den)


def add_months(d: date, months: int) -> date:
    """Same calendar arithmetic as the rules engine (clamp to the last valid day)."""
    year, month = divmod(d.month - 1 + months, 12)
    year += d.year
    month += 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


@dataclass
class Reference:
    procedures: pd.DataFrame
    items: pd.DataFrame
    multipliers: dict[tuple[str, str], float]

    @property
    def listed_procedures(self) -> list[str]:
        return sorted(self.procedures.loc[self.procedures.waiting_category == "listed_condition", "code"])


def load_reference(ref_dir: Path = REFERENCE_DIR) -> Reference:
    procs = pd.read_csv(ref_dir / "procedures.csv", dtype={"icd10": str, "implant_item": str}, keep_default_na=False)
    procs["base_rate_paise"] = procs.base_rate.map(lambda v: to_paise(f"{v:.2f}"))
    procs["age"] = procs.age_profile.map(json.loads)
    items = pd.read_csv(ref_dir / "items.csv", keep_default_na=False)
    items["mrp_paise"] = items.mrp.map(lambda v: to_paise(f"{v:.2f}"))
    items["non_payable"] = items.non_payable.astype(str).str.lower().eq("true")
    mult = pd.read_csv(ref_dir / "multipliers.csv", dtype=str)
    multipliers = {(r.factor_type, r.key): float(r.value) for r in mult.itertuples()}
    return Reference(procs, items, multipliers)


CLAUSE_BASE = {
    "sum_insured": "2.2",
    "non_payable": "3.14",
    "room_rent_cap_pct": "4.2",
    "icu_cap_pct": "4.3",
    "proportional_deduction": "4.4",
    "mrp": "4.5",
    "tariff": "4.6",
    "waiting_periods": "5.1",
    "initial_days": "5.2",
    "listed_conditions_months": "5.3",
    "listed_procedures": "5.3",
    "pre_existing_months": "5.4",
    "sub_limits": "6.1",
    "copay_pct": "7.1",
    "deductible": "7.2",
    "claims_procedure": "8.1",
    "fraud": "9.5",
}


@dataclass
class Product:
    id: str
    name: str
    version: str
    uin: str
    sum_insured_options: list[str]
    room_rent_cap_pct: str | None
    icu_cap_pct: str | None
    copay_pct: str
    deductible: str
    sub_limits: dict[str, str]
    waiting_periods: dict
    clause_refs: dict[str, str] = field(default_factory=dict)

    def pct_milli(self, value: str | None) -> int:
        """'1.000' -> 1000 (thousandths of a percent); None -> -1."""
        if value is None:
            return -1
        whole, _, frac = value.partition(".")
        return int(whole) * 1000 + int((frac + "000")[:3])


def sub_limit_clause(index: int) -> str:
    return f"6.{index + 2}"


def load_products(ref: Reference, path: Path = PRODUCTS_JSON) -> list[Product]:
    raw = json.loads(path.read_text())
    products = []
    for p in raw["products"]:
        wp = dict(p["waiting_periods"])
        wp["listed_procedures"] = ref.listed_procedures
        prod = Product(
            id=p["id"],
            name=p["name"],
            version=p["version"],
            uin=p["uin"],
            sum_insured_options=p["sum_insured_options"],
            room_rent_cap_pct=p["room_rent_cap_pct"],
            icu_cap_pct=p["icu_cap_pct"],
            copay_pct=p["copay_pct"],
            deductible=p["deductible"],
            sub_limits=dict(p["sub_limits"]),
            waiting_periods=wp,
        )
        refs = dict(CLAUSE_BASE)
        for i, code in enumerate(prod.sub_limits):
            refs[f"sub_limits.{code}"] = sub_limit_clause(i)
        prod.clause_refs = refs
        products.append(prod)
    return products
