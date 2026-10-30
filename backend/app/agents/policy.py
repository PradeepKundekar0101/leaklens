"""Action policy - decided in code, never by the LLM.

| Rule findings              | Risk tier                                 | Action                  |
| None                       | Low                                       | approve                 |
| Deductions only            | Low or medium                             | approve_with_deductions |
| None                       | High                                      | investigate             |
| Any                        | High, or duplicate / waiting-period       | refer_siu               |
| Extraction or required documents missing | Any                         | query                   |

Not covered by the table: no findings and medium risk -> investigate (unexplained unusualness gets a closer look;
the investigator agent itself still runs only for high risk).
A reused document (R11) is treated like a duplicate -> refer_siu.
"""

from decimal import Decimal

SIU_RULES = frozenset({"R06", "R08", "R11"})
ACTIONS = ("approve", "approve_with_deductions", "investigate", "refer_siu", "query", "reject")


def decide_action(
    rule_codes: list[str], deduction_total: Decimal, tier: str | None, documents_missing: bool = False
) -> str:
    if documents_missing:
        return "query"
    codes = set(rule_codes)
    if codes & SIU_RULES:
        return "refer_siu"
    has_findings = bool(codes)
    if tier == "high":
        return "refer_siu" if has_findings else "investigate"
    if has_findings and deduction_total > 0:
        return "approve_with_deductions"
    if tier == "medium":
        return "investigate"
    return "approve"


def confidence_for(action: str, tier: str | None, risk: float | None, coverage_needs_review: int) -> float:
    """Calibrated-looking but simple: deterministic evidence is high-confidence, anomaly-only is lower."""
    base = {"approve": 0.9, "approve_with_deductions": 0.92, "refer_siu": 0.85, "investigate": 0.7, "query": 0.6}.get(
        action, 0.7
    )
    if action == "approve" and risk is not None:
        base -= max(0.0, risk - 0.8) * 0.5  # medium-risk approvals are less certain
    base -= min(0.2, 0.03 * coverage_needs_review)
    return round(max(0.3, min(0.99, base)), 3)
