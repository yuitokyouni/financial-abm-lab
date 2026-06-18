"""Ignition gate — freeze the rule that no external-submission infra is built
before P1 GO (or publishable PARTIAL) + one diagnostic case (spec 002 §11, task 6).

This is the rule "frozen in code": any function that would stand up external
submission infrastructure (submission templates, public review, leaderboard UI,
public releases) must call ``require_ignition`` first. Until the gate opens it
raises ``IgnitionLocked``, so the discipline cannot be bypassed by accident — the
arena's worst failure mode is a published-but-empty bench before a diagnostic
result exists (spec 002 §11, anti-pattern §12).

"Diagnostic case" is the outward-facing name; internally it is the "scalp"
(a surprising separation/equivalence, or a documented failure of a known model
under the contract). Externally it must be framed as a diagnostic result, never as
"taking down" a model (spec 002 §11 naming note).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Features that are forbidden before ignition (spec 002 §11).
GATED_FEATURES = (
    "external_submission_templates",
    "public_issue_based_review",
    "contributor_documentation",
    "leaderboard_or_profile_browser_ui",
    "versioned_public_releases",
)


class IgnitionLocked(Exception):
    """Raised when a gated feature is invoked before the ignition gate opens."""


@dataclass(frozen=True, slots=True)
class IgnitionState:
    """Current state of the three ignition conditions (spec 002 §11)."""

    p1_status: str = "not_started"  # "GO" | "PARTIAL_PUBLISHABLE" unlock; others do not
    diagnostic_case_present: bool = False
    canonical_rows: int = 0
    min_rows: int = 8

    def p1_unlocks(self) -> bool:
        return self.p1_status in {"GO", "PARTIAL_PUBLISHABLE"}

    def reasons_locked(self) -> list[str]:
        reasons: list[str] = []
        if not self.p1_unlocks():
            reasons.append(f"P1 status={self.p1_status!r} (need GO or PARTIAL_PUBLISHABLE)")
        if not self.diagnostic_case_present:
            reasons.append("no diagnostic case (surprising separation/equivalence/failure)")
        if self.canonical_rows < self.min_rows:
            reasons.append(f"only {self.canonical_rows} canonical rows (need ≥{self.min_rows})")
        return reasons


def ignition_unlocked(state: IgnitionState) -> bool:
    """True iff all three spec 002 §11 ignition conditions hold."""
    return not state.reasons_locked()


#: The frozen default: locked. P1 has not reached GO and no diagnostic case exists.
DEFAULT_STATE = IgnitionState()


def require_ignition(feature: str, state: IgnitionState = DEFAULT_STATE) -> None:
    """Guard a gated feature. Raises ``IgnitionLocked`` until the gate opens.

    Call this at the top of any code path that builds external-submission infra.
    """
    if feature not in GATED_FEATURES:
        raise ValueError(f"{feature!r} is not a gated feature; gated: {GATED_FEATURES}")
    if not ignition_unlocked(state):
        raise IgnitionLocked(
            f"feature {feature!r} is locked until ignition. Blocking: "
            + "; ".join(state.reasons_locked())
        )
