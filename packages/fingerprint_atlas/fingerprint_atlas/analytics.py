"""analytics — visualise the LLM's predict-then-execute track record.

Three plots, all dumped to a directory as PNGs:

  prediction_error_over_time.png
      Scatter of prediction_error vs proposal_id (proxy for time),
      coloured by llm_model. Lets you see "is the LLM getting better
      as the literature DB grows / prompts improve?"

  prediction_error_by_family.png
      Box / strip plot of prediction_error grouped by target_model.
      Surfaces which families the LLM understands best.

  novelty_calibration.png
      Scatter of predicted_novelty_distance vs actual_novelty_distance
      with y=x reference. Tells you whether the LLM over- or
      under-estimates how unusual its proposals are.

This is the "learning curve" half of the loop: with every executed
proposal, the LLM's calibration becomes measurable.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .db import load_proposals


def _summary_stats(executed: list[dict]) -> dict[str, Any]:
    errors = np.array(
        [p["prediction_error"] for p in executed if p["prediction_error"] is not None]
    )
    return {
        "n_executed": int(len(executed)),
        "n_with_prediction_error": int(len(errors)),
        "median_prediction_error": float(np.median(errors)) if errors.size else None,
        "mean_prediction_error": float(np.mean(errors)) if errors.size else None,
        "p10_prediction_error": float(np.quantile(errors, 0.10)) if errors.size else None,
        "p90_prediction_error": float(np.quantile(errors, 0.90)) if errors.size else None,
    }


def plot_prediction_error_over_time(db_path: str, out_png: str) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [p for p in load_proposals(db_path, status="executed")
            if p["prediction_error"] is not None]
    if not rows:
        raise RuntimeError("no executed proposals with prediction_error")

    fig, ax = plt.subplots(figsize=(10, 5))
    models = sorted(set(r["llm_model"] for r in rows))
    cmap = plt.colormaps.get_cmap("tab10").resampled(max(len(models), 2))
    for k, model in enumerate(models):
        sub = [r for r in rows if r["llm_model"] == model]
        xs = [r["id"] for r in sub]
        ys = [r["prediction_error"] for r in sub]
        ax.scatter(xs, ys, s=70, color=cmap(k), alpha=0.85,
                   edgecolor="black", linewidth=0.4, label=model)
    ax.set_xlabel("proposal id (≈ time)")
    ax.set_ylabel("prediction_error (L2 in 9-D standardised fp space)")
    ax.set_title(f"LLM prediction error per executed proposal "
                 f"(n={len(rows)})")
    ax.grid(True, alpha=0.3)
    ax.axhline(2.0, color="grey", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    return {"out_png": out_png, "n_runs": len(rows), "n_models": len(models)}


def plot_prediction_error_by_family(db_path: str, out_png: str) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [p for p in load_proposals(db_path, status="executed")
            if p["prediction_error"] is not None]
    if not rows:
        raise RuntimeError("no executed proposals with prediction_error")

    families = sorted(set(r["target_model"] for r in rows))
    data = [[r["prediction_error"] for r in rows if r["target_model"] == fam]
            for fam in families]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(data, tick_labels=families, showmeans=True,
               meanline=True, widths=0.55)
    # add individual points on top of the boxes
    for i, fam_errors in enumerate(data, start=1):
        x_jitter = np.random.default_rng(42 + i).normal(loc=i, scale=0.06,
                                                         size=len(fam_errors))
        ax.scatter(x_jitter, fam_errors, color="black", s=20, alpha=0.6)
    ax.set_ylabel("prediction_error (L2 standardised)")
    ax.set_title(f"prediction error by target model (n={len(rows)})")
    ax.grid(True, axis="y", alpha=0.3)
    for tick in ax.get_xticklabels():
        tick.set_rotation(30)
        tick.set_fontsize(8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    return {"out_png": out_png, "n_families": len(families)}


def plot_novelty_calibration(db_path: str, out_png: str) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [p for p in load_proposals(db_path, status="executed")
            if (p["predicted_novelty_distance"] is not None
                and p["actual_novelty_distance"] is not None)]
    if not rows:
        raise RuntimeError("no executed proposals with both novelty values")

    fig, ax = plt.subplots(figsize=(7, 7))
    models = sorted(set(r["llm_model"] for r in rows))
    cmap = plt.colormaps.get_cmap("tab10").resampled(max(len(models), 2))
    for k, model in enumerate(models):
        sub = [r for r in rows if r["llm_model"] == model]
        xs = [r["predicted_novelty_distance"] for r in sub]
        ys = [r["actual_novelty_distance"] for r in sub]
        ax.scatter(xs, ys, s=70, color=cmap(k), alpha=0.85,
                   edgecolor="black", linewidth=0.4, label=model)
        for r in sub:
            ax.annotate(str(r["id"]),
                        (r["predicted_novelty_distance"],
                         r["actual_novelty_distance"]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points")
    lo = min(ax.get_xlim()[0], ax.get_ylim()[0], 0)
    hi = max(ax.get_xlim()[1], ax.get_ylim()[1], 1)
    ax.plot([lo, hi], [lo, hi], color="grey", linestyle="--",
            linewidth=0.8, alpha=0.5, label="y = x (perfect calibration)")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("LLM-predicted novelty distance")
    ax.set_ylabel("measured novelty distance (post-execute)")
    ax.set_title("LLM novelty calibration")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    return {"out_png": out_png, "n_runs": len(rows)}


def summarize(db_path: str) -> dict[str, Any]:
    """Return a dict with executed-proposal stats; safe to print as JSON."""
    rows = load_proposals(db_path, status="executed")
    summary: dict[str, Any] = {"n_proposals_total": len(load_proposals(db_path))}
    summary.update(_summary_stats(rows))
    if rows:
        by_model: dict[str, list[float]] = {}
        for r in rows:
            if r["prediction_error"] is not None:
                by_model.setdefault(r["llm_model"], []).append(r["prediction_error"])
        summary["by_llm_model"] = {
            m: {"n": len(v),
                "median_pred_err": round(float(np.median(v)), 3),
                "mean_pred_err": round(float(np.mean(v)), 3)}
            for m, v in by_model.items()
        }
    return summary
