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
  - a one-line plain-language reading of that vector
  - a PNG of the return series and its histogram (auto-opened unless --no-plot)

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
import os
import platform
import subprocess
import sys
import tempfile

import numpy as np

from .db import load_runs, update_preference
from .fingerprint import FEATURE_NAMES
from .preference import propose_next_k, Proposal


VALID_LABELS = {"-2": -2.0, "-1": -1.0, "0": 0.0,
                "+1": 1.0, "1": 1.0, "+2": 2.0, "2": 2.0}


def _verbal_summary(fp: np.ndarray) -> str:
    """One-line plain-language reading of the 9-D feature vector.

    Translates the raw numbers into the kind of sentence you'd use to describe
    a market regime — tail thickness, clustering style, momentum, leverage —
    so the user can form a snap judgment without re-doing stylized-facts
    interpretation in their head.
    """
    if np.any(~np.isfinite(fp)):
        return "(NaN in features — fingerprint failed)"
    vol, kurt, hill, acf_ret, acf_short, lev, acf_long, acf_decay, agg_kd = fp
    parts: list[str] = []

    if hill < 3:
        parts.append(f"非常に厚い裾 (Hill α={hill:.1f})")
    elif hill < 5:
        parts.append(f"fat tail (α={hill:.1f})")
    elif hill < 15:
        parts.append(f"穏やかな裾 (α={hill:.1f})")
    else:
        parts.append("ほぼガウス的な裾")

    if acf_short > 0.15 and acf_long > 0.05:
        parts.append("強く長期記憶あり vol clustering")
    elif acf_short > 0.15 and acf_long <= 0.05:
        parts.append("短期のみ vol clustering(指数減衰 = GARCH風)")
    elif acf_short > 0.05:
        parts.append("弱い vol clustering")
    else:
        parts.append("vol clustering なし(IID風)")

    if abs(acf_ret) > 0.10:
        direction = "順張り (momentum)" if acf_ret > 0 else "逆張り (mean reversion)"
        parts.append(f"ラグ1リターン {direction} ρ={acf_ret:+.2f}")

    if lev < -0.08:
        parts.append("leverage effect あり(下落で vol 上昇)")

    if kurt > 30:
        parts.append(f"極端な excess kurtosis ({kurt:.0f})")

    return " / ".join(parts)


def _replay_series(r: dict) -> tuple[np.ndarray, str] | None:
    """Re-simulate / re-load the return series for a row, by origin."""
    origin = r["origin"]
    name = r["model_name"]
    try:
        if origin == "abm":
            from .adapters import build_model, series_for_fingerprint
            model = build_model(name, r["params"])
            result = model.run(seed=r["seed"])
            return series_for_fingerprint(name, result)
        if origin == "synthetic":
            from . import synthetic
            # Pass only the params the generator's bound list expects.
            allowed = set(synthetic.SYNTHETIC_BOUNDS[name].keys())
            params = {k: v for k, v in r["params"].items() if k in allowed}
            series = synthetic.build_and_run(name, params, seed=r["seed"])
            return series, "returns"
        if origin == "real":
            from . import real_refs
            symbol = r["params"]["symbol"]
            years = r["params"].get("years", 6.0)
            ts, closes = real_refs.fetch_yahoo_closes(symbol, years=years, cache_dir=None)
            rets = real_refs.log_returns(closes)
            if "window_start_idx" in r["params"]:
                s = int(r["params"]["window_start_idx"])
                w = int(r["params"]["window_len"])
                rets = rets[s:s + w]
            return rets, "returns"
    except Exception as exc:
        print(f"  ! replay failed: {type(exc).__name__}: {exc}")
        return None
    return None


def _save_and_open_plot(series: np.ndarray, kind: str, r: dict,
                        out_dir: str, auto_open: bool = True) -> str:
    """Save a 2-panel PNG (time series + log-y histogram), open with the OS viewer."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(11, 6))
    n_show = min(2000, len(series))
    axes[0].plot(series[:n_show], linewidth=0.4, color="black")
    axes[0].set_title(f"id={r['id']}  {r['model_name']}  seed={r['seed']}  "
                      f"({kind}, showing first {n_show} of {len(series)})")
    axes[0].set_xlabel("step")
    axes[0].set_ylabel(kind)
    axes[0].grid(alpha=0.3)
    axes[0].axhline(0, color="red", linewidth=0.5, alpha=0.5)

    finite = series[np.isfinite(series)]
    axes[1].hist(finite, bins=80, color="steelblue", edgecolor="black")
    axes[1].set_yscale("log")
    axes[1].set_xlabel(kind)
    axes[1].set_ylabel("count (log)")
    axes[1].set_title("distribution")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"run_{r['id']:04d}_{r['model_name']}.png")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    if auto_open:
        _open_with_os_viewer(path)
    return path


def _open_with_os_viewer(path: str) -> None:
    """Open `path` in the OS default image viewer. Best-effort, no error if it fails."""
    sysname = platform.system()
    try:
        if sysname == "Darwin":
            subprocess.run(["open", path], check=False)
        elif sysname == "Linux":
            subprocess.run(["xdg-open", path], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sysname == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        pass


def _format_row(r: dict, *, extra: str = "", plot_path: str | None = None) -> str:
    fp = r["fingerprint"]
    fp_str = "  ".join(f"{n}={v:+.3f}" if np.isfinite(v) else f"{n}=NaN"
                       for n, v in zip(FEATURE_NAMES, fp))
    params = {k: v for k, v in r["params"].items() if k not in ("kind",)}
    p_short = json.dumps(params, sort_keys=True)
    if len(p_short) > 160:
        p_short = p_short[:157] + "..."
    summary = _verbal_summary(fp)
    out = (f"id={r['id']:>4d}  {r['model_name']:<20s}  origin={r['origin']:<10s}  seed={r['seed']}\n"
           f"  params: {p_short}\n"
           f"  読み: {summary}\n"
           f"  features: {fp_str}\n")
    if plot_path:
        out += f"  plot:   {plot_path}\n"
    if extra:
        out += f"  {extra}\n"
    return out


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


def cold_start(db_path: str, n: int, rng_seed: int = 0, *,
               show_plot: bool = True, plot_dir: str | None = None) -> None:
    """Pick `n` unlabeled rows uniformly at random and run the labelling loop."""
    pool = load_runs(db_path, labeled=False)
    if not pool:
        print("No unlabeled rows. Populate the runs table first.")
        return
    rng = np.random.default_rng(rng_seed)
    picks = rng.choice(len(pool), size=min(n, len(pool)), replace=False)
    if show_plot and plot_dir is None:
        plot_dir = tempfile.mkdtemp(prefix="fp_atlas_label_")
        print(f"plots will be saved to: {plot_dir}\n")
    print(f"cold start: presenting {len(picks)} random unlabeled rows "
          f"(of {len(pool)} total unlabeled).\n"
          f"input grammar: -2 / -1 / 0 / +1 / +2  (s = skip, q = quit)\n")
    n_labeled = 0
    for i, idx in enumerate(picks):
        r = pool[int(idx)]
        print(f"--- [{i+1}/{len(picks)}] ---")
        plot_path = None
        if show_plot:
            replay = _replay_series(r)
            if replay is not None:
                series, kind = replay
                plot_path = _save_and_open_plot(series, kind, r, plot_dir, auto_open=True)
        print(_format_row(r, plot_path=plot_path))
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
               lam_ridge: float, show_plot: bool = True,
               plot_dir: str | None = None) -> None:
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
    if show_plot and plot_dir is None:
        plot_dir = tempfile.mkdtemp(prefix="fp_atlas_label_")
        print(f"  plots will be saved to: {plot_dir}")
    print(f"  proposing top {k} of {len(unlabeled)} unlabeled rows by UCB "
          f"(κ={kappa}, λ_novelty={lam_novelty})\n"
          "  input grammar: -2 / -1 / 0 / +1 / +2  (s = skip, q = quit)\n")
    unl_by_id = {r["id"]: r for r in unlabeled}
    n_labeled = 0
    for i, p in enumerate(proposals):
        r = unl_by_id[p.row_id]
        extra = (f"acquisition={p.acquisition:+.3f}  "
                 f"(μ_pref={p.mu:+.3f}, σ={p.sigma:.3f}, novelty={p.novelty:.3f})")
        plot_path = None
        if show_plot:
            replay = _replay_series(r)
            if replay is not None:
                series, kind = replay
                plot_path = _save_and_open_plot(series, kind, r, plot_dir, auto_open=True)
        print(f"--- [{i+1}/{len(proposals)}] ---")
        print(_format_row(r, extra=extra, plot_path=plot_path))
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
    p_cs.add_argument("--no-plot", action="store_true",
                      help="skip the per-run return-series PNG")
    p_cs.add_argument("--plot-dir", default=None,
                      help="directory to save PNG plots (default: a temp dir)")

    p_nx = sub.add_parser("next", help="propose top-K rows by the UCB acquisition function")
    p_nx.add_argument("--k", type=int, default=5)
    p_nx.add_argument("--kappa", type=float, default=1.0,
                      help="weight on σ in UCB (no effect with constant-σ ridge)")
    p_nx.add_argument("--lam-novelty", type=float, default=1.0,
                      help="weight on novelty term in UCB")
    p_nx.add_argument("--lam-ridge", type=float, default=1.0,
                      help="ridge regularisation strength")
    p_nx.add_argument("--no-plot", action="store_true")
    p_nx.add_argument("--plot-dir", default=None)

    sub.add_parser("summary", help="print labelled-vs-total counts")

    args = ap.parse_args()
    if args.cmd == "cold-start":
        cold_start(args.db, args.n, rng_seed=args.seed,
                   show_plot=not args.no_plot, plot_dir=args.plot_dir)
    elif args.cmd == "next":
        label_next(args.db, args.k, kappa=args.kappa,
                   lam_novelty=args.lam_novelty, lam_ridge=args.lam_ridge,
                   show_plot=not args.no_plot, plot_dir=args.plot_dir)
    elif args.cmd == "summary":
        summary(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
