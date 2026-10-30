"""Training: peer statistics + Isolation Forest, versioned, stored, registered."""

import io
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelRegistry, PeerStat
from app.services.anomaly.features import ALL_FEATURES, load_features
from app.services.anomaly.peer_stats import PeerTable, compute_peer_stats, z_matrix
from app.storage import spaces

RANDOM_STATE = 42


@dataclass
class TrainedModel:
    version: str
    model: IsolationForest
    z_train_sorted: np.ndarray
    if_train_sorted: np.ndarray
    peer_stats: pd.DataFrame
    trained_at: datetime
    n_train: int

    def bundle(self) -> dict:
        return {
            "version": self.version,
            "model": self.model,
            "features": ALL_FEATURES,
            "z_train_sorted": self.z_train_sorted,
            "if_train_sorted": self.if_train_sorted,
            "trained_at": self.trained_at.isoformat(),
            "n_train": self.n_train,
        }


def new_version() -> str:
    return datetime.now(UTC).strftime("v%Y%m%d-%H%M%S")


def fit(train: pd.DataFrame, version: str | None = None) -> TrainedModel:
    stats = compute_peer_stats(train)
    table = PeerTable(stats)
    z_train = z_matrix(table, train)
    model = IsolationForest(n_estimators=200, contamination=0.03, random_state=RANDOM_STATE, n_jobs=-1)
    X = train[ALL_FEATURES].to_numpy(dtype=np.float64)
    model.fit(X)
    if_train = -model.score_samples(X)  # higher = more anomalous
    return TrainedModel(
        version=version or new_version(),
        model=model,
        z_train_sorted=np.sort(z_train),
        if_train_sorted=np.sort(if_train),
        peer_stats=stats,
        trained_at=datetime.now(UTC),
        n_train=len(train),
    )


async def train_and_register(session: AsyncSession, activate: bool = True) -> tuple[TrainedModel, float]:
    started = time.monotonic()
    train = await load_features(session, "c.split = 'train'")
    if train.empty:
        raise RuntimeError("no training claims: run generate + load first")
    trained = fit(train)

    buf = io.BytesIO()
    joblib.dump(trained.bundle(), buf, compress=3)
    key = f"models/{trained.version}/iforest.joblib"
    spaces.upload(key, buf.getvalue(), "application/octet-stream")

    await session.execute(delete(PeerStat).where(PeerStat.version == trained.version))
    rows = trained.peer_stats.replace({np.nan: None}).to_dict("records")
    session.add_all(
        PeerStat(
            version=trained.version,
            feature=r["feature"],
            level=int(r["level"]),
            procedure_code=r["procedure_code"],
            hospital_tier=None if r["hospital_tier"] is None else int(r["hospital_tier"]),
            city_tier=None if r["city_tier"] is None else int(r["city_tier"]),
            median=r["median"],
            mad=r["mad"],
            mean_ad=r["mean_ad"],
            n=int(r["n"]),
        )
        for r in rows
    )
    elapsed = time.monotonic() - started
    metrics = {"n_train": trained.n_train, "train_seconds": round(elapsed, 2)}
    for kind, storage_key in (("iforest", key), ("peer_stats", None)):
        session.add(
            ModelRegistry(
                version=trained.version,
                kind=kind,
                storage_key=storage_key,
                trained_at=trained.trained_at,
                metrics=metrics,
                active=False,
            )
        )
    await session.flush()
    if activate:
        await activate_version(session, trained.version)
    return trained, elapsed


async def activate_version(session: AsyncSession, version: str) -> None:
    await session.execute(update(ModelRegistry).values(active=False))
    await session.execute(update(ModelRegistry).where(ModelRegistry.version == version).values(active=True))
    await session.flush()
