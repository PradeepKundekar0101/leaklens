"""Generate the synthetic LeakLens portfolio (Phase 1).

    cd backend && uv run python -m scripts.generate_data [--seed 42] [--n-train 30000] [--n-test 3000] [--out DIR]

Writes one CSV per table (providers, tariffs, agents, members, policy_products, policy_params, member_policies,
claims, line_items, ground_truth) plus sample claim documents under {out}/documents/ and a documents manifest.
Same seed => byte-identical output.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.datagen.claims import ANOMALY_SCENARIOS, RULE_SCENARIOS, World, generate_claims
from scripts.datagen.common import DEFAULT_OUT, fmt_paise, load_products, load_reference
from scripts.datagen.entities import make_agents, make_members, make_policies, make_providers, make_tariffs

POLICY_APPROVED_AT = "2026-01-01 00:00:00+00:00"  # fixed for reproducibility; load_data stamps the real time


def _write(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, lineterminator="\n")


def _bool(series) -> list[str]:
    return ["true" if b else "false" for b in series]


def generate(
    seed: int = 42,
    n_train: int = 30000,
    n_test: int = 3000,
    out: Path = DEFAULT_OUT,
    documents: bool = True,
    quiet: bool = False,
) -> dict:
    t0 = time.perf_counter()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ref = load_reference()
    products = load_products(ref)

    n_members = max(500, round(15000 * (n_train + n_test) / 33000))
    providers = make_providers(rng)
    tariffs = make_tariffs(rng, ref, providers)
    agents = make_agents(rng)
    members = make_members(rng, ref, providers, n_members)
    policies = make_policies(rng, members, agents, products)
    world = World(ref, products, providers, tariffs, members, policies)
    res, _ = generate_claims(rng, world, n_train, n_test)

    # ---- entity CSVs
    p = providers.copy()
    p["nabh"] = _bool(p.nabh)
    p["network"] = _bool(p.network)
    p["joined_at"] = p.joined_at.astype(str)
    _write(p, out / "providers.csv")
    _write(
        pd.DataFrame(
            {
                "provider_id": tariffs.provider_id,
                "procedure_code": tariffs.procedure_code,
                "package_rate": fmt_paise(tariffs.package_paise.to_numpy()),
            }
        ),
        out / "tariffs.csv",
    )
    _write(agents, out / "agents.csv")
    _write(
        pd.DataFrame(
            {
                "id": members.id,
                "name": members.name,
                "age": members.age,
                "gender": members.gender,
                "city": members.city,
                "member_since": policies.start_date.astype(str),
                "declared_conditions": members.declared_conditions,
                "bank_account_hash": members.bank_account_hash,
                "phone_hash": members.phone_hash,
            }
        ),
        out / "members.csv",
    )
    _write(
        pd.DataFrame(
            {
                "id": [pr.id for pr in products],
                "name": [pr.name for pr in products],
                "version": [pr.version for pr in products],
                "wording_key": "",
                "status": "active",
            }
        ),
        out / "policy_products.csv",
    )
    _write(
        pd.DataFrame(
            {
                "product_id": [pr.id for pr in products],
                "room_rent_cap_pct": [pr.room_rent_cap_pct or "" for pr in products],
                "icu_cap_pct": [pr.icu_cap_pct or "" for pr in products],
                "copay_pct": [pr.copay_pct for pr in products],
                "deductible": [pr.deductible for pr in products],
                "sub_limits": [json.dumps(pr.sub_limits, sort_keys=True) for pr in products],
                "waiting_periods": [json.dumps(pr.waiting_periods, sort_keys=True) for pr in products],
                "clause_refs": [json.dumps(pr.clause_refs, sort_keys=True) for pr in products],
                "approved_by": "seed",
                "approved_at": POLICY_APPROVED_AT,
            }
        ),
        out / "policy_params.csv",
    )
    _write(
        pd.DataFrame(
            {
                "id": policies.id,
                "member_id": policies.member_id,
                "product_id": policies.product_id,
                "sum_insured": fmt_paise(policies.si_paise.to_numpy()),
                "balance": fmt_paise(np.maximum(res.balance_paise, 0)),
                "start_date": policies.start_date.astype(str),
                "end_date": policies.end_date.astype(str),
                "agent_id": policies.agent_id,
            }
        ),
        out / "member_policies.csv",
    )
    _write(res.claims, out / "claims.csv")
    _write(res.lines, out / "line_items.csv")
    _write(res.ground_truth[["claim_id", "scenario", "leakage_amount"]], out / "ground_truth.csv")
    t_data = time.perf_counter() - t0

    doc_info: dict = {}
    if documents:
        from scripts.datagen.documents import render_documents

        doc_info = render_documents(rng, world, res, out / "documents")
    elapsed = time.perf_counter() - t0
    report = calibration_report(res)
    report.update(
        {"seconds_data": round(t_data, 2), "seconds_total": round(elapsed, 2), "documents": doc_info, "seed": seed}
    )
    if not quiet:
        print_report(report, res)
    return report


def calibration_report(res) -> dict:
    gt = res.ground_truth
    total = res.report["claims_total_paise"]
    rows = []
    for name, grp in gt.groupby("scenario", sort=False):
        kind = "rule" if name in RULE_SCENARIOS else ("anomaly" if name in ANOMALY_SCENARIOS else "document")
        rows.append((name, kind, len(grp), int(grp.leak_paise.sum())))
    rows.sort(key=lambda r: ("rule", "anomaly", "document").index(r[1]))
    leak = int(gt.leak_paise.sum())
    return {
        "scenarios": rows,
        "claims_total_paise": total,
        "leakage_total_paise": leak,
        "leakage_pct": 100.0 * leak / total if total else 0.0,
        "n_train": res.report["n_train"],
        "n_test": res.report["n_test"],
        "ob_providers": res.ob_providers,
        "ob_share": res.report["ob_share"],
        "dropped": res.report["dropped"],
        "construction_errors": res.report["construction_errors"],
        "unassigned_claims": res.report["unassigned_claims"],
        "tariff_clipped_share": res.report["tariff_clipped_share"],
        "proc_to_tariff": res.report["proc_to_tariff_p50_p90"],
        "reused_pairs": res.reused_pairs,
    }


def _inr(paise: int) -> str:
    return f"{paise / 100:,.2f}"


def print_report(r: dict, res) -> None:
    print("=" * 78)
    print("LeakLens synthetic data - calibration report")
    print("=" * 78)
    print(f"claims: train={r['n_train']:,} test={r['n_test']:,}   total claimed Rs {_inr(r['claims_total_paise'])}")
    print(f"{'scenario':<28}{'type':<10}{'claims':>8}{'leakage (Rs)':>20}{'% claimed':>11}")
    for name, kind, cnt, amt in r["scenarios"]:
        print(f"{name:<28}{kind:<10}{cnt:>8,}{_inr(amt):>20}{100 * amt / r['claims_total_paise']:>10.2f}%")
    print("-" * 78)
    print(f"{'TOTAL planted leakage':<46}{_inr(r['leakage_total_paise']):>20}{r['leakage_pct']:>10.2f}%")
    status = "OK" if 5.0 <= r["leakage_pct"] <= 10.0 else "OUTSIDE 5-10% TARGET"
    print(f"target 5-10% of total claimed: {status}")
    obs = ", ".join(f"{pid} (x{f:.2f})" for pid, f in r["ob_providers"])
    print(f"over-billing providers: {obs}; share of claims {100 * r['ob_share']:.2f}%")
    print(f"dropped while fitting: {r['dropped']}; unassigned skeletons: {r['unassigned_claims']}")
    print(
        f"clean claims with OT+surgeon clipped to tariff: {100 * r['tariff_clipped_share']:.1f}% "
        f"(pre-clip ratio p50/p90 {r['proc_to_tariff']})"
    )
    if r["construction_errors"]:
        print("CONSTRUCTION ERRORS (first 10):")
        for e in r["construction_errors"]:
            print("  ", e)
    d = r.get("documents") or {}
    if d:
        print(f"documents: {d.get('files', 0)} files for {d.get('claims', 0)} claims; canary: {d.get('canary_claim')}")
        print(f"reused bill pairs (original, second claim): {r['reused_pairs']}")
        print(f"unplanted document pairs within pHash distance 5 (look-alikes): {d['unplanted_phash_pairs']}")
    print(f"time: data {r['seconds_data']}s, total {r['seconds_total']}s")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-train", type=int, default=30000)
    ap.add_argument("--n-test", type=int, default=3000)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-documents", action="store_true", help="skip rendering sample PDFs")
    a = ap.parse_args(argv)
    report = generate(a.seed, a.n_train, a.n_test, a.out, documents=not a.no_documents)
    return 1 if report["construction_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
