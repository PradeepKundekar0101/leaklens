"""Ground-truth evaluation. Lives outside app/ on purpose: detection code must never read ground_truth."""

import io
import time
from collections import defaultdict

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select, text, update

from app.core.config import get_settings
from app.db.models import ModelRegistry, PeerStat
from app.db.session import session_scope
from app.services.anomaly.features import load_features
from app.services.anomaly.scorer import Scorer
from app.services.rules.engine import run_rules
from app.services.rules.loader import load_contexts
from app.storage import spaces

RULE_SCENARIOS = {
    "room_rent_above_cap": {"R01"},
    "non_payable_billed": {"R05"},
    "item_above_mrp": {"R04"},
    "above_tariff": {"R03"},
    "exact_duplicate": {"R08"},
    "service_date_outside_stay": {"R09"},
    "reused_document": {"R11"},
}
ANOMALY_SCENARIOS = [
    "inflated_pharmacy",
    "stretched_stay",
    "preauth_escalation",
    "early_claim",
    "combination",
    "overbilling_provider",
]


async def ground_truth(split: str = "test") -> pd.DataFrame:
    async with session_scope() as s:
        rows = await s.execute(
            text(
                "SELECT g.claim_id, g.scenario, g.leakage_amount FROM ground_truth g "
                "JOIN claims c ON c.id = g.claim_id WHERE c.split = :split"
            ),
            {"split": split},
        )
        return pd.DataFrame(rows.mappings().all(), columns=["claim_id", "scenario", "leakage_amount"])


async def evaluate_rules(split: str = "test") -> dict:
    gt = await ground_truth(split)
    async with session_scope() as s:
        ids = list(
            (await s.execute(text("SELECT id FROM claims WHERE split = :s ORDER BY id"), {"s": split})).scalars()
        )
        t0 = time.monotonic()
        contexts = await load_contexts(s, ids)
        t_load = time.monotonic() - t0
    t1 = time.monotonic()
    outputs = {cid: run_rules(ctx) for cid, ctx in contexts.items()}
    t_rules = time.monotonic() - t1
    codes = {cid: {f.rule_code for f in out.findings} for cid, out in outputs.items()}
    planted = set(gt["claim_id"])
    per_scenario = {}
    for scenario, expected in RULE_SCENARIOS.items():
        claims = gt.loc[gt["scenario"] == scenario, "claim_id"].tolist()
        caught = sum(1 for c in claims if codes.get(c, set()) & expected)
        per_scenario[scenario] = {
            "n": len(claims),
            "caught": caught,
            "recall": round(caught / len(claims), 4) if claims else None,
        }
    clean = [c for c in ids if c not in planted]
    false_pos = [c for c in clean if codes.get(c)]
    fp_codes: dict[str, int] = defaultdict(int)
    for c in false_pos:
        for code in codes[c]:
            fp_codes[code] += 1
    total_rule = sum(v["n"] for v in per_scenario.values())
    total_caught = sum(v["caught"] for v in per_scenario.values())
    return {
        "split": split,
        "n_claims": len(ids),
        "per_scenario": per_scenario,
        "rule_recall": round(total_caught / total_rule, 4) if total_rule else None,
        "clean_claims": len(clean),
        "clean_with_findings": len(false_pos),
        "clean_precision": round(1 - len(false_pos) / len(clean), 4) if clean else None,
        "false_positive_codes": dict(fp_codes),
        "seconds_load": round(t_load, 2),
        "seconds_rules": round(t_rules, 2),
    }


async def load_scorer(version: str) -> Scorer:
    async with session_scope() as s:
        reg = (
            await s.execute(
                select(ModelRegistry).where(ModelRegistry.version == version, ModelRegistry.kind == "iforest")
            )
        ).scalar_one()
        bundle = joblib.load(io.BytesIO(spaces.download(reg.storage_key)))
        stats = pd.DataFrame(
            [
                {
                    "feature": p.feature,
                    "level": p.level,
                    "procedure_code": p.procedure_code,
                    "hospital_tier": p.hospital_tier,
                    "city_tier": p.city_tier,
                    "median": float(p.median),
                    "mad": float(p.mad),
                    "mean_ad": float(p.mean_ad),
                    "n": p.n,
                }
                for p in (await s.execute(select(PeerStat).where(PeerStat.version == version))).scalars()
            ]
        )
    return Scorer(bundle, stats)


FLAG_SHARE = 0.10  # every method flags the same share of claims, so recall is compared at equal review effort


def _method_metrics(scores: pd.Series, positives: set[str], gt: pd.DataFrame, budget: int) -> dict:
    ranked = scores.sort_values(ascending=False, kind="stable")
    flagged = set(ranked.index[:budget])
    out = {"flagged": len(flagged)}
    for k in (50, 100):
        top = list(ranked.index[:k])
        out[f"precision_at_{k}"] = round(sum(1 for c in top if c in positives) / k, 4)
    recall = {}
    for scenario in ANOMALY_SCENARIOS + list(RULE_SCENARIOS):
        claims = set(gt.loc[gt["scenario"] == scenario, "claim_id"])
        if claims:
            recall[scenario] = round(len(claims & flagged) / len(claims), 4)
    out["recall"] = recall
    return out


async def evaluate_anomaly(version: str | None = None, split: str = "test", persist: bool = True) -> dict:
    settings = get_settings()
    async with session_scope() as s:
        if version is None:
            version = (
                await s.execute(
                    select(ModelRegistry.version).where(ModelRegistry.kind == "iforest", ModelRegistry.active.is_(True))
                )
            ).scalar_one()
        df = await load_features(s, "c.split = :split", {"split": split})
    scorer = await load_scorer(version)
    results = scorer.score_frame(df, explain=False)
    frame = pd.DataFrame(
        [
            {"claim_id": r.claim_id, "z": r.p_z, "if": r.p_if, "combined": r.risk, "provider_id": pid}
            for r, pid in zip(results, df["provider_id"], strict=True)
        ]
    ).set_index("claim_id")
    gt = await ground_truth(split)
    positives = set(gt["claim_id"])
    budget = max(1, round(len(frame) * FLAG_SHARE))
    metrics = {
        "version": version,
        "split": split,
        "flag_share": FLAG_SHARE,
        "flag_budget": budget,
        "tier_thresholds": {"high": settings.tier_high, "medium": settings.tier_medium},
        "n_claims": len(frame),
        "n_positive": len(positives & set(frame.index)),
        "z_only": _method_metrics(frame["z"], positives, gt, budget),
        "iforest_only": _method_metrics(frame["if"], positives, gt, budget),
        "combined": _method_metrics(frame["combined"], positives, gt, budget),
    }
    over = set(gt.loc[gt["scenario"] == "overbilling_provider", "claim_id"])
    over_providers = set(frame.loc[frame.index.isin(over), "provider_id"])
    top100 = frame.sort_values("combined", ascending=False, kind="stable").head(100)
    share_top = float(top100["provider_id"].isin(over_providers).mean())
    share_all = float(frame["provider_id"].isin(over_providers).mean()) if len(frame) else 0.0
    metrics["overbilling_providers"] = {
        "providers": sorted(over_providers),
        "share_of_top100": round(share_top, 4),
        "share_of_all": round(share_all, 4),
        "lift": round(share_top / share_all, 2) if share_all else None,
    }
    if persist:
        async with session_scope() as s:
            regs = (await s.execute(select(ModelRegistry).where(ModelRegistry.version == version))).scalars()
            for reg in regs:
                await s.execute(
                    update(ModelRegistry)
                    .where(ModelRegistry.version == reg.version, ModelRegistry.kind == reg.kind)
                    .values(metrics={**(reg.metrics or {}), **metrics})
                )
            await s.commit()
    return metrics


def print_table(metrics: dict) -> None:
    methods = [("z-only", "z_only"), ("IF-only", "iforest_only"), ("combined", "combined")]
    scenarios = sorted({s for _, k in methods for s in metrics[k]["recall"]})
    print(
        f"\nAnomaly evaluation - model {metrics['version']} on split={metrics['split']} "
        f"({metrics['n_claims']} claims, {metrics['n_positive']} planted); each method flags its top "
        f"{metrics['flag_share']:.0%} ({metrics['flag_budget']} claims)"
    )
    print(f"{'scenario':30s}" + "".join(f"{name:>12s}" for name, _ in methods))
    for s in scenarios:
        print(f"{s:30s}" + "".join(f"{metrics[k]['recall'].get(s, float('nan')):>12.2%}" for _, k in methods))
    for p in ("precision_at_50", "precision_at_100"):
        print(f"{p:30s}" + "".join(f"{metrics[k][p]:>12.2%}" for _, k in methods))
    ob = metrics["overbilling_providers"]
    print(
        f"over-billing providers {ob['providers']}: {ob['share_of_top100']:.0%} of top-100 vs "
        f"{ob['share_of_all']:.0%} of all claims (lift {ob['lift']})"
    )


def np_safe(x):
    return x.item() if isinstance(x, np.generic) else x
