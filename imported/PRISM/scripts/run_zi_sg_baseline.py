#!/usr/bin/env python3
"""Run ZI-C baseline and SG cell for JPX 2014, recording results.

This script:
1. Runs ZI-C (null model) on JPX 2014 tick size decrease
2. Runs SG (behavioral model) on the same NER
3. Records sign match results and model deltas for both
4. Compares SG discriminating power against ZI-C baseline
"""
from __future__ import annotations

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path

from prism.pipeline import run_cell

NER_PATH = Path(__file__).parent.parent / "data" / "ner" / "jpx_2014_jp_tick.yaml"
FACT_IDS = [
    "volatility_clustering",
    "leverage_effect",
    "gain_loss_asymmetry",
    "fat_tails",
    "abs_autocorrelation",
    "squared_return_acf",
]

SEEDS = [42, 123, 456, 789, 1024]
N_PATHS = 20


def run_adapter_multi_seed(adapter_name: str) -> dict:
    """Run an adapter across multiple seeds and report results."""
    all_results = []

    for seed in SEEDS:
        print(f"  seed={seed}...", end=" ", flush=True)
        cell = run_cell(
            adapter_name=adapter_name,
            ner_path=str(NER_PATH),
            fact_ids=FACT_IDS,
            seed=seed,
            n_paths=N_PATHS,
            per_path_facts=True,
        )

        seed_results = {}
        for m in cell.matches:
            seed_results[m.fact_id] = {
                "sign": m.sign_match.value,
                "delta_model": m.delta_model,
                "delta_empirical": m.delta_empirical,
                "magnitude_within_ci": m.magnitude_within_ci,
            }
        all_results.append(seed_results)
        print(f"done ({sum(1 for m in cell.matches if m.sign_match.value == 'match')}/6 sign matches)")

    # Aggregate across seeds
    print(f"\n  Stability across {len(SEEDS)} seeds:")
    aggregate = {}
    for fid in FACT_IDS:
        signs = [r[fid]["sign"] for r in all_results]
        deltas = [r[fid]["delta_model"] for r in all_results]
        n_match = signs.count("match")
        n_mismatch = signs.count("mismatch")
        n_inconclusive = signs.count("inconclusive")

        import numpy as np
        aggregate[fid] = {
            "n_match": n_match,
            "n_mismatch": n_mismatch,
            "n_inconclusive": n_inconclusive,
            "delta_model_mean": float(np.mean(deltas)),
            "delta_model_std": float(np.std(deltas)),
            "stable_sign": n_match == len(SEEDS) or n_mismatch == len(SEEDS) or n_inconclusive == len(SEEDS),
        }
        status = f"MATCH={n_match} MISMATCH={n_mismatch} INCONCLUSIVE={n_inconclusive}"
        stable = "STABLE" if aggregate[fid]["stable_sign"] else "UNSTABLE"
        print(f"    {fid:30s} {status:40s} [{stable}] Δ_model={aggregate[fid]['delta_model_mean']:+.6f}±{aggregate[fid]['delta_model_std']:.6f}")

    return {"per_seed": all_results, "aggregate": aggregate}


def main():
    print("=" * 72)
    print("PRISM ZI-C Baseline & SG Cell — JPX 2014")
    print(f"NER: {NER_PATH}")
    print(f"Seeds: {SEEDS}")
    print(f"Paths per seed: {N_PATHS}")
    print("=" * 72)

    # Run ZI-C (null model baseline)
    print("\n--- ZI-C (Zero-Intelligence Constrained) ---")
    zi_results = run_adapter_multi_seed("zi")

    # Run SG (behavioral model)
    print("\n--- SG (Speculation Game) ---")
    sg_results = run_adapter_multi_seed("sg")

    # Compare discriminating power
    print("\n" + "=" * 72)
    print("DISCRIMINATING POWER: SG vs ZI-C")
    print("=" * 72)

    for fid in FACT_IDS:
        zi_agg = zi_results["aggregate"][fid]
        sg_agg = sg_results["aggregate"][fid]
        print(f"\n  {fid}:")
        print(f"    ZI-C: MATCH={zi_agg['n_match']} MISMATCH={zi_agg['n_mismatch']} INCONCLUSIVE={zi_agg['n_inconclusive']}  Δ={zi_agg['delta_model_mean']:+.6f}±{zi_agg['delta_model_std']:.6f}")
        print(f"    SG:   MATCH={sg_agg['n_match']} MISMATCH={sg_agg['n_mismatch']} INCONCLUSIVE={sg_agg['n_inconclusive']}  Δ={sg_agg['delta_model_mean']:+.6f}±{sg_agg['delta_model_std']:.6f}")

        # Discriminating power: does SG produce systematically different
        # sign match results from ZI-C?
        if sg_agg["n_inconclusive"] == len(SEEDS) and zi_agg["n_inconclusive"] == len(SEEDS):
            print(f"    → Both INCONCLUSIVE (ground truth CI95 crosses zero)")
        elif sg_agg["n_match"] > zi_agg["n_match"]:
            print(f"    → SG outperforms ZI-C")
        elif sg_agg["n_match"] < zi_agg["n_match"]:
            print(f"    → ZI-C outperforms SG (no discriminating power)")
        else:
            print(f"    → No discriminating power (same match rate)")

    # Save results
    output = {
        "ner_id": "jpx_2014_jp_tick",
        "seeds": SEEDS,
        "n_paths": N_PATHS,
        "zi_c": zi_results,
        "sg": sg_results,
    }

    output_path = Path(__file__).parent.parent / "output" / "zi_sg_baseline.json"
    output_path.parent.mkdir(exist_ok=True)

    # Convert numpy types for JSON
    def convert(obj):
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=convert)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
