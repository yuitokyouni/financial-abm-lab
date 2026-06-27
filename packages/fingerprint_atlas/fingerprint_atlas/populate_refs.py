"""populate_refs — push synthetic injectors + real-market references into `runs`.

Two passes, both writing rows with `origin='synthetic'` or `origin='real'` so
they're distinguishable from the 8 canonical ABMs (`origin='abm'`).

Usage:
  uv run python -m fingerprint_atlas.populate_refs \\
      --db /path/to/abm_knowhow.db \\
      --n-synthetic-per-model 6 --seed-base 5000 \\
      --cache-dir /path/to/yahoo_cache
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

from .db import ensure_runs_schema, insert_run
from .fingerprint import fingerprint, hill_tail_index_raw
from . import synthetic
from . import real_refs


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(__file__),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def populate_synthetic(db_path: str, *, n_per_model: int = 6, seed_base: int = 5000,
                       rng_seed: int = 0, verbose: bool = True) -> dict:
    """Run each synthetic injector under LHS-sampled params, fingerprint, store."""
    ensure_runs_schema(db_path)
    rng = np.random.default_rng(rng_seed)
    provenance_static = {"git_commit": _git_commit(), "host": os.uname().nodename,
                         "kind": "synthetic"}
    rows: list[dict] = []
    errors: list[dict] = []
    t_start = time.time()
    n_total = 0
    for name in synthetic.SYNTHETIC_BOUNDS:
        samples = synthetic.sample_params_lhs(name, n_per_model, rng)
        for i, params in enumerate(samples):
            seed = seed_base + n_total
            t0 = time.time()
            try:
                series = synthetic.build_and_run(name, params, seed=seed)
                fp = fingerprint(series, compute_hill=True)
                hraw = hill_tail_index_raw(series)
                rid = insert_run(
                    db_path, model_name=name, params=params, seed=seed,
                    fingerprint_vec=fp, series_kind="returns",
                    series_length=int(len(series)),
                    provenance={**provenance_static,
                                "elapsed_s": round(time.time() - t0, 3)},
                    created_at=dt.datetime.utcnow().isoformat() + "Z",
                    hill_raw=hraw, origin="synthetic",
                )
                rows.append({"id": rid, "model": name, "i": i})
                if verbose:
                    fp_str = " ".join(f"{x:+7.3f}" if np.isfinite(x) else "    nan" for x in fp)
                    print(f"  [synth {n_total+1:>3}] {name:<16s} #{i:>2d} "
                          f"({time.time()-t0:4.1f}s) hill_raw={hraw:5.2f} fp=[{fp_str}]")
            except Exception as exc:
                errors.append({"model": name, "i": i, "params": params,
                               "error": f"{type(exc).__name__}: {exc}"})
                if verbose:
                    print(f"  [synth {n_total+1:>3}] {name:<16s} #{i:>2d} ERROR {exc}",
                          file=sys.stderr)
            n_total += 1
    return {"n_rows_written": len(rows), "n_errors": len(errors),
            "wall_clock_s": round(time.time() - t_start, 1), "errors": errors}


def populate_real(db_path: str, *, cache_dir: str | None = None,
                  verbose: bool = True) -> dict:
    """Fetch real-market closes, derive log-returns, fingerprint, store."""
    ensure_runs_schema(db_path)
    provenance_static = {"git_commit": _git_commit(), "host": os.uname().nodename,
                         "kind": "real_yahoo_chart_v8"}
    rows: list[dict] = []
    errors: list[dict] = []
    t_start = time.time()
    n_total = 0
    try:
        ref_iter = list(real_refs.iter_reference_runs(cache_dir=cache_dir))
    except Exception as exc:
        return {"n_rows_written": 0, "n_errors": 1,
                "errors": [{"error": f"fetch failed: {type(exc).__name__}: {exc}"}],
                "wall_clock_s": round(time.time() - t_start, 1)}
    for entry in ref_iter:
        try:
            series = np.asarray(entry["series"], dtype=np.float64)
            fp = fingerprint(series, compute_hill=True)
            hraw = hill_tail_index_raw(series)
            params = {"sub_id": entry["sub_id"], **entry["source_meta"]}
            rid = insert_run(
                db_path, model_name=entry["label"], params=params, seed=0,
                fingerprint_vec=fp, series_kind="returns",
                series_length=int(len(series)),
                provenance={**provenance_static, "n_obs": entry["n_obs"]},
                created_at=dt.datetime.utcnow().isoformat() + "Z",
                hill_raw=hraw, origin="real",
            )
            rows.append({"id": rid, "label": entry["label"], "sub_id": entry["sub_id"]})
            if verbose:
                fp_str = " ".join(f"{x:+7.3f}" if np.isfinite(x) else "    nan" for x in fp)
                print(f"  [real  {n_total+1:>3}] {entry['label']:<10s} {entry['sub_id']:<10s} "
                      f"n_obs={entry['n_obs']:>5d}  hill_raw={hraw:5.2f}  fp=[{fp_str}]")
        except Exception as exc:
            errors.append({"label": entry["label"], "sub_id": entry["sub_id"],
                           "error": f"{type(exc).__name__}: {exc}"})
            if verbose:
                print(f"  [real ] ERROR on {entry['label']}/{entry['sub_id']}: {exc}",
                      file=sys.stderr)
        n_total += 1
    return {"n_rows_written": len(rows), "n_errors": len(errors),
            "wall_clock_s": round(time.time() - t_start, 1), "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    ap.add_argument("--n-synthetic-per-model", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=5000)
    ap.add_argument("--rng-seed", type=int, default=0)
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--skip-synthetic", action="store_true")
    ap.add_argument("--skip-real", action="store_true")
    args = ap.parse_args()

    out: dict = {}
    if not args.skip_synthetic:
        print("=== SYNTHETIC ===")
        out["synthetic"] = populate_synthetic(
            args.db, n_per_model=args.n_synthetic_per_model,
            seed_base=args.seed_base, rng_seed=args.rng_seed)
    if not args.skip_real:
        print("\n=== REAL ===")
        out["real"] = populate_real(args.db, cache_dir=args.cache_dir)
    print("\n--- summary ---")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "errors"}
                      for k, v in out.items()}, indent=2))
    for kind, v in out.items():
        if v.get("errors"):
            print(f"\n{kind} errors ({len(v['errors'])}):", v["errors"][:3])
    return 0 if all(v.get("n_errors", 0) == 0 for v in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
