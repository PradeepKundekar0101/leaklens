"""Detection evaluation on split=test against ground_truth: rules recall/precision and anomaly comparison table."""

import argparse
import asyncio

from app.db.session import dispose_engine
from evaluation.metrics import evaluate_anomaly, evaluate_rules, print_table


async def main(version: str | None, split: str) -> None:
    rules = await evaluate_rules(split)
    print(
        f"\nRules on split={split}: {rules['n_claims']} claims, rules ran in {rules['seconds_rules']}s "
        f"(+{rules['seconds_load']}s loading)"
    )
    for scenario, r in rules["per_scenario"].items():
        recall = f"{r['recall']:.2%}" if r["recall"] is not None else "n/a"
        print(f"  {scenario:30s} {r['caught']:>5d}/{r['n']:<5d} recall {recall}")
    print(
        f"  overall rule recall {rules['rule_recall']:.2%}; clean claims with findings "
        f"{rules['clean_with_findings']}/{rules['clean_claims']} (precision {rules['clean_precision']:.2%}) "
        f"{rules['false_positive_codes'] or ''}"
    )
    metrics = await evaluate_anomaly(version, split)
    print_table(metrics)
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    asyncio.run(main(args.version, args.split))
