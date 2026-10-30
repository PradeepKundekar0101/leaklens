"""One feature row per claim, computed in SQL so training, scoring and the peer histogram agree."""

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.money import inr

Z_FEATURES = [
    "log_amount",
    "los",
    "cost_per_day",
    "pharmacy_share",
    "room_rent_per_day",
    "final_to_preauth",
    "days_since_policy_start",
]
IF_ONLY_FEATURES = ["age", "hospital_tier", "city_tier"]
ALL_FEATURES = Z_FEATURES + IF_ONLY_FEATURES

HIGH_SIDE = frozenset(Z_FEATURES) - {"days_since_policy_start"}
LOW_SIDE = frozenset({"days_since_policy_start"})

LABELS = {
    "log_amount": "Claimed amount",
    "los": "Length of stay",
    "cost_per_day": "Cost per day",
    "pharmacy_share": "Pharmacy share",
    "room_rent_per_day": "Room rent per day",
    "final_to_preauth": "Final bill vs pre-auth",
    "days_since_policy_start": "Days since policy start",
    "age": "Member age",
    "hospital_tier": "Hospital tier",
    "city_tier": "City tier",
}

FEATURE_SQL = """
SELECT
    c.id AS claim_id,
    c.procedure_code,
    p.hospital_tier,
    p.city_tier,
    c.split,
    c.provider_id,
    ln(1 + c.claimed_amount)::float8 AS log_amount,
    c.los::float8 AS los,
    (c.claimed_amount / GREATEST(c.los, 1))::float8 AS cost_per_day,
    (c.pharmacy_amount / NULLIF(c.claimed_amount, 0))::float8 AS pharmacy_share,
    c.room_rent_per_day::float8 AS room_rent_per_day,
    COALESCE(c.claimed_amount / NULLIF(c.preauth_amount, 0), 1)::float8 AS final_to_preauth,
    (c.admission_at - mp.start_date)::float8 AS days_since_policy_start,
    m.age::float8 AS age
FROM claims c
JOIN providers p ON p.id = c.provider_id
JOIN member_policies mp ON mp.id = c.member_policy_id
JOIN members m ON m.id = mp.member_id
"""


async def load_features(session: AsyncSession, where: str = "", params: dict | None = None) -> pd.DataFrame:
    sql = FEATURE_SQL + (f" WHERE {where}" if where else "") + " ORDER BY c.id"
    result = await session.execute(text(sql), params or {})
    df = pd.DataFrame(result.mappings().all())
    if df.empty:
        return pd.DataFrame(columns=["claim_id", "procedure_code", "split", "provider_id", *ALL_FEATURES])
    df["pharmacy_share"] = df["pharmacy_share"].fillna(0.0)
    df["hospital_tier"] = df["hospital_tier"].astype(float)
    df["city_tier"] = df["city_tier"].astype(float)
    for col in ALL_FEATURES:
        df[col] = df[col].astype(np.float64)
    return df


async def features_for_claims(session: AsyncSession, claim_ids: list[str]) -> pd.DataFrame:
    return await load_features(session, "c.id = ANY(:ids)", {"ids": list(claim_ids)})


def format_value(feature: str, value: float) -> str:
    if feature == "log_amount":
        return inr(round(float(np.expm1(value))))
    if feature in ("pharmacy_share",):
        return f"{value * 100:.0f}%"
    if feature == "final_to_preauth":
        return f"{value:.2f}×"
    if feature in ("cost_per_day", "room_rent_per_day"):
        return inr(round(value))
    if feature in ("los",):
        return f"{value:.0f} days"
    if feature == "days_since_policy_start":
        return f"{value:.0f} days"
    return f"{value:.0f}"
