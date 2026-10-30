"""Scorer service: loads the active model at startup and scores claims.

risk = w_z * p_z + w_if * p_if, where p_z and p_if are percentiles against the stored *training* score arrays
(never against the current batch). Tiers: high >= 0.98, medium 0.90-0.98, low below 0.90 (configurable).
"""

import asyncio
import io
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
import shap
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import AnomalyScore, ModelRegistry, PeerStat
from app.db.session import session_scope
from app.services.anomaly.explain import shap_contributors, shap_reasons, z_reasons
from app.services.anomaly.features import ALL_FEATURES, features_for_claims
from app.services.anomaly.peer_stats import PeerTable, z_row
from app.storage import spaces

log = get_logger(__name__)


@dataclass
class ScoreResult:
    claim_id: str
    model_version: str
    risk: float
    tier: str
    p_z: float
    p_if: float
    max_rz: float
    feature_z: dict
    shap: list[dict]
    reasons: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "model_version": self.model_version,
            "risk": round(self.risk, 5),
            "tier": self.tier,
            "p_z": round(self.p_z, 5),
            "p_if": round(self.p_if, 5),
            "max_rz": round(self.max_rz, 3),
            "feature_z": self.feature_z,
            "shap": self.shap,
            "reasons": self.reasons,
        }


def percentile(sorted_train: np.ndarray, values: np.ndarray | float) -> np.ndarray:
    """Fraction of training scores <= value (searchsorted on the stored array)."""
    return np.searchsorted(sorted_train, values, side="right") / len(sorted_train)


def tier_for(risk: float) -> str:
    s = get_settings()
    if risk >= s.tier_high:
        return "high"
    if risk >= s.tier_medium:
        return "medium"
    return "low"


class Scorer:
    def __init__(self, bundle: dict, peer_stats: pd.DataFrame) -> None:
        self.version: str = bundle["version"]
        self.model = bundle["model"]
        self.z_train: np.ndarray = bundle["z_train_sorted"]
        self.if_train: np.ndarray = bundle["if_train_sorted"]
        self.table = PeerTable(peer_stats)
        self.explainer = shap.TreeExplainer(self.model)
        s = get_settings()
        self.w_z, self.w_if = float(s.risk_weight_z), float(s.risk_weight_if)

    def score_frame(self, df: pd.DataFrame, explain: bool = True) -> list[ScoreResult]:
        if df.empty:
            return []
        X = df[ALL_FEATURES].to_numpy(dtype=np.float64)
        if_scores = -self.model.score_samples(X)
        p_if = percentile(self.if_train, if_scores)
        rows = df.to_dict("records")
        details = [z_row(self.table, r) for r in rows]
        z = np.array([d[1] for d in details])
        p_z = percentile(self.z_train, z)
        shap_values = self.explainer.shap_values(X) if explain else None
        out = []
        for i, row in enumerate(rows):
            risk = self.w_z * float(p_z[i]) + self.w_if * float(p_if[i])
            contributors = shap_contributors(shap_values[i], X[i]) if shap_values is not None else []
            feature_z = details[i][0]
            tier = tier_for(risk)
            # SHAP always explains *something*; it is only a reason to look closer when the claim is unusual.
            unusual = tier != "low"
            out.append(
                ScoreResult(
                    claim_id=row["claim_id"],
                    model_version=self.version,
                    risk=risk,
                    tier=tier,
                    p_z=float(p_z[i]),
                    p_if=float(p_if[i]),
                    max_rz=float(z[i]),
                    feature_z=feature_z,
                    shap=contributors,
                    reasons=z_reasons(feature_z) + (shap_reasons(contributors) if unusual else []),
                )
            )
        return out


_active: Scorer | None = None


async def _load(session: AsyncSession) -> Scorer | None:
    reg = (
        await session.execute(
            select(ModelRegistry).where(ModelRegistry.kind == "iforest", ModelRegistry.active.is_(True))
        )
    ).scalar_one_or_none()
    if reg is None or reg.storage_key is None:
        return None
    data = await asyncio.to_thread(spaces.download, reg.storage_key)
    bundle = joblib.load(io.BytesIO(data))
    stats_rows = (await session.execute(select(PeerStat).where(PeerStat.version == reg.version))).scalars().all()
    stats = pd.DataFrame(
        [
            {
                "feature": s.feature,
                "level": s.level,
                "procedure_code": s.procedure_code,
                "hospital_tier": s.hospital_tier,
                "city_tier": s.city_tier,
                "median": float(s.median),
                "mad": float(s.mad),
                "mean_ad": float(s.mean_ad),
                "n": s.n,
            }
            for s in stats_rows
        ]
    )
    return Scorer(bundle, stats)


async def load_active() -> Scorer | None:
    global _active
    try:
        async with session_scope() as session:
            _active = await _load(session)
    except Exception:  # noqa: BLE001 - the API still starts; scoring reports unavailable
        log.exception("scorer_load_failed")
        _active = None
    if _active:
        log.info("scorer_loaded", version=_active.version)
    return _active


def get_scorer() -> Scorer | None:
    return _active


async def ensure_scorer() -> Scorer | None:
    return _active or await load_active()


async def score_claims(
    session: AsyncSession, claim_ids: list[str], explain: bool = True, persist: bool = True
) -> list[ScoreResult]:
    scorer = await ensure_scorer()
    if scorer is None:
        return []
    df = await features_for_claims(session, claim_ids)
    results = scorer.score_frame(df, explain=explain)
    if persist:
        for r in results:
            await session.merge(
                AnomalyScore(
                    claim_id=r.claim_id,
                    model_version=r.model_version,
                    risk=r.risk,
                    tier=r.tier,
                    p_z=r.p_z,
                    p_if=r.p_if,
                    max_rz=r.max_rz,
                    feature_z=r.feature_z,
                    shap=r.shap,
                    reasons=r.reasons,
                )
            )
        await session.flush()
    return results


async def score(session: AsyncSession, claim_id: str) -> ScoreResult | None:
    results = await score_claims(session, [claim_id])
    return results[0] if results else None
