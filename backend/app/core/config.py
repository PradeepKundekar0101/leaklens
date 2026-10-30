"""Application settings, read only from environment variables (and an optional .env file)."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "dev", "demo", "test"] = "local"
    app_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://localhost:5432/leaklens"
    database_url_direct: str = ""
    db_pool_mode: Literal["session", "transaction"] = "session"

    storage_backend: Literal["local", "spaces"] = "local"
    local_storage_dir: Path = DATA_DIR / "storage"
    spaces_endpoint: str = "https://blr1.digitaloceanspaces.com"
    spaces_region: str = "blr1"
    spaces_bucket: str = "leaklens"
    spaces_key: str = ""
    spaces_secret: str = ""

    anthropic_api_key: str = ""
    # Explicit, so an ANTHROPIC_BASE_URL inherited from the shell never redirects API traffic.
    anthropic_base_url: str = "https://api.anthropic.com"
    model_reasoning: str = "claude-sonnet-5-5"
    model_fast: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 30.0

    docling_artifacts_path: str = ""  # models baked into the Docker image; empty = download on first use

    voyage_api_key: str = ""
    embed_model: str = "voyage-3.5"
    embed_dims: int = 1024

    langsmith_api_key: str = ""
    langsmith_project: str = "leaklens"
    langsmith_tracing: bool = False

    jwt_secret: str = "change-me-local-only-secret-at-least-32-bytes"
    jwt_expire_minutes: int = 480
    cookie_secure: bool = True

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    job_concurrency: int = 4
    job_poll_interval: float = 0.5
    job_max_attempts: int = 3
    run_worker: bool = True

    risk_weight_z: Decimal = Decimal("0.5")
    risk_weight_if: Decimal = Decimal("0.5")
    tier_high: float = 0.98
    tier_medium: float = 0.90

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def direct_url(self) -> str:
        """Plain libpq URL for LangGraph (direct connection, never through the pool)."""
        url = self.database_url_direct or self.database_url
        return url.replace("postgresql+psycopg://", "postgresql://")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def embeddings_enabled(self) -> bool:
        return bool(self.voyage_api_key)


def export_tracing_env(settings: Settings) -> None:
    """LangSmith and LangGraph read tracing configuration from the process environment."""
    import os

    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    else:
        os.environ["LANGSMITH_TRACING"] = "false"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    export_tracing_env(settings)
    return settings
