"""Rule registry and runner. Each rule is a pure function check(ctx) -> list[RuleFinding]."""

from collections.abc import Callable
from dataclasses import dataclass

from app.services.rules.context import ClaimContext, RuleFinding

RULES_VERSION = "2026.10.1"

Check = Callable[[ClaimContext], list[RuleFinding]]


@dataclass(frozen=True)
class RuleSpec:
    code: str
    description: str
    check: Check
    version: str = RULES_VERSION


REGISTRY: dict[str, RuleSpec] = {}


def rule(code: str, description: str) -> Callable[[Check], Check]:
    def _register(fn: Check) -> Check:
        REGISTRY[code] = RuleSpec(code, description, fn)
        return fn

    return _register


def _load_checks() -> None:
    from app.services.rules.checks import duplicates, items, policy, room  # noqa: F401


@dataclass
class RulesOutput:
    findings: list[RuleFinding]
    payable: "PayableResult"  # noqa: F821
    rules_version: str = RULES_VERSION

    @property
    def full_claim_codes(self) -> list[str]:
        return sorted({f.rule_code for f in self.findings if f.full_claim})


def run_rules(ctx: ClaimContext) -> RulesOutput:
    from app.services.rules.payable import compute_payable

    _load_checks()
    findings: list[RuleFinding] = []
    for code in sorted(REGISTRY):
        findings.extend(REGISTRY[code].check(ctx))
    full = sorted({f.rule_code for f in findings if f.full_claim})
    return RulesOutput(findings=findings, payable=compute_payable(ctx, full_claim_rules=full))
