"""inverse_abm — "today's market is closest to which ABM?"

This is the third nearest-neighbour query promised by the seed README,
sitting alongside the atlas (population embedding) and novelty search
(distance to nearest labeled point). Same operation, different framing:
given a target — a real-market window, an external return CSV, an
existing run id, or the centroid of a model family — find the k ABM runs
whose fingerprints are closest to the target in standardised feature space.

Two entry points:

  nearest_abms_to_target(db, ..., k)
      programmatic search; returns the ranked list.
  compute_real_vs_abm_distance_matrix(db)
      build the full real-vs-ABM matrix for heatmap plotting.

All distances are L2 in the joint standardised feature space of every
valid-fingerprint run in `runs`. Targets fed via `returns` or `returns_csv`
are folded into that population first so the standardisation is consistent.
"""
from __future__ import annotations

import csv
from typing import Any

import numpy as np

from .db import load_runs
from .fingerprint import FEATURE_NAMES, fingerprint, standardize


def _load_returns_from_csv(path: str) -> np.ndarray:
    """Read a one-column CSV (one log-return per line) into a numpy array.

    First row is treated as a header if it can't be parsed as a number.
    Empty lines and lines starting with '#' are skipped.
    """
    vals: list[float] = []
    with open(path) as fh:
        first = True
        for raw in fh:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            # If the line has a comma, take the last column (handles
            # date,return style CSVs).
            tok = s.split(",")[-1].strip()
            try:
                vals.append(float(tok))
            except ValueError:
                if first:
                    first = False
                    continue   # header skipped
                # otherwise raise
                raise
            first = False
    return np.asarray(vals, dtype=np.float64)


def _resolve_target(
    rows: list[dict], *,
    target_run_id: int | None,
    target_model_name: str | None,
    returns: np.ndarray | None,
) -> tuple[np.ndarray, str]:
    """Return (raw_fingerprint, human_label) for the target."""
    if target_run_id is not None:
        row = next((r for r in rows if r["id"] == target_run_id), None)
        if row is None:
            raise KeyError(f"no run with id={target_run_id}")
        return np.asarray(row["fingerprint"], dtype=float), f"run#{target_run_id} ({row['model_name']})"
    if target_model_name is not None:
        matching = [r for r in rows if r["model_name"] == target_model_name]
        if not matching:
            raise KeyError(f"no runs with model_name={target_model_name!r}")
        fps = np.vstack([
            r["fingerprint"] for r in matching
            if np.all(np.isfinite(r["fingerprint"]))
        ])
        return fps.mean(axis=0), f"{target_model_name}(centroid of n={len(matching)})"
    if returns is not None:
        fp = fingerprint(returns, compute_hill=True)
        return fp, f"<external returns n={len(returns)}>"
    raise ValueError(
        "must provide one of: target_run_id / target_model_name / returns"
    )


def nearest_abms_to_target(
    db_path: str, *,
    target_run_id: int | None = None,
    target_model_name: str | None = None,
    returns: np.ndarray | None = None,
    k: int = 5,
    abm_only: bool = True,
) -> dict[str, Any]:
    """Find the k runs closest to `target` in standardised fingerprint space.

    Filters:
      abm_only=True  only consider rows with origin='abm' as candidates
                     (the natural inverse-ABM use case: "given a real market,
                     what ABM should I look at?"). Set False to include
                     real / synthetic rows too.

    Self-match (the target's own run, if target_run_id is given) is always
    excluded from the result.
    """
    all_rows = load_runs(db_path)
    valid_rows = [r for r in all_rows
                  if np.all(np.isfinite(r["fingerprint"]))]
    if not valid_rows:
        raise RuntimeError("no valid fingerprints in runs table")

    target_fp, target_label = _resolve_target(
        valid_rows,
        target_run_id=target_run_id,
        target_model_name=target_model_name,
        returns=returns,
    )

    if not np.all(np.isfinite(target_fp)):
        raise RuntimeError("target fingerprint contains NaN — series too short or degenerate")

    candidates = list(valid_rows)
    if abm_only:
        candidates = [r for r in candidates if r["origin"] == "abm"]
    if target_run_id is not None:
        candidates = [r for r in candidates if r["id"] != target_run_id]
    if not candidates:
        raise RuntimeError("no candidate runs after filtering")

    # Standardise jointly with target so the target lives in the same space.
    fps_raw = np.vstack([r["fingerprint"] for r in candidates] + [target_fp])
    fps_std, mu, sd = standardize(fps_raw)
    target_std = fps_std[-1]
    cand_std = fps_std[:-1]
    diffs = cand_std - target_std
    dists = np.sqrt(np.nansum(diffs ** 2, axis=1))
    order = np.argsort(dists)

    matches = []
    for idx in order[:k]:
        r = candidates[idx]
        matches.append({
            "run_id": int(r["id"]),
            "model_name": r["model_name"],
            "origin": r["origin"],
            "distance": float(dists[idx]),
            "seed": r["seed"],
            "params": r["params"],
            "fingerprint": [round(float(v), 4) for v in r["fingerprint"].tolist()],
        })
    return {
        "target_label": target_label,
        "target_fingerprint": [round(float(v), 4) for v in target_fp.tolist()],
        "feature_names": FEATURE_NAMES,
        "k": int(k),
        "n_candidates_searched": int(len(candidates)),
        "matches": matches,
    }


def compute_real_vs_abm_distance_matrix(db_path: str) -> dict[str, Any]:
    """Per-pair median L2 distance between every real-market run and every
    ABM family (across that family's runs).

    Returns:
      matrix          (n_real, n_abm_families)
      real_labels     row labels = real_run model_names, sorted
      abm_families    col labels = sorted set of ABM model_names
      argmin_per_real list of (real_label, nearest_abm, distance)
    """
    all_rows = load_runs(db_path)
    valid = [r for r in all_rows
             if np.all(np.isfinite(r["fingerprint"]))]
    real_rows = [r for r in valid if r["origin"] == "real"]
    abm_rows = [r for r in valid if r["origin"] == "abm"]
    if not real_rows or not abm_rows:
        raise RuntimeError(
            f"need both real ({len(real_rows)}) and ABM ({len(abm_rows)}) runs"
        )

    fps_all = np.vstack([r["fingerprint"] for r in valid])
    fps_std, mu, sd = standardize(fps_all)
    fp_by_id = {r["id"]: fps_std[i] for i, r in enumerate(valid)}

    real_labels = sorted({r["model_name"] for r in real_rows})
    abm_families = sorted({r["model_name"] for r in abm_rows})

    matrix = np.full((len(real_labels), len(abm_families)), np.nan)
    for i, rl in enumerate(real_labels):
        real_run_fp = fp_by_id[next(r for r in real_rows if r["model_name"] == rl)["id"]]
        for j, fam in enumerate(abm_families):
            fam_fps = np.vstack([fp_by_id[r["id"]]
                                 for r in abm_rows if r["model_name"] == fam])
            diffs = fam_fps - real_run_fp[None, :]
            dists = np.sqrt(np.nansum(diffs ** 2, axis=1))
            matrix[i, j] = float(np.median(dists))

    argmin_per_real = []
    for i, rl in enumerate(real_labels):
        j_min = int(np.argmin(matrix[i]))
        argmin_per_real.append({
            "real": rl,
            "nearest_abm_family": abm_families[j_min],
            "median_distance": round(float(matrix[i, j_min]), 3),
        })
    return {
        "matrix": matrix,
        "real_labels": real_labels,
        "abm_families": abm_families,
        "argmin_per_real": argmin_per_real,
    }


def plot_real_vs_abm_heatmap(db_path: str, out_png: str) -> dict[str, Any]:
    """Render `compute_real_vs_abm_distance_matrix` as an annotated heatmap.

    The nearest ABM per real is circled in red. Median distances are
    written in each cell. The colorbar shows distance magnitude
    (lower = closer = darker in the chosen colormap).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = compute_real_vs_abm_distance_matrix(db_path)
    matrix = data["matrix"]
    real_labels = data["real_labels"]
    abm_families = data["abm_families"]

    fig, ax = plt.subplots(
        figsize=(max(8, len(abm_families) * 1.1),
                 max(5, len(real_labels) * 0.55)),
    )
    im = ax.imshow(matrix, cmap="viridis_r", aspect="auto")

    ax.set_xticks(range(len(abm_families)))
    ax.set_xticklabels(abm_families, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(real_labels)))
    ax.set_yticklabels(real_labels, fontsize=9)

    threshold = float(np.nanmedian(matrix))
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            colour = "white" if val > threshold else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    color=colour, fontsize=7)

    for i in range(matrix.shape[0]):
        j_min = int(np.argmin(matrix[i]))
        ax.scatter([j_min], [i], marker="o", s=180,
                   edgecolor="red", facecolor="none", linewidths=2.0)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("median L2 distance (standardised fingerprint space)")
    ax.set_title("Real markets × ABM families — distance matrix\n"
                 "red circle = nearest ABM family per real period")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return {
        "out_png": out_png,
        "matrix_shape": list(matrix.shape),
        "argmin_per_real": data["argmin_per_real"],
    }
