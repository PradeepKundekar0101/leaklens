"""Running claims through the orchestrator."""

import asyncio
import uuid

from langgraph.types import Command

from app.agents import runtime
from app.core import audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.services.anomaly import scorer
from app.services.claims import set_status
from app.services.rules.engine import RULES_VERSION

log = get_logger(__name__)


async def process_claim(claim_id: str, use_llm: bool = True) -> dict:
    """Run the graph until the human-review interrupt. Re-processing starts a fresh thread."""
    await runtime.checkpointer().adelete_thread(f"claim:{claim_id}")
    run_id = uuid.uuid4().hex
    settings = get_settings()
    active = scorer.get_scorer()
    config = runtime.thread_config(
        claim_id,
        run_id=run_id,
        model_reasoning=settings.model_reasoning,
        model_fast=settings.model_fast,
        anomaly_model=active.version if active else "none",
        rules=RULES_VERSION,
    )
    try:
        state = await runtime.graph().ainvoke({"claim_id": claim_id, "run_id": run_id, "use_llm": use_llm}, config)
    except Exception as exc:
        log.exception("process_claim_failed", claim_id=claim_id)
        async with session_scope() as session:
            await set_status(
                session,
                claim_id,
                "failed",
                audit.agent("orchestrator"),
                {"run_id": run_id, "error": f"{type(exc).__name__}: {exc}"[:500]},
            )
            await session.commit()
        raise
    rec = state.get("recommendation") or {}
    return {
        "claim_id": claim_id,
        "run_id": run_id,
        "action": rec.get("action"),
        "payable": rec.get("payable_amount"),
        "leakage": rec.get("leakage_amount"),
        "errors": state.get("errors", []),
    }


async def resume_review(claim_id: str, review: dict) -> dict:
    config = runtime.thread_config(claim_id)
    state = await runtime.graph().ainvoke(Command(resume=review), config)
    return {"claim_id": claim_id, "review": state.get("review"), "errors": state.get("errors", [])}


async def pending_interrupt(claim_id: str) -> bool:
    snapshot = await runtime.graph().aget_state(runtime.thread_config(claim_id))
    return bool(snapshot and snapshot.next and "human_review" in snapshot.next)


async def process_many(claim_ids: list[str], concurrency: int = 5, use_llm: bool = False) -> dict:
    """Bulk processing defaults to deterministic mode: LLM agents per claim at batch scale are slow and costly."""
    sem = asyncio.Semaphore(concurrency)
    done, failed = 0, 0
    actions: dict[str, int] = {}

    async def one(cid: str) -> None:
        nonlocal done, failed
        async with sem:
            try:
                out = await process_claim(cid, use_llm=use_llm)
                actions[out["action"] or "none"] = actions.get(out["action"] or "none", 0) + 1
                done += 1
            except Exception:  # noqa: BLE001 - recorded on the claim
                failed += 1

    await asyncio.gather(*(one(c) for c in claim_ids))
    return {"processed": done, "failed": failed, "actions": actions}
