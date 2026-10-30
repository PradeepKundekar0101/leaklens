"""App factory, routers and lifespan (job worker, LangGraph checkpointer and store)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.db.session import dispose_engine


def _api_router() -> APIRouter:
    from app.api import (
        admin,
        auth,
        claims,
        copilot,
        dashboard,
        jobs,
        lookups,
        policies,
        providers,
    )
    from app.api import audit as audit_api

    api = APIRouter(prefix="/api/v1")
    for module in (auth, jobs, lookups, claims, copilot, dashboard, providers, policies, admin, audit_api):
        api.include_router(module.router)
    return api


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    import app.jobs.handlers  # noqa: F401 - registers job handlers
    from app.agents import runtime
    from app.jobs.runner import Worker
    from app.services.anomaly import scorer

    await runtime.startup()
    await scorer.load_active()
    worker = Worker() if settings.run_worker else None
    if worker:
        await worker.start()
    try:
        yield
    finally:
        if worker:
            await worker.stop()
        await runtime.shutdown()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(json=settings.app_env != "local")
    app = FastAPI(title="LeakLens API", version=settings.app_version, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from app.api import health

    app.include_router(health.router)
    app.include_router(_api_router())
    return app


app = create_app()
