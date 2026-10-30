"""LangGraph runtime: checkpointer + store on DATABASE_URL_DIRECT, created in the app lifespan.

The direct (not pooled) URL is required: LangGraph uses prepared statements and session features that DO's
PgBouncer transaction pool cannot provide. Connections use autocommit=True and row_factory=dict_row.
"""

from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.policy.embed import store_embed

log = get_logger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_store: AsyncPostgresStore | None = None
_graph: Any = None


async def startup() -> None:
    global _pool, _checkpointer, _store, _graph
    if _graph is not None:
        return
    settings = get_settings()
    _pool = AsyncConnectionPool(
        conninfo=settings.direct_url,
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    _store = AsyncPostgresStore(_pool, index={"dims": settings.embed_dims, "embed": store_embed, "fields": ["text"]})
    await _store.setup()
    from app.agents.graph import build_graph

    _graph = build_graph().compile(checkpointer=_checkpointer, store=_store)
    log.info("langgraph_ready")


async def shutdown() -> None:
    global _pool, _checkpointer, _store, _graph
    if _pool is not None:
        await _pool.close()
    _pool = _checkpointer = _store = _graph = None


def graph() -> Any:
    if _graph is None:
        raise RuntimeError("LangGraph runtime not started")
    return _graph


def store() -> AsyncPostgresStore:
    if _store is None:
        raise RuntimeError("LangGraph runtime not started")
    return _store


def checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph runtime not started")
    return _checkpointer


def thread_config(claim_id: str, **tags: Any) -> dict:
    return {
        "configurable": {"thread_id": f"claim:{claim_id}"},
        "tags": [f"claim:{claim_id}", *(f"{k}:{v}" for k, v in tags.items())],
        "metadata": {"claim_id": claim_id, **tags},
        "run_name": f"process_claim {claim_id}",
    }
