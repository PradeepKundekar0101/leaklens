"""Train peer statistics + Isolation Forest on split=train, register and activate, then evaluate on split=test."""

import asyncio
import json

from app.db.session import dispose_engine, session_scope
from app.services.anomaly.iforest import train_and_register
from evaluation.metrics import evaluate_anomaly, print_table


async def main() -> None:
    async with session_scope() as session:
        trained, seconds = await train_and_register(session, activate=True)
        await session.commit()
    print(f"trained {trained.version} on {trained.n_train} claims in {seconds:.1f}s")
    metrics = await evaluate_anomaly(trained.version)
    print_table(metrics)
    print(json.dumps({"version": trained.version, "train_seconds": round(seconds, 2)}))
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
