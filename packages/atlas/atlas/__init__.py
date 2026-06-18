"""atlas — Intervention Atlas Minimum Viable Arena (spec 002).

Contract-first (spec 002 §3): a model that satisfies ``model_contract_v1`` becomes
eligible for an Atlas row. This package implements the MVA core:

  - ``contract``        model_contract_v1 surface + C0/C1/C2 conformance
  - ``intervention``    the four B2 schemes the P1 run needs
  - ``profiles``        the six GT-free scoring-profile axes (no validity rank)
  - ``registry``        frozen semantic-labeling layer (kept out of the CI gate)
  - ``row``             AtlasRow schema + emit_row (dogfood the contract)
  - ``reference_atlas`` first internal reference atlas + launch-readiness check
  - ``ignition``        the frozen "no external infra before P1 GO + diagnostic" rule
"""

from __future__ import annotations

from .contract import (
    ConformanceLevel,
    ContractModel,
    ContractViolation,
    Intervention,
    Simulator,
    check_determinism,
    detect_conformance,
)
from .ignition import (
    GATED_FEATURES,
    IgnitionLocked,
    IgnitionState,
    ignition_unlocked,
    require_ignition,
)
from .intervention import SCHEMES, InterventionScheme, apply_scheme
from .profiles import PROFILE_AXES, ScoringProfile
from .reference_atlas import (
    check_launch_readiness,
    generate_reference_atlas,
    write_reference_atlas,
)
from .registry import FROZEN_REGISTRY, diversity_satisfied, eligible_models
from .row import emit_row

__all__ = [
    "ConformanceLevel",
    "ContractModel",
    "ContractViolation",
    "Intervention",
    "Simulator",
    "check_determinism",
    "detect_conformance",
    "InterventionScheme",
    "SCHEMES",
    "apply_scheme",
    "PROFILE_AXES",
    "ScoringProfile",
    "FROZEN_REGISTRY",
    "eligible_models",
    "diversity_satisfied",
    "emit_row",
    "generate_reference_atlas",
    "check_launch_readiness",
    "write_reference_atlas",
    "GATED_FEATURES",
    "IgnitionLocked",
    "IgnitionState",
    "ignition_unlocked",
    "require_ignition",
]
