"""label_cli — terminal labelling loop for the preference-learning stage.

Two modes:

  cold-start  : draw N rows uniformly at random from the unlabeled pool and
                present them in sequence. Use for the very first batch when
                no preference model can be fit yet.

  next        : fit the preference model on the already-labeled rows, score
                every unlabeled row by the UCB acquisition function, present
                the top K. Use after the first cold-start batch.

For each row the CLI prints:
  - row id, model_name, origin, key params, seed
  - the 9-D feature vector (the v4 fingerprint() output)
  - position relative to the labeled centroid and the labeled extremes
  - in `next` mode: predicted preference μ, residual σ, novelty score, UCB

Input grammar (one keystroke or short token, then Enter):
  -2, -1, 0, +1 (or 1), +2 (or 2)   :  Likert preference, written to runs.preference_label
  s                                  :  skip (no label written)
  q                                  :  quit the loop

Usage:
  uv run python -m fingerprint_atlas.label_cli --db /path/to/db.db cold-start --n 10
  uv run python -m fingerprint_atlas.label_cli --db /path/to/db.db next --k 5
  uv run python -m fingerprint_atlas.label_cli --db /path/to/db.db summary
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from .db import load_runs, update_preference
from .fingerprint import FEATURE_NAMES
from .preference import propose_next_k, Proposal


VALID_LABELS = {"-2": -2.0, "-1": -1.0, "0": 0.0,
                "+1": 1.0, "1": 1.0, "+2": 2.0, "2": 2.0}


def _format_row(r: dict, *, extra: str = "") -> str:
    fp = r["fingerprint"]
    fp_str = "  ".join(f"{n}={v:+.3f}" if np.isfinite(v) else f"{n}=NaN"
                       for n, v in zip(FEATURE_NAMES, fp))
    params = {k: v for k, v in r["params"].items() if k not in ("kind",)}
    p_short = json.dumps(params, sort_keys=True)
    if len(p_short) > 160:
        p_short = p_short[:157] + "..."
    return (f"id={r['id']:>4d}  {r['model_name']:<20s}  origin={r['origin']:<10s}  seed={r['seed']}\n"
            f"  params: {p_short}\n"
            f"  features: {fp_str}\n"
            + (f"  {extra}\n" if extra else ""))


def _read_label(prompt: str) -> tuple[str, float | None]:
    """Return (verdict, label).
    verdict in {'label', 'skip', 'quit'}.
    """
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return "quit", None
        if raw in {"q", "quit", "exit"}:
            return "quit", None
        if raw in {"s", "skip", ""}:
            return "skip", None
        if raw in VALID_LABELS:
            return "label", VALID_LABELS[raw]
        print(f"  ?  expected one of -2 -1 0 +1 +2 (or s/q), got {raw!r}")


def cold_start(db_path: str, n: int, rng_seed: int = 0) -> None:
    """Pick `n` unlabeled rows uniformly at random and run the labelling loop."""
    pool = load_runs(db_path, labeled=False)
    if not pool:
        print("No unlabeled rows. Populate the runs table first.")
        return
    rng = np.random.default_rng(rng_seed)
    picks = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    print(f"cold start: presenting {len(picks)} random unlabeled rows "
          f"(of {len(pool)} total unlabeled).\n"
          f"input grammar: -2 / -1 / 0 / +1 / +2  (s = skip, q = quit)\n")
    n_labeled = 0
    for i, idx in enumerate(picks):
        r = pool[int(idx)]
        print(f"--- [{i+1}/{len(picks)}] ---")
        print(_format_row(r))
        verdict, label = _read_label("  preference > ")
        if verdict == "quit":
            print(f"stopped early; {n_labeled} labels written.")
            return
        if verdict == "skip":
            continue
        update_preference(db_path, r["id"], label)
        n_labeled += 1
        print(f"  -> wrote preference_label={label} for id={r['id']}\n")
    print(f"done: {n_labeled} labels written.")


def label_next(db_path: str, k: int, *, kappa: float, lam_novelty: float,
               lam_ridge: float) -> None:
    """Fit the preference model, propose the top-k unlabeled rows by UCB."""
    labeled = load_runs(db_path, labeled=True)
    unlabeled = load_runs(db_path, labeled=False)
    if not unlabeled:
        print("No unlabeled rows left to propose.")
        return
    proposals, model = propose_next_k(
        labeled, unlabeled, k=k,
        lam_ridge=lam_ridge, kappa=kappa, lam_novelty=lam_novelty,
    )
    if model is None:
        print(f"  cold start ({len(labeled)} labels < 2 needed for ridge fit); "
              "ranking by pure novelty.")
    else:
        print(f"  fit ridge on {len(labeled)} labels, residual σ={model.residual_std_:.3f}")
    print(f"  proposing top {k} of {len(unlabeled)} unlabeled rows by UCB "
          f"(κ={kappa}, λ_novelty={lam_novelty})\n"
          "  input grammar: -2 / -1 / 0 / +1 / +2  (s = skip, q = quit)\n")
    unl_by_id = {r["id"]: r for r in unlabeled}
    n_labeled = 0
    for i, p in enumerate(proposals):
        r = unl_by_id[p.row_id]
        extra = (f"acquisition={p.acquisition:+.3f}  "
                 f"(μ_pref={p.mu:+.3f}, σ={p.sigma:.3f}, novelty={p.novelty:.3f})")
        print(f"--- [{i+1}/{len(proposals)}] ---")
        print(_format_row(r, extra=extra))
        verdict, label = _read_label("  preference > ")
        if verdict == "quit":
            print(f"stopped early; {n_labeled} labels written.")
            return
        if verdict == "skip":
            continue
        update_preference(db_path, r["id"], label)
        n_labeled += 1
        print(f"  -> wrote preference_label={label} for id={r['id']}\n")
    print(f"done: {n_labeled} labels written.")


def summary(db_path: str) -> None:
    """Print a small overview of how many rows are labeled and by which family."""
    all_rows = load_runs(db_path)
    labeled = [r for r in all_rows if r["preference_label"] is not None]
    by_family: dict[str, list[float]] = {}
    for r in labeled:
        by_family.setdefault(r["model_name"], []).append(r["preference_label"])
    print(f"total runs: {len(all_rows)}")
    print(f"labeled   : {len(labeled)}")
    if labeled:
        print("per-family label counts and mean:")
        for fam in sorted(by_family):
            vals = by_family[fam]
            print(f"  {fam:<20s}  n={len(vals):>2d}  mean={np.mean(vals):+.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cs = sub.add_parser("cold-start", help="draw N random unlabeled rows for the first batch")
    p_cs.add_argument("--n", type=int, default=10)
    p_cs.add_argument("--seed", type=int, default=0)

    p_nx = sub.add_parser("next", help="propose top-K rows by the UCB acquisition function")
    p_nx.add_argument("--k", type=int, default=5)
    p_nx.add_argument("--kappa", type=float, default=1.0,
                      help="weight on σ in UCB (no effect with constant-σ ridge)")
    p_nx.add_argument("--lam-novelty", type=float, default=1.0,
                      help="weight on novelty term in UCB")
    p_nx.add_argument("--lam-ridge", type=float, default=1.0,
                      help="ridge regularisation strength")

    sub.add_parser("summary", help="print labelled-vs-total counts")

    args = ap.parse_args()
    if args.cmd == "cold-start":
        cold_start(args.db, args.n, rng_seed=args.seed)
    elif args.cmd == "next":
        label_next(args.db, args.k, kappa=args.kappa,
                   lam_novelty=args.lam_novelty, lam_ridge=args.lam_ridge)
    elif args.cmd == "summary":
        summary(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
