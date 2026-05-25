"""NER (Natural Experiment Record) loader — reads YAML files into typed objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from prism.types import CanonicalIntervention, GroundTruthDelta, NaturalExperimentRecord


def load_ner(path: str | Path) -> NaturalExperimentRecord:
    """Load a NER from a YAML file."""
    path = Path(path)
    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return _parse_ner(raw)


def _parse_ner(raw: dict[str, Any]) -> NaturalExperimentRecord:
    intervention_raw = raw["intervention"]
    intervention = CanonicalIntervention(
        intervention_class=intervention_raw["class"],
        canonical_params=intervention_raw.get("canonical_params", {}),
    )

    ner_id = raw.get("ner_id", "<unknown>")
    deltas = []
    for d in raw.get("ground_truth_delta", []):
        refs = d.get("references", [])
        if "external_claim" in refs:
            raise ValueError(
                f"NER '{ner_id}' fact '{d.get('fact_id')}' contains an "
                f"'external_claim' reference — ground truth must be empirically "
                f"re-derived before use in PRISM."
            )
        ci_raw = d.get("ci95")
        ci95 = tuple(ci_raw) if ci_raw else None
        deltas.append(
            GroundTruthDelta(
                fact_id=d["fact_id"],
                delta_hat=float(d["delta_hat"]),
                ci95=ci95,
                causal_method=d.get("causal_method", "did_firm_fe"),
                causal_assumptions=d.get("causal_assumptions", []),
                unit=d.get("unit", "relative"),
                references=d.get("references", []),
            )
        )

    return NaturalExperimentRecord(
        ner_id=raw["ner_id"],
        intervention=intervention,
        ground_truth_deltas=deltas,
        venue=raw.get("venue", ""),
        date_effective=raw.get("date_effective", ""),
        assignment=raw.get("assignment", "randomized"),
        data_hashes=raw.get("data_hashes", {}),
    )
