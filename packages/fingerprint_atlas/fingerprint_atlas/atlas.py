"""atlas — read runs from the DB, build the fingerprint geometry, validate.

Two artefacts:

  1. `validation_gate(rows)`  — pure numbers. The validation question is:
     does the fingerprint actually separate the 8 model families? Concretely:
     mean intra-model distance < mean inter-model distance? Silhouette > 0?
  2. `plot_atlas(rows, out_png)` — 2-D PCA layout coloured by model. The
     pretty picture, but only after the numbers say it's worth looking at.

If the gate fails (numbers say "no separation"), fix `fingerprint.py` /
`adapters.MODEL_BOUNDS` BEFORE building anything on top. The seed README is
explicit: this is the foundation; if it's sand, every layer above is sand too.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import numpy as np

from .db import collect_population, load_runs
from .fingerprint import FEATURE_NAMES, distance_matrix, standardize


def _pca_2d(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Plain SVD-based PCA -> (xy, explained_var_ratio)."""
    xc = x - x.mean(axis=0)
    u, s, vt = np.linalg.svd(xc, full_matrices=False)
    explained = (s ** 2) / max(1, (xc.shape[0] - 1))
    total = explained.sum()
    ratio = explained / total if total > 0 else np.zeros_like(explained)
    return xc @ vt[:2].T, ratio


def validation_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the separation numbers.

    Returns dict with:
      n_runs, n_models, n_per_model,
      feature_means / stds (raw),
      mean_intra, mean_inter, separation_ratio (inter / intra; > 1 is good),
      silhouette_macro (mean of per-model silhouette; > 0 is good),
      per_model_centroids (in standardized space).
    """
    fps_raw, kept = collect_population(rows)
    if len(kept) < 4:
        return {"ok": False, "reason": f"only {len(kept)} valid rows"}

    labels = np.array([r["model_name"] for r in kept])
    fps_std, mu, sd = standardize(fps_raw)
    D = distance_matrix(fps_std)
    np.fill_diagonal(D, np.nan)

    intra_vals: list[float] = []
    inter_vals: list[float] = []
    sils: list[float] = []
    for i in range(len(kept)):
        same = (labels == labels[i]) & (np.arange(len(kept)) != i)
        diff = labels != labels[i]
        if not same.any() or not diff.any():
            continue
        a_i = float(np.nanmean(D[i, same]))
        # mean over other clusters' mean distances; then min (silhouette b_i)
        other_clusters = [lab for lab in set(labels) if lab != labels[i]]
        b_means = [float(np.nanmean(D[i, labels == lab])) for lab in other_clusters]
        b_i = float(min(b_means))
        intra_vals.append(a_i)
        inter_vals.append(float(np.nanmean(D[i, diff])))
        sils.append((b_i - a_i) / max(a_i, b_i, 1e-12))

    counts = defaultdict(int)
    for lab in labels:
        counts[lab] += 1

    centroids: dict[str, list[float]] = {}
    for lab in sorted(set(labels)):
        mask = labels == lab
        centroids[lab] = np.nanmean(fps_std[mask], axis=0).round(4).tolist()

    intra = float(np.mean(intra_vals)) if intra_vals else float("nan")
    inter = float(np.mean(inter_vals)) if inter_vals else float("nan")
    sil = float(np.mean(sils)) if sils else float("nan")
    return {
        "ok": np.isfinite(sil) and sil > 0 and inter > intra,
        "n_runs": int(len(kept)),
        "n_models": int(len(counts)),
        "n_per_model": dict(counts),
        "feature_names": FEATURE_NAMES,
        "feature_means_raw": [round(float(v), 4) for v in mu],
        "feature_stds_raw": [round(float(v), 4) for v in sd],
        "mean_intra_distance": round(intra, 4),
        "mean_inter_distance": round(inter, 4),
        "separation_ratio": round(inter / intra, 4) if intra > 0 else float("nan"),
        "silhouette_macro": round(sil, 4),
        "centroids_standardized": centroids,
    }


_ORIGIN_MARKER = {"abm": "o", "synthetic": "^", "real": "*"}
_ORIGIN_SIZE = {"abm": 60, "synthetic": 130, "real": 240}


def _display_family(model_name: str) -> str:
    """Collapse `real_spx_p3` -> `real_spx`, `real_btc_full` -> `real_btc`.

    Periods become point-shape variations within the same colour, so the
    eye reads "the real S&P is multiple regimes" rather than 12 separate
    legend entries.
    """
    if model_name.startswith("real_spx"):
        return "real_spx"
    if model_name.startswith("real_btc"):
        return "real_btc"
    return model_name


def plot_atlas(rows: list[dict[str, Any]], out_png: str, title: str = "ABM fingerprint atlas") -> dict:
    """Draw the 2-D PCA scatter coloured by model family, save to PNG, return summary.

    Marker shape encodes `origin`:
      - circles  (o)  = ABM family    (abm)
      - triangles (^) = synthetic injector (Cont-outside probe)
      - stars     (*) = real market window (ground-truth landmark)

    Real periods (`real_spx_p0..p4`, `real_spx_full`, etc.) collapse into one
    colour per market so the regime spread within a market is visible.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fps_raw, kept = collect_population(rows)
    if len(kept) < 3:
        raise RuntimeError(f"only {len(kept)} valid rows, cannot plot")
    labels = np.array([r["model_name"] for r in kept])
    families = np.array([_display_family(lab) for lab in labels])
    origins = np.array([r.get("origin", "abm") for r in kept])
    fps_std, _, _ = standardize(fps_raw)
    xy, ratio = _pca_2d(fps_std)

    fig, ax = plt.subplots(figsize=(12, 8))
    uniq = sorted(set(families))
    cmap = plt.colormaps.get_cmap("tab20").resampled(max(len(uniq), 2))
    for k, fam in enumerate(uniq):
        m = families == fam
        origin = origins[m][0] if m.any() else "abm"
        marker = _ORIGIN_MARKER.get(origin, "o")
        size = _ORIGIN_SIZE.get(origin, 60)
        ax.scatter(xy[m, 0], xy[m, 1], s=size, alpha=0.78, edgecolor="black",
                   linewidth=0.5, color=cmap(k), marker=marker,
                   label=f"{fam} (n={int(m.sum())}, {origin})")
        # Annotate real-period points with the period id so spread is readable
        if origin == "real":
            for idx in np.where(m)[0]:
                pid = labels[idx].split("_")[-1]   # 'p0', 'full', ...
                ax.annotate(pid, (xy[idx, 0], xy[idx, 1]), fontsize=6,
                            xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel(f"PC1  ({100*ratio[0]:.1f}% var)")
    ax.set_ylabel(f"PC2  ({100*ratio[1]:.1f}% var)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8, frameon=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return {
        "out_png": out_png,
        "n_runs": int(len(kept)),
        "n_families_collapsed": int(len(uniq)),
        "pc1_var": round(float(ratio[0]), 4),
        "pc2_var": round(float(ratio[1]), 4),
    }


def plot_feature_box(rows: list[dict[str, Any]], out_png: str) -> dict:
    """Per-model boxplot of each raw fingerprint feature.

    Used to *see* which features carry the separation. If a feature is flat
    across all models, it's dead weight and should be dropped/reweighted.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fps_raw, kept = collect_population(rows)
    if len(kept) < 3:
        raise RuntimeError(f"only {len(kept)} valid rows, cannot plot")
    labels = np.array([r["model_name"] for r in kept])
    uniq = sorted(set(labels))

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharey=False)
    axes = axes.flatten()
    for k, feat in enumerate(FEATURE_NAMES):
        ax = axes[k]
        data = [fps_raw[labels == lab, k] for lab in uniq]
        ax.boxplot(data, tick_labels=[lab[:10] for lab in uniq])
        ax.set_title(feat, fontsize=10)
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
            tick.set_fontsize(7)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Per-model distribution of each fingerprint feature (raw)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return {"out_png": out_png, "models": uniq, "n_features": len(FEATURE_NAMES)}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    ap.add_argument("--atlas-png", default=None)
    ap.add_argument("--feature-png", default=None)
    ap.add_argument("--gate-json", default=None)
    args = ap.parse_args()

    rows = load_runs(args.db)
    gate = validation_gate(rows)
    print(json.dumps(gate, indent=2, default=str))
    if args.gate_json:
        with open(args.gate_json, "w") as fh:
            json.dump(gate, fh, indent=2, default=str)
    if args.atlas_png:
        print("plot_atlas ->", plot_atlas(rows, args.atlas_png))
    if args.feature_png:
        print("plot_feature_box ->", plot_feature_box(rows, args.feature_png))
    return 0 if gate.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
