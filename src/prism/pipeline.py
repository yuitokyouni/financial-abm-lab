"""End-to-end evaluation pipeline — one cell of the phase-diagram tensor.

Orchestrates: NER loading → adapter calibration → pre/post simulation →
fact estimation → delta computation → scoring → provenance sealing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from prism.adapters.sg import SGAdapter
from prism.data import load_ner
from prism.facts import FACT_REGISTRY, compute_fact
from prism.provenance import ProvenanceTracker
from prism.scoring import compute_matches
from prism.types import (
    DeltaFact,
    MarketData,
    MatchResult,
    MatchVerdict,
    NaturalExperimentRecord,
)


ADAPTER_REGISTRY: dict[str, type] = {
    "sg": SGAdapter,
}


@dataclass
class CellOutput:
    """Output of one evaluation cell."""

    adapter_id: str
    ner_id: str
    matches: list[MatchResult]
    provenance: dict[str, Any]

    def summary(self) -> str:
        lines = [
            f"=== PRISM Cell: {self.adapter_id} × {self.ner_id} ===",
            "",
        ]
        for m in self.matches:
            sign_str = m.sign_match.value.upper()
            mag_str = "yes" if m.magnitude_within_ci else ("no" if m.magnitude_within_ci is False else "n/a")
            lines.append(
                f"  {m.fact_id:30s}  sign={sign_str:14s}  "
                f"mag_in_ci={mag_str:4s}  "
                f"Δ_model={m.delta_model:+.6f}  Δ_empirical={m.delta_empirical:+.6f}  "
                f"confidence={m.confidence:.2f}"
            )
        lines.append("")

        sign_matches = sum(1 for m in self.matches if m.sign_match == MatchVerdict.MATCH)
        lines.append(
            f"  Sign consistency: {sign_matches}/{len(self.matches)}"
        )
        lines.append(f"  Run ID: {self.provenance.get('run_id', 'unknown')}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "ner_id": self.ner_id,
            "matches": [
                {
                    "fact_id": m.fact_id,
                    "delta_model": m.delta_model,
                    "delta_empirical": m.delta_empirical,
                    "sign_match": m.sign_match.value,
                    "magnitude_within_ci": m.magnitude_within_ci,
                    "confidence": m.confidence,
                }
                for m in self.matches
            ],
            "provenance": self.provenance,
        }


def run_cell(
    adapter_name: str,
    ner_path: str | Path,
    fact_ids: list[str],
    seed: int = 42,
    n_paths: int = 10,
) -> CellOutput:
    """Execute one cell of the phase-diagram tensor."""

    # --- Setup ---
    tracker = ProvenanceTracker()
    tracker.record_seed("simulation", seed)
    tracker.record_parameter("adapter", adapter_name)
    tracker.record_parameter("n_paths", n_paths)

    # --- Load NER ---
    ner = load_ner(ner_path)
    tracker.record_parameter("ner_id", ner.ner_id)

    # --- Create adapter ---
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    adapter = ADAPTER_REGISTRY[adapter_name]()

    # --- Generate synthetic pre-intervention data for calibration ---
    rng = np.random.default_rng(seed)
    pre_returns = rng.normal(0, 0.02, (500, 1))
    pre_data = MarketData(returns=pre_returns)
    tracker.record_data_hash("pre_synthetic", pre_data.content_hash())

    # --- Calibrate baseline ---
    calib = adapter.calibrate_baseline(pre_data, {})

    # --- Simulate PRE-intervention ---
    sim_pre = adapter.simulate(seed=seed, n_paths=n_paths)
    tracker.record_data_hash("sim_pre", sim_pre.content_hash())

    # --- Apply intervention ---
    post_adapter = adapter.apply_intervention(calib, ner.intervention)

    # --- Simulate POST-intervention ---
    sim_post = post_adapter.simulate(seed=seed, n_paths=n_paths)
    tracker.record_data_hash("sim_post", sim_post.content_hash())

    # --- Compute facts on both regimes ---
    model_deltas = []
    for fid in fact_ids:
        pre_fact = compute_fact(fid, sim_pre.returns)
        post_fact = compute_fact(fid, sim_post.returns)
        tracker.record_estimator_version(fid, pre_fact.estimator_version)

        delta = DeltaFact(
            fact_id=fid,
            delta=post_fact.value - pre_fact.value,
            pre=pre_fact,
            post=post_fact,
        )
        model_deltas.append(delta)

    # --- Score against ground truth ---
    matches = compute_matches(model_deltas, ner.ground_truth_deltas)

    # --- Seal provenance ---
    prov = tracker.seal()

    return CellOutput(
        adapter_id=adapter_name,
        ner_id=ner.ner_id,
        matches=matches,
        provenance=prov.to_dict(),
    )
