"""Restore the demo database to a known state (< 1 minute once data is generated):

1. Reset every analysis result and claim status (keeps reference data, claims, documents, models, policies).
2. Process the five hero claims end to end so the demo opens with them waiting for review.
3. Queue a background batch for the rest of the test split (run by the API's job worker).

Hero claims (picked deterministically from the test split by their characteristics, never from ground_truth):
  clean fast-track approval; rule deductions with clause citations; anomaly-only investigation;
  reused document or duplicate; a claim from the highest observed/expected provider.
"""

import asyncio
import json
import time

from sqlalchemy import text

from app.agents import runtime
from app.db.session import dispose_engine, session_scope
from app.jobs.runner import enqueue
from app.services import processing
from app.services.anomaly import scorer
from app.services.portfolio import refresh_provider_stats
from app.services.rules.engine import run_rules
from app.services.rules.loader import load_contexts

RESET_SQL = [
    "TRUNCATE rule_findings, coverage_findings, anomaly_scores, recommendations, investigations, reviews "
    "RESTART IDENTITY",
    "DELETE FROM jobs",
    "DELETE FROM claims WHERE split = 'live'",
    "UPDATE claims SET status = 'received' WHERE status <> 'received'",
    "UPDATE claim_documents SET parse_status = 'pending' WHERE parse_status <> 'pending' AND claim_id IN "
    "(SELECT id FROM claims WHERE NOT EXISTS (SELECT 1 FROM line_items l WHERE l.claim_id = claims.id))",
    "DELETE FROM audit_log WHERE entity = 'claim'",
    "DELETE FROM checkpoint_writes",
    "DELETE FROM checkpoint_blobs",
    "DELETE FROM checkpoints",
    "DELETE FROM store WHERE prefix LIKE 'copilot%' OR prefix LIKE 'cases%'",
]


async def pick_heroes() -> dict[str, str]:
    async with session_scope() as s:
        ids = list(
            (await s.execute(text("SELECT id FROM claims WHERE split = 'test' ORDER BY id LIMIT 1500"))).scalars()
        )
        contexts = await load_contexts(s, ids)
        frame = await scorer.ensure_scorer()
        from app.services.anomaly.features import features_for_claims

        feats = await features_for_claims(s, ids)
    scores = {r.claim_id: r for r in frame.score_frame(feats, explain=False)} if frame else {}
    rules = {cid: {f.rule_code for f in run_rules(ctx).findings} for cid, ctx in contexts.items()}
    heroes: dict[str, str] = {}
    for cid in ids:
        sc, codes = scores.get(cid), rules.get(cid, set())
        if sc is None:
            continue
        if "clean_approval" not in heroes and not codes and sc.risk < 0.5:
            heroes["clean_approval"] = cid
        if "rule_deductions" not in heroes and codes & {"R01", "R05"} and len(codes) >= 1 and sc.tier == "low":
            heroes["rule_deductions"] = cid
        if "anomaly_investigation" not in heroes and not codes and sc.tier == "high":
            heroes["anomaly_investigation"] = cid
        if "duplicate_or_reused" not in heroes and codes & {"R08", "R11"}:
            heroes["duplicate_or_reused"] = cid
    async with session_scope() as s:
        top = (
            await s.execute(
                text(
                    "SELECT provider_id FROM provider_stats GROUP BY provider_id "
                    "ORDER BY sum(claimed_total) / NULLIF(sum(claimed_total / NULLIF(oe_index, 0)), 0) DESC LIMIT 1"
                )
            )
        ).scalar_one_or_none()
    if top:
        for cid in ids:
            ctx = contexts.get(cid)
            if ctx and ctx.provider_id == top and cid not in heroes.values() and not rules.get(cid):
                heroes["overbilling_provider"] = cid
                break
    return heroes


async def main() -> None:
    t0 = time.monotonic()
    async with session_scope() as s:
        for sql in RESET_SQL:
            try:
                async with s.begin_nested():
                    await s.execute(text(sql))
            except Exception as exc:  # noqa: BLE001 - LangGraph tables may not exist before first start
                print(f"skip: {sql[:50]}... ({type(exc).__name__})")
        await refresh_provider_stats(s)
        await s.commit()
    await runtime.startup()
    await scorer.load_active()
    heroes = await pick_heroes()
    results = [await processing.process_claim(cid) for cid in heroes.values()]  # sequential: small DB, rate limits
    async with session_scope() as s:
        await refresh_provider_stats(s)
        # The rest of the test split is processed in the background by the API's job worker (about 2 minutes),
        # followed by a provider-stats refresh, so the dashboard fills while the demo starts on the hero claims.
        await enqueue(
            s,
            "process_batch",
            {"split": "test", "limit": 5000, "concurrency": 8, "only_unprocessed": True, "use_llm": False},
        )
        await enqueue(s, "provider_stats", {})
        await s.commit()
    print(
        json.dumps(
            {
                name: {"claim_id": cid, "action": r["action"], "payable": r["payable"], "leakage": r["leakage"]}
                for (name, cid), r in zip(heroes.items(), results, strict=True)
            },
            indent=2,
        )
    )
    print(f"demo reset in {time.monotonic() - t0:.1f}s")
    await runtime.shutdown()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
