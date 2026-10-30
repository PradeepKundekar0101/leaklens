"""Peer statistics and robust z-scores.

Levels: L1 (procedure, hospital tier, city tier), L2 (procedure, hospital tier), L3 (procedure).
At scoring time the most specific level with n >= 30 is used.
rz = 0.6745 (x - median) / MAD; if MAD = 0, rz = (x - median) / (1.2533 * mean absolute deviation);
if that is 0, rz = 0.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.services.anomaly.features import HIGH_SIDE, LOW_SIDE, Z_FEATURES

MIN_N = 30
LEVEL_KEYS = {
    1: ["procedure_code", "hospital_tier", "city_tier"],
    2: ["procedure_code", "hospital_tier"],
    3: ["procedure_code"],
}


@dataclass(frozen=True)
class Stat:
    median: float
    mad: float
    mean_ad: float
    n: int
    level: int


def _mad(x: pd.Series) -> float:
    return float(np.median(np.abs(x - np.median(x))))


def _mean_ad(x: pd.Series) -> float:
    return float(np.mean(np.abs(x - np.mean(x))))


def compute_peer_stats(train: pd.DataFrame) -> pd.DataFrame:
    """Long-format table: feature, level, procedure_code, hospital_tier, city_tier, median, mad, mean_ad, n."""
    frames = []
    for level, keys in LEVEL_KEYS.items():
        grouped = train.groupby(keys)
        for feature in Z_FEATURES:
            agg = grouped[feature].agg(median="median", mad=_mad, mean_ad=_mean_ad, n="count").reset_index()
            agg["feature"] = feature
            agg["level"] = level
            frames.append(agg)
    out = pd.concat(frames, ignore_index=True)
    for col in ("hospital_tier", "city_tier"):
        if col not in out:
            out[col] = np.nan
    return out[["feature", "level", "procedure_code", "hospital_tier", "city_tier", "median", "mad", "mean_ad", "n"]]


class PeerTable:
    """In-memory lookup over the active peer statistics."""

    def __init__(self, stats: pd.DataFrame) -> None:
        self._index: dict[tuple, Stat] = {}
        for r in stats.itertuples(index=False):
            ht = None if pd.isna(r.hospital_tier) else int(r.hospital_tier)
            ct = None if pd.isna(r.city_tier) else int(r.city_tier)
            key = (
                r.feature,
                int(r.level),
                r.procedure_code,
                ht if r.level <= 2 else None,
                ct if r.level == 1 else None,
            )
            self._index[key] = Stat(float(r.median), float(r.mad), float(r.mean_ad), int(r.n), int(r.level))

    def lookup(self, feature: str, procedure_code: str, hospital_tier: int, city_tier: int) -> Stat | None:
        for level, key in (
            (1, (feature, 1, procedure_code, hospital_tier, city_tier)),
            (2, (feature, 2, procedure_code, hospital_tier, None)),
            (3, (feature, 3, procedure_code, None, None)),
        ):
            stat = self._index.get(key)
            if stat is not None and (stat.n >= MIN_N or level == 3):
                return stat
        return None


def robust_z(x: float, stat: Stat | None) -> float:
    if stat is None:
        return 0.0
    if stat.mad > 0:
        return 0.6745 * (x - stat.median) / stat.mad
    if stat.mean_ad > 0:
        return (x - stat.median) / (1.2533 * stat.mean_ad)
    return 0.0


def one_sided(feature: str, rz: float) -> float:
    if feature in HIGH_SIDE:
        return max(0.0, rz)
    if feature in LOW_SIDE:
        return max(0.0, -rz)
    return 0.0


def z_row(table: PeerTable, row) -> tuple[dict[str, dict], float]:
    """Per-feature z details and the claim-level z (max one-sided rz)."""
    details: dict[str, dict] = {}
    best = 0.0
    ht, ct = int(row["hospital_tier"]), int(row["city_tier"])
    for feature in Z_FEATURES:
        stat = table.lookup(feature, row["procedure_code"], ht, ct)
        rz = robust_z(float(row[feature]), stat)
        os_ = one_sided(feature, rz)
        best = max(best, os_)
        details[feature] = {
            "value": float(row[feature]),
            "median": stat.median if stat else None,
            "rz": round(rz, 3),
            "one_sided": round(os_, 3),
            "level": stat.level if stat else None,
            "n": stat.n if stat else 0,
        }
    return details, best


def z_matrix(table: PeerTable, df: pd.DataFrame) -> np.ndarray:
    """Claim-level z for every row (vectorised enough for 30k rows)."""
    return np.array([z_row(table, r)[1] for r in df.to_dict("records")], dtype=np.float64)
