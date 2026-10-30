"""Registered job handlers."""

from sqlalchemy import select

from app.core import audit
from app.db.models import Claim
from app.db.session import session_scope
from app.jobs.runner import handler


@handler("noop")
async def noop(payload: dict) -> dict:
    return {"echo": payload}


@handler("process_claim")
async def process_claim(payload: dict) -> dict:
    from app.services.processing import process_claim as run

    return await run(payload["claim_id"])


@handler("process_batch")
async def process_batch(payload: dict) -> dict:
    from app.services.processing import process_many

    split = payload.get("split", "test")
    limit = int(payload.get("limit", 100))
    async with session_scope() as session:
        q = select(Claim.id).where(Claim.split == split)
        if payload.get("only_unprocessed", True):
            q = q.where(Claim.status == "received")
        ids = list((await session.execute(q.order_by(Claim.id).limit(limit))).scalars())
    return await process_many(ids, concurrency=int(payload.get("concurrency", 5)))


@handler("parse_document")
async def parse_document(payload: dict) -> dict:
    from app.services.documents.pipeline import process_document

    return await process_document(int(payload["document_id"]))


@handler("retrain")
async def retrain(payload: dict) -> dict:
    """Train a new version; activate it only if precision@100 is not worse than the active version."""
    from sqlalchemy import select as sel

    from app.db.models import ModelRegistry
    from app.services.anomaly import scorer
    from app.services.anomaly.iforest import activate_version, train_and_register
    from evaluation.metrics import evaluate_anomaly

    async with session_scope() as session:
        active = (
            await session.execute(
                sel(ModelRegistry).where(ModelRegistry.kind == "iforest", ModelRegistry.active.is_(True))
            )
        ).scalar_one_or_none()
        trained, seconds = await train_and_register(session, activate=False)
        await session.commit()
    metrics = await evaluate_anomaly(trained.version)
    new_p100 = metrics["combined"]["precision_at_100"]
    old_p100 = ((active.metrics or {}).get("combined") or {}).get("precision_at_100") if active else None
    activated = old_p100 is None or new_p100 >= old_p100
    async with session_scope() as session:
        if activated:
            await activate_version(session, trained.version)
        await audit.log(
            session,
            ("user", str(payload.get("user_id", "system"))),
            "retrain",
            "model",
            trained.version,
            {
                "precision_at_100": new_p100,
                "previous": old_p100,
                "activated": activated,
                "train_seconds": round(seconds, 2),
            },
        )
        await session.commit()
    if activated:
        await scorer.load_active()
    return {
        "version": trained.version,
        "activated": activated,
        "precision_at_100": new_p100,
        "previous_precision_at_100": old_p100,
    }


@handler("ingest_policy")
async def ingest_policy(payload: dict) -> dict:
    from app.services.policy import params as policy_params
    from app.services.policy.ingest import ingest_product

    product_id = payload["product_id"]
    async with session_scope() as session:
        result = await ingest_product(session, product_id)
        await audit.log(
            session, ("user", str(payload.get("user_id", "system"))), "policy_ingested", "policy", product_id, result
        )
        await session.commit()
    async with session_scope() as session:
        try:
            extraction = await policy_params.extract(session, product_id)
        except ValueError as exc:
            extraction = {"ok": False, "error": str(exc)}
        await session.commit()
    return {**result, "params_extraction": {k: v for k, v in extraction.items() if k != "diff"}}


@handler("provider_stats")
async def provider_stats(payload: dict) -> dict:
    from app.services.portfolio import refresh_provider_stats

    async with session_scope() as session:
        n = await refresh_provider_stats(session)
        await session.commit()
    return {"rows": n}
