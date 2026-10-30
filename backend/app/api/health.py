import asyncio
from importlib.metadata import version
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import require_role
from app.db.session import get_session
from app.services.llm import client as llm
from app.storage.spaces import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> JSONResponse:
    settings = get_settings()
    checks: dict[str, dict] = {}
    try:
        server_version = (await session.execute(text("SELECT 1, current_setting('server_version')"))).one()[1]
        checks["database"] = {"ok": True, "server_version": server_version}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"ok": False, "error": type(exc).__name__}
    try:
        await asyncio.to_thread(get_storage().head_bucket)
        checks["storage"] = {"ok": True, "backend": settings.storage_backend}
    except Exception as exc:  # noqa: BLE001
        checks["storage"] = {"ok": False, "backend": settings.storage_backend, "error": type(exc).__name__}
    ok = all(c["ok"] for c in checks.values())
    body = {
        "status": "ok" if ok else "degraded",
        "env": settings.app_env,
        "checks": checks,
        "versions": {
            "app": settings.app_version,
            "fastapi": version("fastapi"),
            "langgraph": version("langgraph"),
            "model_reasoning": settings.model_reasoning,
            "model_fast": settings.model_fast,
            "llm_enabled": settings.llm_enabled,
            "embeddings_enabled": settings.embeddings_enabled,
        },
    }
    return JSONResponse(body, status_code=200 if ok else 503)


@router.get("/health/llm", dependencies=[Depends(require_role("admin", "manager"))])
async def health_llm() -> dict:
    """Pings the fast model. Manual use only."""
    return await llm.ping()
