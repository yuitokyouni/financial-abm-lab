#!/usr/bin/env python
"""Validate the JPX 2014 cell: re-derive empirical delta-F from real data.

This is the first scientifically valid cell in PRISM.  It:
1. Fetches TOPIX 100 (treatment) and non-TOPIX-100 (control) daily returns
2. Computes PRISM's own 6 facts on each group/period using the SAME estimators
3. DiD estimates with bootstrap CI95
4. Runs SG + ZI-C adapters against the empirically derived deltas
5. Reports whether behavioral (SG) outperforms structural-null (ZI-C)

Usage:
    python scripts/validate_jpx_cell.py
    python scripts/validate_jpx_cell.py --output output/jpx_validation.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

src_root = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_root))

from prism.data.jpx_data import fetch_jpx_dataset
from prism.empirical.did import did_facts
from prism.facts.estimators import FACT_REGISTRY
from prism.pipeline import run_cell
from prism.types import MarketData


ALL_FACT_IDS = list(FACT_REGISTRY.keys())


def main() -> None:
    parser = argparse.ArgumentParser(description="JPX 2014 empirical validation")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    parser.add_argument("--n-boot", type=int, default=2000, help="Bootstrap resamples")
    args = parser.parse_args()

    print("=" * 72)
    print("  PRISM JPX 2014 Empirical Validation")
    print("=" * 72)
    print()

    # --- Step 1: Fetch data ---
    print("[1/4] Fetching JPX treatment/control data via yfinance...")
    dataset = fetch_jpx_dataset()
    print(f"  Treatment: {len(dataset.treatment_ids)} stocks, "
          f"pre={dataset.treatment_pre.shape[0]}d, post={dataset.treatment_post.shape[0]}d")
    print(f"  Control:   {len(dataset.control_ids)} stocks, "
          f"pre={dataset.control_pre.shape[0]}d, post={dataset.control_post.shape[0]}d")
    print(f"  Treatment tickers: {dataset.treatment_ids}")
    print(f"  Control tickers:   {dataset.control_ids}")
    print()

    # --- Step 2: DiD ---
    print(f"[2/4] Computing DiD for {len(ALL_FACT_IDS)} facts (n_boot={args.n_boot})...")
    did_results = did_facts(
        treatment_pre=dataset.treatment_pre,
        treatment_post=dataset.treatment_post,
        control_pre=dataset.control_pre,
        control_post=dataset.control_post,
        fact_ids=ALL_FACT_IDS,
        treatment_ids=dataset.treatment_ids,
        control_ids=dataset.control_ids,
        n_boot=args.n_boot,
    )

    print()
    print("  DiD Results (PRISM estimators on real data):")
    print(f"  {'Fact':<25s}  {'DiD':>10s}  {'CI95_lo':>10s}  {'CI95_hi':>10s}  {'N_treat':>7s}  {'N_ctrl':>7s}")
    print("  " + "-" * 80)
    for r in did_results:
        print(f"  {r.fact_id:<25s}  {r.did_estimate:>+10.6f}  "
              f"{r.ci95[0]:>+10.6f}  {r.ci95[1]:>+10.6f}  "
              f"{r.n_treatment:>7d}  {r.n_control:>7d}")
    print()

    # --- Step 3: Run SG + ZI-C ---
    print("[3/4] Running SG + ZI-C adapters against empirical deltas...")

    avg_treat_pre = np.mean(dataset.treatment_pre, axis=1, keepdims=True)
    pre_data = MarketData(returns=avg_treat_pre)

    ner_path = Path(__file__).resolve().parent.parent / "data" / "ner" / "jpx_2014_jp_tick.yaml"

    adapter_results = {}
    for adapter_name in ["sg", "zi"]:
        cell = run_cell(
            adapter_name=adapter_name,
            ner_path=str(ner_path),
            fact_ids=ALL_FACT_IDS,
            seed=42,
            n_paths=20,
            per_path_facts=True,
            pre_data=pre_data,
        )
        adapter_results[adapter_name] = cell

    # --- Step 4: Compare ---
    print()
    print("[4/4] Comparison: SG (behavioral) vs ZI-C (structural null)")
    print()
    print(f"  {'Fact':<25s}  {'DiD_empirical':>14s}  {'SG_delta':>10s}  {'ZI_delta':>10s}  {'SG_sign':>8s}  {'ZI_sign':>8s}  {'SG>ZI?':>7s}")
    print("  " + "-" * 95)

    comparison_rows = []
    for did_r in did_results:
        fid = did_r.fact_id
        sg_match = next((m for m in adapter_results["sg"].matches if m.fact_id == fid), None)
        zi_match = next((m for m in adapter_results["zi"].matches if m.fact_id == fid), None)

        if sg_match and zi_match:
            sg_err = abs(sg_match.delta_model - did_r.did_estimate)
            zi_err = abs(zi_match.delta_model - did_r.did_estimate)
            sg_beats_zi = sg_err < zi_err

            print(f"  {fid:<25s}  {did_r.did_estimate:>+14.6f}  "
                  f"{sg_match.delta_model:>+10.6f}  {zi_match.delta_model:>+10.6f}  "
                  f"{sg_match.sign_match.value:>8s}  {zi_match.sign_match.value:>8s}  "
                  f"{'YES' if sg_beats_zi else 'NO':>7s}")

            comparison_rows.append({
                "fact_id": fid,
                "did_empirical": did_r.did_estimate,
                "did_ci95": list(did_r.ci95),
                "sg_delta": sg_match.delta_model,
                "zi_delta": zi_match.delta_model,
                "sg_sign": sg_match.sign_match.value,
                "zi_sign": zi_match.sign_match.value,
                "sg_error": sg_err,
                "zi_error": zi_err,
                "sg_beats_zi": sg_beats_zi,
            })

    print()
    sg_wins = sum(1 for r in comparison_rows if r["sg_beats_zi"])
    print(f"  SG beats ZI-C on {sg_wins}/{len(comparison_rows)} facts")
    if sg_wins <= len(comparison_rows) // 2:
        print("  WARNING: SG does NOT consistently outperform the structural null (ZI-C).")
        print("  The behavioral mechanisms may add no value beyond random structure.")
    print()

    # --- Output ---
    output = {
        "event": "JPX 2014 tick size decrease",
        "dataset": {
            "treatment_tickers": dataset.treatment_ids,
            "control_tickers": dataset.control_ids,
            "pre_period": [dataset.pre_start, dataset.pre_end],
            "post_period": [dataset.post_start, dataset.post_end],
            "treatment_pre_shape": list(dataset.treatment_pre.shape),
            "treatment_post_shape": list(dataset.treatment_post.shape),
        },
        "did_results": [
            {
                "fact_id": r.fact_id,
                "did_estimate": r.did_estimate,
                "ci95": list(r.ci95),
                "treatment_pre_mean": r.treatment_pre_mean,
                "treatment_post_mean": r.treatment_post_mean,
                "control_pre_mean": r.control_pre_mean,
                "control_post_mean": r.control_post_mean,
                "n_treatment": r.n_treatment,
                "n_control": r.n_control,
            }
            for r in did_results
        ],
        "adapter_comparison": comparison_rows,
        "sg_wins": sg_wins,
        "total_facts": len(comparison_rows),
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"  Results saved to {out_path}")

    # Also print the NER-compatible ground truth deltas
    print()
    print("  NER-compatible ground_truth_delta (for jpx_2014_jp_tick.yaml):")
    print("  " + "-" * 60)
    for r in did_results:
        gt = r.to_ground_truth_delta(
            causal_method="did_firm_fe",
            causal_assumptions=["parallel_trends", "no_anticipation", "no_spillover_to_non_topix100"],
            references=["empirical_prism_estimator_v0.2.0"],
        )
        print(f"  - fact_id: {gt.fact_id}")
        print(f"    delta_hat: {gt.delta_hat:.6f}")
        print(f"    ci95: [{gt.ci95[0]:.6f}, {gt.ci95[1]:.6f}]" if gt.ci95 else "    ci95: null")
        print()


if __name__ == "__main__":
    main()
