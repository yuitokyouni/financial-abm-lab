"""The six scoring-profile axes as artifact schemas (spec 002 §8, task 2).

The MVA uses **profiles, not scalar validity ranks** (spec 002 §1 non-goal). Each
axis is GT-free (computable without any reference to "the real market"). A radar
of these six axes creates an improvement incentive without pretending to rank
validity.

Axes (spec 002 §8):
    1. claim_admissibility      — fraction of declared claims the validator admits
    2. audit_completeness       — how tightly the causal structure is pinned
                                  (``may/must`` gap is a *component*, not the whole)
    3. intervention_coverage    — declared schemes / channels actually exercised
    4. mechanism_separability   — separation from other mechanisms (needs C1)
    5. replication_stability    — seed-cross stability of summary statistics
    6. failure_transparency     — are negatives structured (spec 002 §9)?

Two axes (separability, the ``may/must`` component of audit) are *pending* until a
C1 channel pair / L3 capture exists. They are reported as ``pending`` with a
reason, never as a fabricated number (spec 002 §11 honesty discipline).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: Canonical axis order for the radar.
PROFILE_AXES: tuple[str, ...] = (
    "claim_admissibility",
    "audit_completeness",
    "intervention_coverage",
    "mechanism_separability",
    "replication_stability",
    "failure_transparency",
)

#: Reach claims that carry NO causal content and are always admissible at L2.
_NON_CAUSAL_CLAIMS = frozenset({"reproducibility", "genealogy", "exploration", "reported"})
#: Causal claims that require a sound ``may``/``must`` reach (not available at L2).
_CAUSAL_CLAIMS = frozenset({"invariance", "counterfactual", "causal_path"})


@dataclass(slots=True)
class ClaimAdmissibility:
    """Axis 1. Fraction of declared claims the reach↔claim rule admits.

    At reach=``reported`` (L2), only non-causal claims are admissible; an
    invariance/counterfactual claim from ``reported`` is rejected (the validator
    rule of prov_abm_design_notes §5.3). A model that declares no causal claim is
    trivially fully admissible.
    """

    reach_claim: str
    declared_claims: tuple[str, ...]
    admissible: tuple[str, ...]
    rejected: tuple[str, ...]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def claim_admissibility(reach_claim: str, declared_claims: tuple[str, ...]) -> ClaimAdmissibility:
    admissible: list[str] = []
    rejected: list[str] = []
    for c in declared_claims:
        if c in _NON_CAUSAL_CLAIMS:
            admissible.append(c)
        elif c in _CAUSAL_CLAIMS:
            # Causal claims need sound may/must; reported cannot back them.
            (admissible if reach_claim in {"may", "must", "exact"} else rejected).append(c)
        else:
            rejected.append(c)  # unknown claim type → not admissible
    n = len(declared_claims)
    score = 1.0 if n == 0 else len(admissible) / n
    return ClaimAdmissibility(reach_claim, tuple(declared_claims), tuple(admissible), tuple(rejected), score)


@dataclass(slots=True)
class AuditCompleteness:
    """Axis 2. How auditable/tight the model's provenance + structure is.

    ``may_must_gap`` is a *component* and is ``None`` until L3 capture exists
    (spec 002 §8: it is not the sole objective). The computable part now is L2
    provenance-field completeness + determinism.
    """

    prov_field_completeness: float
    determinism_verified: bool
    may_must_gap: float | None  # None = requires L3 capture (not in scope)
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REQUIRED_PROV_FIELDS = ("uuid", "model", "config_hash", "seed", "output_sha256", "reach_claim")


def audit_completeness(prov: dict[str, Any], *, determinism_verified: bool) -> AuditCompleteness:
    present = sum(1 for f in _REQUIRED_PROV_FIELDS if prov.get(f) not in (None, ""))
    completeness = present / len(_REQUIRED_PROV_FIELDS)
    # Score from the computable components only; gap component left out (None).
    score = 0.5 * completeness + 0.5 * (1.0 if determinism_verified else 0.0)
    return AuditCompleteness(completeness, determinism_verified, None, score)


@dataclass(slots=True)
class InterventionCoverage:
    """Axis 3. Declared B2 schemes actually exercisable on exposed channels.

    Coverage is over *exposed* channels (what the contract surface offers now),
    not declared/semantic channels — so canonical C0 models score 0 honestly.
    """

    n_exposed_channels: int
    n_schemes: int
    n_covered: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def intervention_coverage(n_exposed_channels: int, n_schemes: int = 4) -> InterventionCoverage:
    covered = n_exposed_channels * n_schemes
    possible = max(n_schemes, 1)
    # Normalize against "at least one channel × all schemes" as the unit.
    score = 0.0 if n_exposed_channels == 0 else min(1.0, covered / possible)
    return InterventionCoverage(n_exposed_channels, n_schemes, covered, score)


@dataclass(slots=True)
class MechanismSeparability:
    """Axis 4. Whether intervention response separates this model from others.

    Requires C1 (an exposed channel + intervention response). Until then it is
    ``pending`` with the declared channels that would be wired (spec 002 §11 /
    Finding 0002 order-book channel work).
    """

    status: str  # "pending_c1" | "computed"
    declared_channels: tuple[str, ...]
    separating_dims: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def mechanism_separability_pending(declared_channels: tuple[str, ...]) -> MechanismSeparability:
    return MechanismSeparability(
        status="pending_c1",
        declared_channels=declared_channels,
        reason="no exposed C1 channel yet; intervention-response not computed",
    )


@dataclass(slots=True)
class ReplicationStability:
    """Axis 5. Seed-cross stability of summary statistics (lower CV = more stable)."""

    n_seeds: int
    metric_cv: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FailureTransparency:
    """Axis 6. Are negative/failed results structured (spec 002 §9)?

    A failure entry is admissible only with: contract compliance, a declared
    target claim, a reproducible run bundle, and a failure-taxonomy assignment.
    """

    has_failure: bool
    taxonomy: str | None
    structured: bool
    score: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: spec 002 §9 failure taxonomy.
FAILURE_TAXONOMY = (
    "implementation_failure",
    "non_identification",
    "non_separation",
    "unsupported_validity_claim",
    "battery_non_applicable",
)


def failure_transparency(
    *, has_failure: bool, taxonomy: str | None, reproducible: bool, contract_ok: bool
) -> FailureTransparency:
    if not has_failure:
        return FailureTransparency(False, None, True, 1.0, "no failure to report")
    structured = bool(taxonomy in FAILURE_TAXONOMY and reproducible and contract_ok)
    return FailureTransparency(
        True,
        taxonomy,
        structured,
        1.0 if structured else 0.0,
        "" if structured else "failure lacks taxonomy/reproducibility/contract → not negative evidence",
    )


@dataclass(slots=True)
class ScoringProfile:
    """The full six-axis profile for one model (the radar)."""

    claim_admissibility: ClaimAdmissibility
    audit_completeness: AuditCompleteness
    intervention_coverage: InterventionCoverage
    mechanism_separability: MechanismSeparability
    replication_stability: ReplicationStability
    failure_transparency: FailureTransparency

    def to_dict(self) -> dict[str, Any]:
        return {axis: getattr(self, axis).to_dict() for axis in PROFILE_AXES}

    def radar(self) -> dict[str, float | None]:
        """Scalar per axis for the radar (separability is None until C1)."""
        sep = None if self.mechanism_separability.status == "pending_c1" else 1.0
        return {
            "claim_admissibility": self.claim_admissibility.score,
            "audit_completeness": self.audit_completeness.score,
            "intervention_coverage": self.intervention_coverage.score,
            "mechanism_separability": sep,
            "replication_stability": self.replication_stability.score,
            "failure_transparency": self.failure_transparency.score,
        }
