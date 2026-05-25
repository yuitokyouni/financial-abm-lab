"""End-to-end evaluation pipeline — one cell of the phase-diagram tensor.

Orchestrates: NER loading → adapter calibration → pre/post simulation →
fact estimation → delta computation → scoring → provenance sealing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from prism.adapters.ci import CIAdapter
from prism.adapters.sg import SGAdapter
from prism.adapters.zi import ZIAdapter
from prism.data import load_ner
from prism.facts import compute_fact
from prism.provenance import ProvenanceTracker
from prism.scoring import compute_matches
from prism.scoring.eligibility import (
    EligibilityResult,
    EligibilityVerdict,
    check_eligibility,
)
from prism.scoring.mdl import WeightedMatchResult, apply_mdl_weights
from prism.types import (
    DeltaFact,
    FactResult,
    MarketData,
    MatchResult,
    MatchVerdict,
    SimulatedMarketData,
)


ADAPTER_REGISTRY: dict[str, type] = {
    "sg": SGAdapter,
    "ci": CIAdapter,
    "zi": ZIAdapter,
}


@dataclass
class CellOutput:
    """Output of one evaluation cell."""

    adapter_id: str
    ner_id: str
    matches: list[MatchResult]
    provenance: dict[str, Any]
    weighted_matches: list[WeightedMatchResult] = field(default_factory=list)
    eligibility: EligibilityResult | None = None

    def summary(self) -> str:
        lines = [
            f"=== PRISM Cell: {self.adapter_id} × {self.ner_id} ===",
            "",
        ]

        if self.eligibility:
            lines.append(f"  Eligibility: {self.eligibility.verdict.value}")
            for c in self.eligibility.checks:
                status = "PASS" if c.in_range else "FAIL"
                lines.append(
                    f"    {c.fact_id:28s} value={c.value:+.6f}  "
                    f"range=[{c.expected_range[0]:.3f}, {c.expected_range[1]:.3f}]  {status}"
                )
            lines.append("")

        use_weighted = bool(self.weighted_matches)
        display = self.weighted_matches if use_weighted else self.matches

        for item in display:
            if isinstance(item, WeightedMatchResult):
                sign_str = item.sign_match.value.upper()
                mag_str = "yes" if item.magnitude_within_ci else ("no" if item.magnitude_within_ci is False else "n/a")
                lines.append(
                    f"  {item.fact_id:30s}  sign={sign_str:14s}  "
                    f"mag_in_ci={mag_str:4s}  "
                    f"Δ_model={item.delta_model:+.6f}  Δ_empirical={item.delta_empirical:+.6f}  "
                    f"conf_raw={item.confidence_raw:.2f}  "
                    f"mdl_w={item.mdl_weight:.3f}  "
                    f"conf_weighted={item.confidence_weighted:.3f}"
                )
            else:
                sign_str = item.sign_match.value.upper()
                mag_str = "yes" if item.magnitude_within_ci else ("no" if item.magnitude_within_ci is False else "n/a")
                lines.append(
                    f"  {item.fact_id:30s}  sign={sign_str:14s}  "
                    f"mag_in_ci={mag_str:4s}  "
                    f"Δ_model={item.delta_model:+.6f}  Δ_empirical={item.delta_empirical:+.6f}  "
                    f"confidence={item.confidence:.2f}"
                )
        lines.append("")

        sign_matches = sum(1 for m in self.matches if m.sign_match == MatchVerdict.MATCH)
        lines.append(
            f"  Sign consistency: {sign_matches}/{len(self.matches)}"
        )
        lines.append(f"  Run ID: {self.provenance.get('run_id', 'unknown')}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
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
        if self.weighted_matches:
            result["weighted_matches"] = [
                {
                    "fact_id": wm.fact_id,
                    "confidence_raw": wm.confidence_raw,
                    "mdl_weight": wm.mdl_weight,
                    "confidence_weighted": wm.confidence_weighted,
                }
                for wm in self.weighted_matches
            ]
        if self.eligibility:
            result["eligibility"] = {
                "verdict": self.eligibility.verdict.value,
                "n_pass": self.eligibility.n_pass,
                "n_fail": self.eligibility.n_fail,
                "checks": [
                    {
                        "fact_id": c.fact_id,
                        "value": c.value,
                        "expected_range": list(c.expected_range),
                        "in_range": c.in_range,
                    }
                    for c in self.eligibility.checks
                ],
            }
        return result


def _compute_per_path_facts(
    adapter: object,
    fact_ids: list[str],
    seed: int,
    n_paths: int,
) -> tuple[dict[str, FactResult], SimulatedMarketData]:
    """Compute facts on individual simulation paths and return median values.

    Instead of averaging returns across paths (which destroys higher-order
    distributional properties like kurtosis), this runs each path
    independently and takes the median of per-path fact estimates.
    """
    all_facts: dict[str, list[FactResult]] = {fid: [] for fid in fact_ids}
    first_sim: SimulatedMarketData | None = None

    for p in range(n_paths):
        sim = adapter.simulate(seed=seed + p, n_paths=1)  # type: ignore[union-attr]
        if first_sim is None:
            first_sim = sim
        for fid in fact_ids:
            fact = compute_fact(fid, sim.returns)
            all_facts[fid].append(fact)

    assert first_sim is not None

    median_facts: dict[str, FactResult] = {}
    for fid in fact_ids:
        values = [f.value for f in all_facts[fid] if not np.isnan(f.value)]
        if values:
            median_val = float(np.median(values))
            cis = [f.ci95 for f in all_facts[fid] if f.ci95 is not None]
            ci95: tuple[float, float] | None = None
            if cis:
                ci95 = (
                    float(np.median([c[0] for c in cis])),
                    float(np.median([c[1] for c in cis])),
                )
            median_facts[fid] = FactResult(
                fact_id=fid,
                value=median_val,
                ci95=ci95,
                estimator_version=all_facts[fid][0].estimator_version,
                metadata={
                    "aggregation": "per_path_median",
                    "n_paths": n_paths,
                },
            )
        else:
            median_facts[fid] = all_facts[fid][0]

    return median_facts, first_sim


def run_cell(
    adapter_name: str,
    ner_path: str | Path,
    fact_ids: list[str],
    seed: int = 42,
    n_paths: int = 10,
    per_path_facts: bool = False,
) -> CellOutput:
    """Execute one cell of the phase-diagram tensor.

    When per_path_facts=True, facts are computed on individual simulation
    paths and aggregated via median.  This preserves higher-order
    distributional properties (kurtosis, skewness) that path-averaging
    destroys.
    """

    # --- Setup ---
    tracker = ProvenanceTracker()
    tracker.record_seed("simulation", seed)
    tracker.record_parameter("adapter", adapter_name)
    tracker.record_parameter("n_paths", n_paths)
    tracker.record_parameter("per_path_facts", per_path_facts)

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

    # --- Apply intervention ---
    post_adapter = adapter.apply_intervention(calib, ner.intervention)

    if per_path_facts:
        # --- Per-path mode: preserve distributional properties ---
        pre_facts, sim_pre = _compute_per_path_facts(
            adapter, fact_ids, seed, n_paths,
        )
        tracker.record_data_hash("sim_pre", sim_pre.content_hash())

        post_facts, sim_post = _compute_per_path_facts(
            post_adapter, fact_ids, seed, n_paths,
        )
        tracker.record_data_hash("sim_post", sim_post.content_hash())

        model_deltas = []
        for fid in fact_ids:
            tracker.record_estimator_version(fid, pre_facts[fid].estimator_version)
            delta = DeltaFact(
                fact_id=fid,
                delta=post_facts[fid].value - pre_facts[fid].value,
                pre=pre_facts[fid],
                post=post_facts[fid],
            )
            model_deltas.append(delta)

        baseline_facts = list(pre_facts.values())
    else:
        # --- Classic mode: average returns across paths ---
        sim_pre = adapter.simulate(seed=seed, n_paths=n_paths)
        tracker.record_data_hash("sim_pre", sim_pre.content_hash())

        sim_post = post_adapter.simulate(seed=seed, n_paths=n_paths)
        tracker.record_data_hash("sim_post", sim_post.content_hash())

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

        baseline_facts = [compute_fact(fid, sim_pre.returns) for fid in fact_ids]

    # --- Static eligibility gate ---
    eligibility = check_eligibility(adapter_name, baseline_facts)
    tracker.record_parameter("eligibility", eligibility.verdict.value)

    # --- Score against ground truth ---
    matches = compute_matches(model_deltas, ner.ground_truth_deltas)

    # --- MDL + causal method weighting ---
    complexity = adapter.describe_complexity()
    primary_causal = ner.ground_truth_deltas[0].causal_method if ner.ground_truth_deltas else ""
    weighted = apply_mdl_weights(matches, complexity, causal_method=primary_causal)
    tracker.record_parameter("mdl_n_free_params", complexity.n_free_params)

    # --- Seal provenance ---
    prov = tracker.seal()

    return CellOutput(
        adapter_id=adapter_name,
        ner_id=ner.ner_id,
        matches=matches,
        provenance=prov.to_dict(),
        weighted_matches=weighted,
        eligibility=eligibility,
    )


@dataclass
class TensorOutput:
    """Full phase-diagram tensor: adapter × intervention × fact → match."""

    cells: list[CellOutput]
    adapter_ids: list[str]
    ner_ids: list[str]
    fact_ids: list[str]

    def summary(self) -> str:
        lines = ["=" * 72, "  PRISM Phase-Diagram Tensor", "=" * 72, ""]

        ineligible = [
            c for c in self.cells
            if c.eligibility and c.eligibility.verdict == EligibilityVerdict.INELIGIBLE
        ]
        if ineligible:
            lines.append("  *** Ineligible adapters (baseline outside empirical range):")
            for c in ineligible:
                lines.append(f"      {c.adapter_id} × {c.ner_id}")
            lines.append("")

        for cell in self.cells:
            lines.append(cell.summary())
            lines.append("")

        lines.append("-" * 72)
        lines.append("  Divergence Analysis")
        lines.append("-" * 72)

        for ner_id in self.ner_ids:
            ner_cells = [c for c in self.cells if c.ner_id == ner_id]
            for fid in self.fact_ids:
                scores = {}
                for cell in ner_cells:
                    for m in cell.matches:
                        if m.fact_id == fid:
                            scores[cell.adapter_id] = m
                if len(scores) >= 2:
                    ids = list(scores.keys())
                    for i in range(len(ids)):
                        for j in range(i + 1, len(ids)):
                            a, b = ids[i], ids[j]
                            ma, mb = scores[a], scores[b]
                            if ma.sign_match != mb.sign_match:
                                lines.append(
                                    f"  DIVERGENCE [{ner_id}/{fid}]: "
                                    f"{a}={ma.sign_match.value} vs "
                                    f"{b}={mb.sign_match.value}"
                                )
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_ids": self.adapter_ids,
            "ner_ids": self.ner_ids,
            "fact_ids": self.fact_ids,
            "cells": [c.to_dict() for c in self.cells],
        }


@dataclass
class MethodComparisonRow:
    """One row in a causal method comparison: same match, different weighting."""

    causal_method: str
    causal_weight: float
    fact_id: str
    confidence_raw: float
    mdl_weight: float
    confidence_weighted: float


@dataclass
class MethodComparisonOutput:
    """Comparison of causal methods for a single adapter × NER cell."""

    adapter_id: str
    ner_id: str
    methods: list[str]
    rows: list[MethodComparisonRow]

    def summary(self) -> str:
        lines = [
            f"=== Causal Method Comparison: {self.adapter_id} × {self.ner_id} ===",
            "",
            f"  {'Method':<20s}  {'Fact':<25s}  {'w_causal':>8s}  {'conf_raw':>8s}  {'mdl_w':>6s}  {'conf_wtd':>8s}",
            "  " + "-" * 85,
        ]
        for row in self.rows:
            lines.append(
                f"  {row.causal_method:<20s}  {row.fact_id:<25s}  "
                f"{row.causal_weight:>8.3f}  {row.confidence_raw:>8.3f}  "
                f"{row.mdl_weight:>6.3f}  {row.confidence_weighted:>8.3f}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "ner_id": self.ner_id,
            "methods": self.methods,
            "rows": [
                {
                    "causal_method": r.causal_method,
                    "causal_weight": r.causal_weight,
                    "fact_id": r.fact_id,
                    "confidence_raw": r.confidence_raw,
                    "mdl_weight": r.mdl_weight,
                    "confidence_weighted": r.confidence_weighted,
                }
                for r in self.rows
            ],
        }


def compare_causal_methods(
    adapter_name: str,
    ner_path: str | Path,
    fact_ids: list[str],
    methods: list[str] | None = None,
    seed: int = 42,
    n_paths: int = 10,
    per_path_facts: bool = False,
) -> MethodComparisonOutput:
    """Re-weight the same cell with different causal identification methods."""
    from prism.scoring.causal import CAUSAL_METHOD_WEIGHTS, causal_method_weight

    if methods is None:
        methods = list(CAUSAL_METHOD_WEIGHTS.keys())

    cell = run_cell(adapter_name, ner_path, fact_ids, seed, n_paths, per_path_facts=per_path_facts)
    complexity = ADAPTER_REGISTRY[adapter_name]().describe_complexity()
    mdl = apply_mdl_weights(cell.matches, complexity).pop() if cell.matches else None
    mdl_w = mdl.mdl_weight if mdl else 0.0

    rows = []
    for method in methods:
        cw = causal_method_weight(method)
        for m in cell.matches:
            rows.append(MethodComparisonRow(
                causal_method=method,
                causal_weight=cw,
                fact_id=m.fact_id,
                confidence_raw=m.confidence,
                mdl_weight=mdl_w,
                confidence_weighted=m.confidence * mdl_w * cw,
            ))

    ner = load_ner(ner_path)
    return MethodComparisonOutput(
        adapter_id=adapter_name,
        ner_id=ner.ner_id,
        methods=methods,
        rows=rows,
    )


def run_tensor(
    adapter_names: list[str],
    ner_paths: list[str | Path],
    fact_ids: list[str],
    seed: int = 42,
    n_paths: int = 10,
    per_path_facts: bool = False,
) -> TensorOutput:
    """Execute the full phase-diagram tensor: adapters × NERs × facts."""

    cells = []
    ner_ids = []
    for ner_path in ner_paths:
        ner = load_ner(ner_path)
        ner_ids.append(ner.ner_id)

    for adapter_name in adapter_names:
        for ner_path in ner_paths:
            cell = run_cell(
                adapter_name=adapter_name,
                ner_path=ner_path,
                fact_ids=fact_ids,
                seed=seed,
                n_paths=n_paths,
                per_path_facts=per_path_facts,
            )
            cells.append(cell)

    seen = []
    for nid in ner_ids:
        if nid not in seen:
            seen.append(nid)

    return TensorOutput(
        cells=cells,
        adapter_ids=adapter_names,
        ner_ids=seen,
        fact_ids=fact_ids,
    )
