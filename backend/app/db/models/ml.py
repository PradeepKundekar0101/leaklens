"""Models, peer statistics and policy search."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Computed, DateTime, Identity, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Json

EMBED_DIMS = 1024


class PeerStat(Base):
    __tablename__ = "peer_stats"
    __table_args__ = (
        Index("ix_peer_stats_lookup", "version", "feature", "level", "procedure_code", "hospital_tier", "city_tier"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    feature: Mapped[str] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer)
    procedure_code: Mapped[str] = mapped_column(String(32))
    hospital_tier: Mapped[int | None] = mapped_column(Integer)
    city_tier: Mapped[int | None] = mapped_column(Integer)
    median: Mapped[float] = mapped_column(Numeric(16, 6))
    mad: Mapped[float] = mapped_column(Numeric(16, 6))
    mean_ad: Mapped[float] = mapped_column(Numeric(16, 6))
    n: Mapped[int] = mapped_column(Integer)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)  # iforest / peer_stats
    storage_key: Mapped[str | None] = mapped_column(String(255))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[Json]
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        Index(
            "ix_policy_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_policy_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(32), index=True)
    section_path: Mapped[str] = mapped_column(Text)
    clause_no: Mapped[str] = mapped_column(String(32))
    clause_type: Mapped[str] = mapped_column(String(20), default="general")
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(EMBED_DIMS), nullable=True)
    embed_model: Mapped[str | None] = mapped_column(String(64))
    tsv = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(section_path, '') || ' ' || text)", persisted=True),
    )
