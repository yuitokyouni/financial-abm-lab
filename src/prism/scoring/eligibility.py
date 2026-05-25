"""Static eligibility gate — baseline realism check.

Before trusting a model's intervention response, verify that its
baseline (pre-intervention) simulation reproduces known stylized
facts within empirical ranges.  An ineligible model is one that
cannot even get the baseline right, so its intervention-response
scoring is unreliable.

Empirical ranges are sourced from canonical surveys:
  - volatility_clustering (α + β): [0.5, 0.999]  (Cont 2001)
  - leverage_effect (Corr(r, r²₊₁)): [-0.5, 0.0]  (Black 1976)
  - gain_loss_asymmetry (skewness): [-3.0, 0.5]  (broad equity range)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from prism.types import FactResult


class EligibilityVerdict(Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNTESTED = "untested"


@dataclass(frozen=True)
class FactRange:
    fact_id: str
    lo: float
    hi: float


EMPIRICAL_RANGES: dict[str, FactRange] = {
    "volatility_clustering": FactRange("volatility_clustering", 0.5, 0.999),
    "leverage_effect": FactRange("leverage_effect", -0.5, 0.0),
    "gain_loss_asymmetry": FactRange("gain_loss_asymmetry", -3.0, 0.5),
    "fat_tails": FactRange("fat_tails", 1.0, 50.0),
    "abs_autocorrelation": FactRange("abs_autocorrelation", 0.05, 0.5),
}


@dataclass(frozen=True)
class FactEligibility:
    fact_id: str
    value: float
    expected_range: tuple[float, float]
    in_range: bool


@dataclass(frozen=True)
class EligibilityResult:
    model_id: str
    verdict: EligibilityVerdict
    checks: list[FactEligibility]
    n_pass: int
    n_fail: int

    def summary(self) -> str:
        lines = [f"Eligibility: {self.model_id} — {self.verdict.value}"]
        for c in self.checks:
            status = "PASS" if c.in_range else "FAIL"
            lines.append(
                f"  {c.fact_id:30s} value={c.value:+.6f}  "
                f"range=[{c.expected_range[0]:.3f}, {c.expected_range[1]:.3f}]  "
                f"{status}"
            )
        return "\n".join(lines)


def check_fact_in_range(
    fact: FactResult,
    ranges: dict[str, FactRange] | None = None,
) -> FactEligibility | None:
    """Check one fact against its empirical range."""
    if ranges is None:
        ranges = EMPIRICAL_RANGES
    if fact.fact_id not in ranges:
        return None
    r = ranges[fact.fact_id]
    if np.isnan(fact.value):
        return FactEligibility(
            fact_id=fact.fact_id,
            value=float("nan"),
            expected_range=(r.lo, r.hi),
            in_range=False,
        )
    return FactEligibility(
        fact_id=fact.fact_id,
        value=fact.value,
        expected_range=(r.lo, r.hi),
        in_range=r.lo <= fact.value <= r.hi,
    )


def check_eligibility(
    model_id: str,
    baseline_facts: list[FactResult],
    ranges: dict[str, FactRange] | None = None,
) -> EligibilityResult:
    """Run static eligibility gate on a set of baseline facts."""
    checks = []
    for fact in baseline_facts:
        result = check_fact_in_range(fact, ranges)
        if result is not None:
            checks.append(result)

    if not checks:
        return EligibilityResult(
            model_id=model_id,
            verdict=EligibilityVerdict.UNTESTED,
            checks=[],
            n_pass=0,
            n_fail=0,
        )

    n_pass = sum(1 for c in checks if c.in_range)
    n_fail = len(checks) - n_pass
    verdict = EligibilityVerdict.ELIGIBLE if n_fail == 0 else EligibilityVerdict.INELIGIBLE

    return EligibilityResult(
        model_id=model_id,
        verdict=verdict,
        checks=checks,
        n_pass=n_pass,
        n_fail=n_fail,
    )
