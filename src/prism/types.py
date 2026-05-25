"""Core data types and protocols for PRISM."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt


class MatchVerdict(Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class MarketData:
    """Time series of daily returns (and optional prices) for a set of instruments."""

    returns: npt.NDArray[np.float64]  # shape: (T, N) — T days, N instruments
    dates: npt.NDArray[np.datetime64] | None = None
    instrument_ids: list[str] = field(default_factory=list)

    @property
    def n_days(self) -> int:
        return self.returns.shape[0]

    @property
    def n_instruments(self) -> int:
        return self.returns.shape[1] if self.returns.ndim > 1 else 1

    def content_hash(self) -> str:
        return hashlib.sha256(self.returns.tobytes()).hexdigest()[:16]


@dataclass(frozen=True)
class CanonicalIntervention:
    """A canonical intervention from the Abstract Intervention Space."""

    intervention_class: str  # e.g. "tick_size_increase"
    canonical_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CalibrationArtifact:
    """Immutable record of a model's baseline calibration."""

    model_id: str
    calibrated_params: dict[str, Any]
    pre_data_hash: str
    seed: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulatedMarketData:
    """Output of a model simulation — same shape contract as MarketData."""

    returns: npt.NDArray[np.float64]
    seed: int
    n_paths: int
    model_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        return hashlib.sha256(self.returns.tobytes()).hexdigest()[:16]


@dataclass(frozen=True)
class FactResult:
    """Result of computing a single stylized fact."""

    fact_id: str
    value: float
    ci95: tuple[float, float] | None = None
    estimator_version: str = "0.2.0"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeltaFact:
    """Change in a fact between pre- and post-intervention regimes."""

    fact_id: str
    delta: float  # post - pre
    pre: FactResult
    post: FactResult
    ci95: tuple[float, float] | None = None


@dataclass(frozen=True)
class GroundTruthDelta:
    """Empirical delta from a natural experiment (NER)."""

    fact_id: str
    delta_hat: float
    ci95: tuple[float, float] | None = None
    causal_method: str = "did_firm_fe"
    causal_assumptions: list[str] = field(default_factory=list)
    unit: str = "relative"
    references: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NaturalExperimentRecord:
    """A natural experiment record — the empirical ground truth."""

    ner_id: str
    intervention: CanonicalIntervention
    ground_truth_deltas: list[GroundTruthDelta]
    venue: str = ""
    date_effective: str = ""
    assignment: str = "randomized"
    data_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResult:
    """Result of comparing model delta to empirical delta for one fact."""

    fact_id: str
    delta_model: float
    delta_empirical: float
    sign_match: MatchVerdict
    magnitude_within_ci: bool | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class ComplexitySpec:
    """Model complexity descriptor for MDL weighting."""

    n_free_params: int
    structural_description: str
    description_length: float = 0.0


@dataclass
class CellResult:
    """One cell of the phase-diagram tensor: mechanism x intervention x fact."""

    model_id: str
    model_commit: str
    intervention_class: str
    fact_id: str
    delta_hat_model: float
    delta_obs: float
    match: MatchVerdict
    confidence: float
    provenance_uri: str = ""


@runtime_checkable
class ModelAdapter(Protocol):
    """Protocol that any ABM must satisfy to be evaluated by PRISM."""

    def calibrate_baseline(
        self, pre_data: MarketData, ais_context: dict[str, Any]
    ) -> CalibrationArtifact: ...

    def apply_intervention(
        self, calib: CalibrationArtifact, intervention: CanonicalIntervention
    ) -> ModelAdapter: ...

    def simulate(self, seed: int, n_paths: int) -> SimulatedMarketData: ...

    def describe_complexity(self) -> ComplexitySpec: ...
