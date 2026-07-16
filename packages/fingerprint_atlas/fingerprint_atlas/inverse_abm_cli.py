"""inverse_abm_cli — terminal interface to the "today's market ≈ which ABM?"
query.

Sub-commands:
  nearest    Find the k ABM runs whose fingerprint is closest to a given
             target. Target is one of:
               --target-run-id N        an existing run in `runs`
               --target-model NAME      use the centroid of that model's runs
               --returns-csv PATH       a one-column CSV of log-returns
             By default candidates are filtered to origin='abm' — pass
             --include-real-synthetic to widen the search.

  heatmap    Render the full real-market × ABM-family distance matrix as a
             PNG heatmap, with the nearest ABM family per real period
             circled in red. Prints the argmin summary as JSON.

Usage examples:
  uv run python -m fingerprint_atlas.inverse_abm_cli \\
      --db ../test/knowhow/abm_knowhow.db nearest --target-model real_spx_full --k 5

  uv run python -m fingerprint_atlas.inverse_abm_cli \\
      --db ../test/knowhow/abm_knowhow.db nearest --returns-csv my_returns.csv --k 5

  uv run python -m fingerprint_atlas.inverse_abm_cli \\
      --db ../test/knowhow/abm_knowhow.db heatmap --out notebooks/inverse_abm.png
"""
from __future__ import annotations

import argparse
import json
import sys

from .fingerprint import FEATURE_NAMES
from .inverse_abm import (
    _load_returns_from_csv, nearest_abms_to_target, plot_real_vs_abm_heatmap,
)


def cmd_nearest(args) -> int:
    returns = None
    if args.returns_csv:
        try:
            returns = _load_returns_from_csv(args.returns_csv)
        except Exception as exc:
            print(f"failed to load {args.returns_csv}: {exc}", file=sys.stderr)
            return 1
        print(f"  loaded {len(returns)} returns from {args.returns_csv}")
    try:
        result = nearest_abms_to_target(
            args.db,
            target_run_id=args.target_run_id,
            target_model_name=args.target_model,
            returns=returns,
            k=args.k,
            abm_only=not args.include_real_synthetic,
        )
    except (KeyError, RuntimeError, ValueError) as exc:
        print(f"  error: {exc}", file=sys.stderr)
        return 1

    print(f"\n=== inverse-ABM: closest {result['k']} runs ===")
    print(f"  target: {result['target_label']}")
    print(f"  searched against {result['n_candidates_searched']} candidate runs"
          + ("" if not args.include_real_synthetic
             else " (incl. real / synthetic)"))
    print(f"  feature_names: {FEATURE_NAMES}")
    print(f"  target_fingerprint: {result['target_fingerprint']}")
    print()
    for i, m in enumerate(result["matches"], start=1):
        params_short = json.dumps(m["params"], sort_keys=True)
        if len(params_short) > 90:
            params_short = params_short[:87] + "..."
        print(f"  #{i:<2d} dist={m['distance']:.3f}  run_id={m['run_id']:<4d} "
              f"{m['model_name']:<22s} ({m['origin']})")
        print(f"        seed={m['seed']}  params={params_short}")
        print(f"        fp={m['fingerprint']}")
    return 0


def cmd_heatmap(args) -> int:
    import os
    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    try:
        result = plot_real_vs_abm_heatmap(args.db, args.out)
    except RuntimeError as exc:
        print(f"  error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {result['out_png']}  (matrix shape: {result['matrix_shape']})")
    print("\nnearest ABM family per real period:")
    for r in result["argmin_per_real"]:
        print(f"  {r['real']:<22s} -> {r['nearest_abm_family']:<22s} "
              f"(median dist {r['median_distance']:.2f})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="inverse-ABM nearest-neighbour + real×ABM heatmap"
    )
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_n = sub.add_parser("nearest", help="find k nearest ABM runs to a target")
    src = p_n.add_mutually_exclusive_group(required=True)
    src.add_argument("--target-run-id", type=int,
                     help="use the fingerprint of this run as target")
    src.add_argument("--target-model", type=str,
                     help="use the centroid of all runs with this model_name")
    src.add_argument("--returns-csv", type=str,
                     help="one-column CSV of log-returns (or date,return)")
    p_n.add_argument("--k", type=int, default=5)
    p_n.add_argument("--include-real-synthetic", action="store_true",
                     help="search across real / synthetic candidates too "
                          "(default: ABM-only)")

    p_h = sub.add_parser("heatmap",
                          help="real × ABM family distance matrix as PNG")
    p_h.add_argument("--out", default="notebooks/inverse_abm_heatmap.png")

    args = ap.parse_args()
    if args.cmd == "nearest":
        return cmd_nearest(args)
    if args.cmd == "heatmap":
        return cmd_heatmap(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
