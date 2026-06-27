"""populate — run every REGISTRY model under LHS-sampled params, fingerprint, store.

Pipeline (per (model, sample)):
  1. sample params via LHS within MODEL_BOUNDS[model]
  2. run model with given seed
  3. extract series (returns or attendance_excess) via series_for_fingerprint
  4. fingerprint(series) -> 6-vector
  5. insert into runs table with provenance

Usage:
  uv run python -m fingerprint_atlas.populate \\
      --db ../test/knowhow/abm_knowhow.db \\
      --n-per-model 12 --seed-base 1000
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

import numpy as np

from abm_models import REGISTRY
from .adapters import MODEL_BOUNDS, build_model, sample_params_lhs, series_for_fingerprint
from .db import ensure_runs_schema, insert_run
from .fingerprint import FEATURE_NAMES, fingerprint


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(__file__),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def populate(
    db_path: str,
    *,
    n_per_model: int = 12,
    seed_base: int = 1000,
    models: list[str] | None = None,
    rng_seed: int = 0,
    verbose: bool = True,
) -> dict:
    """Run all models × LHS samples and write rows to `runs`."""
    ensure_runs_schema(db_path)
    chosen = list(models) if models else list(REGISTRY.keys())

    rng = np.random.default_rng(rng_seed)
    provenance_static = {"git_commit": _git_commit(), "host": os.uname().nodename}

    summary = {"db": db_path, "rows": [], "errors": [], "feature_names": FEATURE_NAMES}
    n_total = 0
    t_start = time.time()
    for name in chosen:
        if name not in MODEL_BOUNDS:
            summary["errors"].append({"model": name, "error": "no MODEL_BOUNDS entry"})
            continue
        samples = sample_params_lhs(name, n_per_model, rng)
        for i, params in enumerate(samples):
            seed = seed_base + n_total
            t0 = time.time()
            try:
                model = build_model(name, params)
                result = model.run(seed=seed)
                series, kind = series_for_fingerprint(name, result)
                fp = fingerprint(series, compute_hill=(kind == "returns"))
                rid = insert_run(
                    db_path,
                    model_name=name,
                    params=params,
                    seed=seed,
                    fingerprint_vec=fp,
                    series_kind=kind,
                    series_length=int(len(series)),
                    provenance={**provenance_static,
                                "elapsed_s": round(time.time() - t0, 3),
                                "exception": None},
                    created_at=dt.datetime.utcnow().isoformat() + "Z",
                )
                summary["rows"].append({"id": rid, "model": name, "i": i,
                                        "fp": [None if not np.isfinite(v) else round(float(v), 4)
                                               for v in fp.tolist()]})
                if verbose:
                    elapsed = time.time() - t0
                    fp_str = " ".join(f"{x:+7.3f}" if np.isfinite(x) else "    nan"
                                      for x in fp)
                    print(f"  [{n_total + 1:>3}] {name:<18s} #{i:>2d} seed={seed} "
                          f"({elapsed:5.1f}s) fp=[{fp_str}]")
            except Exception as exc:
                summary["errors"].append({"model": name, "i": i, "params": params,
                                          "error": f"{type(exc).__name__}: {exc}"})
                if verbose:
                    print(f"  [{n_total + 1:>3}] {name:<18s} #{i:>2d} ERROR {exc}", file=sys.stderr)
            n_total += 1
    summary["wall_clock_s"] = round(time.time() - t_start, 1)
    summary["n_rows_written"] = len(summary["rows"])
    summary["n_errors"] = len(summary["errors"])
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True, help="path to abm_knowhow.db (created if absent)")
    ap.add_argument("--n-per-model", type=int, default=12)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--models", nargs="+", default=None, help="subset of REGISTRY keys")
    ap.add_argument("--rng-seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    s = populate(
        args.db, n_per_model=args.n_per_model, seed_base=args.seed_base,
        models=args.models, rng_seed=args.rng_seed, verbose=not args.quiet,
    )
    print("\n--- summary ---")
    print(json.dumps({
        "db": s["db"], "n_rows_written": s["n_rows_written"], "n_errors": s["n_errors"],
        "wall_clock_s": s["wall_clock_s"],
    }, indent=2))
    if s["errors"]:
        print(f"\n{len(s['errors'])} errors; first 3:")
        for e in s["errors"][:3]:
            print("  -", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
