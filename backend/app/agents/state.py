import operator
from typing import Annotated, Literal, TypedDict


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class ClaimState(TypedDict, total=False):
    claim_id: str
    run_id: str
    use_llm: bool  # False = deterministic only (rules, anomaly, templated explanation); used for bulk batches
    claim: dict  # claim row + member policy + provider
    documents: list[dict]
    line_items: list[dict]
    policy_params: dict
    coverage: Annotated[list[dict], operator.add]  # merged from fan-out
    rules: dict  # findings + PayableResult
    anomaly: dict  # AnomalyScore
    route: Literal["standard", "investigate"]
    investigation: dict | None
    recommendation: dict
    review: dict | None
    errors: Annotated[list[str], operator.add]
    versions: Annotated[dict, merge_dicts]  # rules, peer_stats, iforest, prompts, models


class CoverageTask(TypedDict):
    claim_id: str
    run_id: str
    product_id: str
    group: list[dict]
