from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.anomaly.explain import z_reasons
from app.services.anomaly.peer_stats import MIN_N, PeerTable, Stat, compute_peer_stats, one_sided, robust_z
from app.services.anomaly.scorer import percentile


def test_robust_z_uses_mad():
    assert robust_z(14.0, Stat(median=10, mad=2, mean_ad=3, n=50, level=1)) == pytest.approx(0.6745 * 2)


def test_robust_z_mad_zero_falls_back_to_mean_absolute_deviation():
    assert robust_z(14.0, Stat(median=10, mad=0, mean_ad=2, n=50, level=1)) == pytest.approx(4 / (1.2533 * 2))


def test_robust_z_both_zero_is_zero():
    assert robust_z(14.0, Stat(median=10, mad=0, mean_ad=0, n=50, level=1)) == 0.0
    assert robust_z(14.0, None) == 0.0


def test_one_sided_directions():
    assert one_sided("pharmacy_share", 3.0) == 3.0
    assert one_sided("pharmacy_share", -3.0) == 0.0
    assert one_sided("days_since_policy_start", -4.0) == 4.0  # low side
    assert one_sided("days_since_policy_start", 4.0) == 0.0
    assert one_sided("age", 9.0) == 0.0  # Isolation Forest input only


def _frame(groups: dict[tuple, int]) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(0)
    for (proc, ht, ct), n in groups.items():
        for _ in range(n):
            rows.append(
                {
                    "procedure_code": proc,
                    "hospital_tier": ht,
                    "city_tier": ct,
                    "log_amount": rng.normal(10, 1),
                    "los": 3.0,
                    "cost_per_day": 1000.0,
                    "pharmacy_share": 0.15,
                    "room_rent_per_day": 2000.0,
                    "final_to_preauth": 1.0,
                    "days_since_policy_start": 500.0,
                }
            )
    return pd.DataFrame(rows)


def test_level_fallback_picks_most_specific_level_with_enough_claims():
    df = _frame({("P1", 1, 1): MIN_N + 5, ("P1", 1, 2): 5, ("P1", 2, 2): 5})
    table = PeerTable(compute_peer_stats(df))
    assert table.lookup("los", "P1", 1, 1).level == 1
    assert table.lookup("los", "P1", 1, 2).level == 2  # L1 has 5, L2 (P1, tier 1) has 40
    assert table.lookup("los", "P1", 2, 2).level == 3  # L1 and L2 have 5 each
    assert table.lookup("los", "P_UNKNOWN", 1, 1) is None


def test_percentile_lookup_against_training_array():
    train = np.sort(np.array([1.0, 2.0, 3.0, 4.0]))
    assert list(percentile(train, np.array([0.5, 2.0, 2.5, 9.0]))) == [0.0, 0.5, 0.5, 1.0]


def test_z_reasons_template():
    reasons = z_reasons(
        {"pharmacy_share": {"value": 0.38, "median": 0.15, "rz": 3.9, "one_sided": 3.9, "level": 1, "n": 80}}
    )
    assert reasons[0]["text"] == "Pharmacy share 38% vs 15% peer median (3.9 robust z)"


def test_detection_code_never_reads_ground_truth():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.parts[-3:-1] == ("db", "models"):
            continue  # the table definition itself
        if "ground_truth" in path.read_text() or "GroundTruth" in path.read_text():
            offenders.append(str(path.relative_to(app_dir)))
    assert offenders == []
