"""S3 Windows 側 step 2: 4 条件 100 trial の full summary + interaction + lifetime.

S3 plan v2 §3.5 / §3.7 / §3.8 / §3.9 / §3.10:
  - 4 条件 × 全指標 mean ± 95% CI table (§3.10 tab_S3_full_summary.csv)
  - Pooled bin_var_slope の 4 条件比較 + interaction value (§3.7、v2 修正 1)
  - 4 条件 interaction (full / first half / second half) × 5 主 + plan B (§3.9)
  - Lifetime distribution + 仮説 A primary evidence flag (§3.8、v2 修正 2)
  - Figures (3 種)
  - README.md 追記
  - logs/S3_summary_for_diff.json

Run (Windows、combine_ensemble_summaries.py の後):
  cd experiments/YH006_1
  python -m code.aggregate_full_summary
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from analysis import bin_variance_slope_pooled  # noqa: E402
from config import AGG_PARAMS, LOB_PARAMS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS  # noqa: E402
from stats import bootstrap_ci  # noqa: E402

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

ALL_CONDS = ["C0u", "C0p", "C2", "C3"]
AGG_CONDS = ["C0u", "C0p"]
LOB_CONDS = ["C2", "C3"]

MAIN_METRICS = [
    "rho_pearson", "rho_spearman", "tau_kendall",
    "rho_p_first_half", "rho_p_second_half",
    "rho_s_first_half", "rho_s_second_half",
    "bin_var_slope", "q90_q10_slope_diff",
    "corr_w_init_h", "skew_high_minus_low", "hill_alpha",
    "lifetime_median", "lifetime_p90",
    "wealth_persistence_rho", "forced_retire_rate",
]
INTERACTION_METRICS = [
    "rho_pearson", "rho_spearman", "tau_kendall",
    "bin_var_slope", "q90_q10_slope_diff",
]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S3-full")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S3_aggregate_full.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Pooled bin_var_slope 4 条件 (§3.7、v2 修正 1)
# ---------------------------------------------------------------------------

def compute_pooled_bin_var_4cond(
    seeds: List[int], logger: logging.Logger,
) -> Dict[str, float]:
    """4 条件すべて pooled bin_var_slope を計算."""
    pooled: Dict[str, float] = {}
    for cond in ALL_CONDS:
        cond_dir = DATA_DIR / cond
        rt_dfs = []
        for seed in seeds:
            p = cond_dir / f"trial_{seed:04d}.parquet"
            if p.exists():
                rt_dfs.append(pd.read_parquet(p, columns=["horizon", "delta_g"]))
        if not rt_dfs:
            logger.warning(f"[pooled] {cond}: no trial parquet found, skipping")
            pooled[cond] = float("nan")
            continue
        pooled_rt = pd.concat(rt_dfs, ignore_index=True)
        pooled[cond] = bin_variance_slope_pooled(pooled_rt, K=15)
        logger.info(
            f"[pooled] {cond}: pooled n_rt={len(pooled_rt):,} "
            f"bin_var_slope_pooled={pooled[cond]:+.4f}"
        )
    return pooled


def classify_bin_var_pattern(
    pooled: Dict[str, float],
    lob_diff_ci: Tuple[float, float, float],
) -> Tuple[str, str]:
    """§3.7 v2 修正 1: interaction 値で α/β/γ/δ pattern 判定.

    Returns: (pattern_name, description)
    """
    agg_diff = pooled["C0p"] - pooled["C0u"]
    lob_diff_mean, lob_lo, lob_hi = lob_diff_ci
    interaction = lob_diff_mean - agg_diff

    if lob_lo <= 0.0 <= lob_hi:
        return ("δ", f"LOB diff CI [{lob_lo:+.3f}, {lob_hi:+.3f}] が 0 を跨ぐ "
                f"→ 判定保留、S1-secondary の bootstrap CI で再判定")
    same_sign = (lob_diff_mean > 0) == (agg_diff > 0)
    same_order = abs(lob_diff_mean) >= 0.5 * abs(agg_diff) and abs(lob_diff_mean) <= 2.0 * abs(agg_diff)
    if same_sign and same_order:
        return ("α", f"LOB diff = {lob_diff_mean:+.3f} ≈ aggregate diff = {agg_diff:+.3f} "
                f"(interaction = {interaction:+.3f}) → 世界依存性なし、F1 機構は world-invariant")
    if not same_sign and abs(interaction) >= 0.2:
        return ("β", f"LOB diff = {lob_diff_mean:+.3f} が aggregate diff = {agg_diff:+.3f} と反転 "
                f"(interaction = {interaction:+.3f}) → 世界依存性 大、F1 機構解明 primary signal")
    return ("γ", f"LOB diff = {lob_diff_mean:+.3f} は aggregate diff = {agg_diff:+.3f} と同符号だが桁違い "
            f"(interaction = {interaction:+.3f}) → 世界依存性 中、F1 機構が world-modulated")


def lob_diff_bootstrap(
    df: pd.DataFrame, metric: str, n_resample: int = 10_000,
    rng: np.random.Generator = None,
) -> Tuple[float, float, float]:
    """trial-level (cond=C2, cond=C3) から (C3 trial - C2 trial) の bootstrap CI."""
    if rng is None:
        rng = np.random.default_rng(0)
    c2 = df[df["cond"] == "C2"][metric].dropna().to_numpy(dtype=np.float64)
    c3 = df[df["cond"] == "C3"][metric].dropna().to_numpy(dtype=np.float64)
    if c2.size == 0 or c3.size == 0:
        return (float("nan"),) * 3
    n = min(c2.size, c3.size)
    diffs = c3[:n] - c2[:n]
    return bootstrap_ci(diffs, n_resample=n_resample, ci=0.95, rng=rng)


# ---------------------------------------------------------------------------
# Lifetime evidence (§3.8、v2 修正 2)
# ---------------------------------------------------------------------------

def lifetime_evidence_table(
    df: pd.DataFrame, seeds: List[int], logger: logging.Logger,
) -> pd.DataFrame:
    """4 条件 lifetime distribution + 仮説 A primary evidence 判定 (§3.8、v2 修正 2).

    Mac stage の Yuito 判断 (2026-04-30) で **主指標切替** 確定:
      - 主指標 1: p25 lifetime (右端 censoring に頑健、tail composition 差を捕捉)
      - 主指標 2: conditional median (uncensored sample のみ、退場 agent の中央値)
      - 主指標 3: censoring 率 (sample-level、sim 終了時生存 sample の比率)
      - 補助:    median, p90 (T 張り付きで discrimination 不能、参考値)

    censoring 率は `lifetimes_*.parquet` の `censored` 列から sample-level で計算 (trial-level
    の median > T/2 件数とは別物)。
    """
    rows = []
    for cond in ALL_CONDS:
        sub = df[df["cond"] == cond]
        if len(sub) == 0:
            continue
        T_cond = AGG_PARAMS["T"] if cond in AGG_CONDS else LOB_PARAMS["main_steps"]
        median_arr = sub["lifetime_median"].dropna().to_numpy()
        p90_arr = sub["lifetime_p90"].dropna().to_numpy()
        n_above = int((median_arr > T_cond / 2).sum()) if median_arr.size else 0
        # 主指標 (3): conditional median, p25, censoring 率 — sample-level で取得
        cond_median, p25, censoring_rate, n_total_samples = (
            _read_conditional_lifetime_stats(cond, seeds, T_cond)
        )
        rows.append({
            "cond": cond,
            "T": T_cond,
            "n_trials": len(sub),
            # --- primary indicators (Yuito 2026-04-30 mandate) ---
            "p25_pooled": p25,
            "conditional_median": cond_median,
            "censoring_rate": censoring_rate,
            # --- auxiliary (T 張り付きで discrimination 不能、参考のみ) ---
            "lifetime_median_mean": float(np.mean(median_arr)) if median_arr.size else float("nan"),
            "lifetime_p90_mean": float(np.mean(p90_arr)) if p90_arr.size else float("nan"),
            "n_above_T_half": n_above,
            "n_total_samples": n_total_samples,
        })
        logger.info(
            f"[lifetime] {cond} T={T_cond}: "
            f"PRIMARY p25={p25:.1f}, cond_median={cond_median:.1f}, "
            f"censoring={censoring_rate:.1%} (n_samples={n_total_samples}); "
            f"AUX median_mean={rows[-1]['lifetime_median_mean']:.1f}, "
            f"n_above_T/2={n_above}/{len(sub)}"
        )
    return pd.DataFrame(rows)


def _read_conditional_lifetime_stats(
    cond: str, seeds: List[int], T_cond: int,
) -> Tuple[float, float, float, int]:
    """Lifetime parquet から conditional median (censored 除外) + p25 + censoring 率を計算.

    Returns: (conditional_median, p25_pooled, censoring_rate, n_total_samples)
    """
    cond_dir = DATA_DIR / cond
    all_lifetimes: List[float] = []
    all_censored: List[bool] = []
    for seed in seeds:
        p = cond_dir / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt_df = pd.read_parquet(p)
        if len(lt_df) == 0:
            continue
        all_lifetimes.extend(lt_df["lifetime"].tolist())
        if "censored" in lt_df.columns:
            all_censored.extend(lt_df["censored"].tolist())
        else:
            all_censored.extend([False] * len(lt_df))
    if not all_lifetimes:
        return (float("nan"), float("nan"), float("nan"), 0)
    arr = np.array(all_lifetimes, dtype=np.float64)
    cens = np.array(all_censored, dtype=bool)
    p25 = float(np.percentile(arr, 25))
    censoring_rate = float(cens.mean()) if cens.size else float("nan")
    if (~cens).sum() > 0:
        cond_median = float(np.median(arr[~cens]))
    else:
        cond_median = float("nan")
    return (cond_median, p25, censoring_rate, int(arr.size))


def hypothesis_A_evidence(lifetime_df: pd.DataFrame) -> Tuple[bool, str]:
    """§3.8 v2 修正 2 + Mac stage Yuito mandate: 仮説 A 中間予測 primary evidence 判定.

    判定軸 (Yuito 2026-04-30 mandate に従い):
      - aggregate (T=50000): censoring_rate ≪ 1、退場 dynamics が active
      - LOB (T=1500): censoring_rate >> aggregate なら friction が turnover を抑制
      - C2 vs C3 の p25 対比で wealth-tail composition が persist しているか確認

    primary evidence 確定基準: LOB の **trial-level median > T/2 件数** が 50/100 以上、
    または **sample-level censoring_rate が aggregate より顕著に高い** (差 > 0.5)。
    """
    agg_cens = lifetime_df[lifetime_df["cond"].isin(AGG_CONDS)]["censoring_rate"].mean()
    lob_cens = lifetime_df[lifetime_df["cond"].isin(LOB_CONDS)]["censoring_rate"].mean()
    cens_gap = lob_cens - agg_cens
    n_lob_trials = sum(
        int(r["n_trials"]) for _, r in lifetime_df.iterrows()
        if r["cond"] in LOB_CONDS
    )
    n_lob_above = sum(
        int(r["n_above_T_half"]) for _, r in lifetime_df.iterrows()
        if r["cond"] in LOB_CONDS
    )
    is_evidence = (n_lob_above >= n_lob_trials // 2) or (cens_gap > 0.5)

    # tail composition 対比 (C2 vs C3 p25)
    c2 = lifetime_df[lifetime_df["cond"] == "C2"]
    c3 = lifetime_df[lifetime_df["cond"] == "C3"]
    p25_contrast = ""
    if len(c2) and len(c3):
        c2_p25 = float(c2["p25_pooled"].iloc[0])
        c3_p25 = float(c3["p25_pooled"].iloc[0])
        p25_contrast = f" / C2 p25={c2_p25:.1f} vs C3 p25={c3_p25:.1f}"

    if is_evidence:
        msg = (f"LOB censoring_rate={lob_cens:.1%} vs agg {agg_cens:.1%} "
               f"(gap={cens_gap:+.1%}), median>T/2 trial 件数={n_lob_above}/{n_lob_trials}"
               f"{p25_contrast} "
               f"→ **仮説 A 中間予測の primary evidence 確定** (LOB friction が agent turnover を抑制、tail composition persist)")
    else:
        msg = (f"LOB censoring_rate={lob_cens:.1%} vs agg {agg_cens:.1%} "
               f"(gap={cens_gap:+.1%}), median>T/2 trial 件数={n_lob_above}/{n_lob_trials}"
               f"{p25_contrast} "
               f"→ 補助 mechanism signal にとどまる (primary evidence 基準未達)")
    return (is_evidence, msg)


# ---------------------------------------------------------------------------
# Interaction (§3.9)
# ---------------------------------------------------------------------------

def compute_interactions(
    df: pd.DataFrame, n_resample: int = 10_000,
) -> pd.DataFrame:
    """(C3 - C2) - (C0p - C0u) interaction with bootstrap CI per metric."""
    rng = np.random.default_rng(0)
    rows = []
    for metric in INTERACTION_METRICS:
        c0u = df[df["cond"] == "C0u"][metric].dropna().to_numpy()
        c0p = df[df["cond"] == "C0p"][metric].dropna().to_numpy()
        c2 = df[df["cond"] == "C2"][metric].dropna().to_numpy()
        c3 = df[df["cond"] == "C3"][metric].dropna().to_numpy()
        n = min(c0u.size, c0p.size, c2.size, c3.size)
        if n == 0:
            rows.append({"metric": metric, "interaction_mean": float("nan"),
                         "ci_lo": float("nan"), "ci_hi": float("nan"), "n": 0})
            continue
        # interaction per trial pair
        agg_diff = c0p[:n] - c0u[:n]
        lob_diff = c3[:n] - c2[:n]
        inter = lob_diff - agg_diff
        m, lo, hi = bootstrap_ci(inter, n_resample=n_resample, ci=0.95, rng=rng)
        rows.append({
            "metric": metric, "interaction_mean": m,
            "ci_lo": lo, "ci_hi": hi, "n": int(n),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Full summary table (§3.10)
# ---------------------------------------------------------------------------

def write_full_summary(
    df: pd.DataFrame, pooled_bin_var: Dict[str, float],
    out_path: Path, logger: logging.Logger,
) -> None:
    rng = np.random.default_rng(0)
    rows = []
    for cond in ALL_CONDS:
        sub = df[df["cond"] == cond]
        for col in MAIN_METRICS:
            vals = sub[col].dropna().to_numpy(dtype=np.float64)
            if vals.size == 0:
                rows.append({"cond": cond, "metric": col,
                             "mean": float("nan"), "ci_lo": float("nan"),
                             "ci_hi": float("nan"), "n": 0})
                continue
            m, lo, hi = bootstrap_ci(vals, n_resample=10_000, ci=0.95, rng=rng)
            rows.append({"cond": cond, "metric": col,
                         "mean": m, "ci_lo": lo, "ci_hi": hi, "n": int(vals.size)})
        rows.append({
            "cond": cond, "metric": "bin_var_slope_pooled",
            "mean": pooled_bin_var.get(cond, float("nan")),
            "ci_lo": float("nan"), "ci_hi": float("nan"),
            "n": int(len(sub)),
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# Figures (§3.10)
# ---------------------------------------------------------------------------

def plot_pooled_bin_var_2x2(
    pooled: Dict[str, float], pattern: str, out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 6))
    matrix = np.array([
        [pooled.get("C0u", np.nan), pooled.get("C0p", np.nan)],
        [pooled.get("C2", np.nan), pooled.get("C3", np.nan)],
    ])
    im = ax.imshow(matrix, cmap="RdBu_r", vmin=-0.6, vmax=0.6, aspect="equal")
    for i in range(2):
        for j in range(2):
            v = matrix[i, j]
            ax.text(j, i, f"{v:+.3f}" if not np.isnan(v) else "—",
                    ha="center", va="center",
                    color="white" if abs(v) > 0.3 else "black",
                    fontsize=14, fontweight="bold")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["wealth=uniform", "wealth=pareto"])
    ax.set_yticklabels(["world=agg", "world=lob"])
    ax.set_title(f"Pooled bin_var_slope (4-cond)\nPattern: {pattern}", fontsize=12)
    fig.colorbar(im, ax=ax, label="bin_var_slope (pooled)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


def plot_interaction_violin(
    df: pd.DataFrame, out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(INTERACTION_METRICS),
                             figsize=(4 * len(INTERACTION_METRICS), 5))
    for ax, metric in zip(axes, INTERACTION_METRICS):
        c0u = df[df["cond"] == "C0u"][metric].dropna().to_numpy()
        c0p = df[df["cond"] == "C0p"][metric].dropna().to_numpy()
        c2 = df[df["cond"] == "C2"][metric].dropna().to_numpy()
        c3 = df[df["cond"] == "C3"][metric].dropna().to_numpy()
        n = min(c0u.size, c0p.size, c2.size, c3.size)
        if n == 0:
            ax.set_title(f"{metric}\n(no data)")
            continue
        inter = (c3[:n] - c2[:n]) - (c0p[:n] - c0u[:n])
        parts = ax.violinplot([inter], positions=[0], showmeans=True, showextrema=True)
        for pc in parts["bodies"]:
            pc.set_facecolor("#7777ff"); pc.set_alpha(0.6)
        ax.axhline(0, color="black", linewidth=0.4, alpha=0.5)
        ax.set_xticks([]); ax.set_title(f"{metric}\nmean={inter.mean():+.3f}", fontsize=10)
    fig.suptitle("S3 — Interaction (C3-C2) - (C0p-C0u) per trial pair", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


def plot_lifetime_distributions(
    seeds: List[int], out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641", "C2": "#d62728", "C3": "#a50f15"}
    for ax, cond in zip(axes.flatten(), ALL_CONDS):
        cond_dir = DATA_DIR / cond
        T_cond = AGG_PARAMS["T"] if cond in AGG_CONDS else LOB_PARAMS["main_steps"]
        all_lifetimes: List[float] = []
        for seed in seeds:
            p = cond_dir / f"lifetimes_{seed:04d}.parquet"
            if p.exists():
                lt_df = pd.read_parquet(p)
                if len(lt_df) > 0:
                    all_lifetimes.extend(lt_df["lifetime"].tolist())
        if not all_lifetimes:
            ax.set_title(f"{cond} (no data)")
            continue
        arr = np.array(all_lifetimes, dtype=np.float64)
        ax.hist(arr, bins=60, color=palette[cond], alpha=0.7)
        ax.axvline(T_cond / 2, color="black", linestyle="--", alpha=0.7,
                   label=f"T/2 = {T_cond/2:.0f}")
        ax.axvline(T_cond, color="red", linestyle="--", alpha=0.7,
                   label=f"T = {T_cond}")
        ax.set_title(f"{cond} (T={T_cond}, n_samples={len(arr):,})", fontsize=10)
        ax.set_xlabel("lifetime (steps)"); ax.set_ylabel("count")
        ax.legend(fontsize=8)
    fig.suptitle("S3 — 4-cond lifetime distributions (Hypothesis A primary evidence, plan v2 §3.8)",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# README append
# ---------------------------------------------------------------------------

def append_readme(
    df: pd.DataFrame, pooled: Dict[str, float], pattern: Tuple[str, str],
    interaction_df: pd.DataFrame, lifetime_df: pd.DataFrame,
    hyp_a_evidence: Tuple[bool, str], readme_path: Path,
) -> None:
    lines: List[str] = []
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Stage S3 — LOB ensemble (C2/C3) + 4 条件 interaction")
    lines.append("")
    n_per_cond = df.groupby("cond").size().to_dict()
    lines.append("**実行範囲**: " + ", ".join(f"{c}: {n} trial" for c, n in n_per_cond.items()))
    lines.append("")

    # 4 条件 main metrics
    lines.append("### 主指標 4 条件 mean ± 95% CI (bootstrap 10,000 resample)")
    lines.append("")
    lines.append("| metric | C0u | C0p | C2 | C3 |")
    lines.append("|---|---|---|---|---|")
    rng = np.random.default_rng(0)
    summary_main = ["rho_pearson", "rho_spearman", "tau_kendall",
                    "bin_var_slope", "q90_q10_slope_diff",
                    "corr_w_init_h", "skew_high_minus_low", "hill_alpha",
                    "lifetime_median", "lifetime_p90",
                    "wealth_persistence_rho", "forced_retire_rate"]
    for col in summary_main:
        cells = []
        for cond in ALL_CONDS:
            vals = df[df["cond"] == cond][col].dropna().to_numpy()
            if vals.size == 0:
                cells.append("—")
                continue
            m, lo, hi = bootstrap_ci(vals, n_resample=10_000, ci=0.95, rng=rng)
            cells.append(f"{m:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        lines.append(f"| {col} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} |")
    lines.append("")

    # Pooled bin_var 2x2 + pattern
    lines.append("### Pooled bin_var_slope 2×2 + pattern (S3 plan v2 §3.7、修正 1)")
    lines.append("")
    lines.append("| | wealth=uniform | wealth=pareto | wealth diff (pareto-uniform) |")
    lines.append("|---|---|---|---|")
    agg_diff = pooled.get("C0p", float("nan")) - pooled.get("C0u", float("nan"))
    lob_diff = pooled.get("C3", float("nan")) - pooled.get("C2", float("nan"))
    lines.append(f"| world=agg | C0u: {pooled.get('C0u', float('nan')):+.4f} | "
                 f"C0p: {pooled.get('C0p', float('nan')):+.4f} | {agg_diff:+.4f} (S2 確定) |")
    lines.append(f"| world=lob | C2: {pooled.get('C2', float('nan')):+.4f} | "
                 f"C3: {pooled.get('C3', float('nan')):+.4f} | {lob_diff:+.4f} |")
    lines.append("")
    lines.append(f"**Interaction value (LOB diff − aggregate diff)** = {lob_diff - agg_diff:+.4f}")
    lines.append("")
    lines.append(f"**Pattern**: **{pattern[0]}** — {pattern[1]}")
    lines.append("")

    # Interaction (full)
    lines.append("### Interaction = (C3 − C2) − (C0p − C0u) ± 95% CI (S1-secondary 確定前の 100 trial 値)")
    lines.append("")
    lines.append("| metric | mean | CI lo | CI hi | n |")
    lines.append("|---|---:|---:|---:|---:|")
    for _, r in interaction_df.iterrows():
        lines.append(f"| {r['metric']} | {r['interaction_mean']:+.4f} | "
                     f"{r['ci_lo']:+.4f} | {r['ci_hi']:+.4f} | {int(r['n'])} |")
    lines.append("")

    # Lifetime evidence (Yuito 2026-04-30 mandate: 主指標切替後)
    lines.append("### Lifetime distribution: 仮説 A 中間予測 primary evidence (§3.8、修正 2)")
    lines.append("")
    lines.append("**主指標 (Yuito mandate 2026-04-30)**: p25 / conditional median / censoring 率 — "
                 "median と p90 は LOB で T 張り付くため補助。")
    lines.append("")
    lines.append("| cond | T | n_trials | n_samples | **p25 (主)** | **conditional median (主)** | **censoring 率 (主)** | median (補助) | p90 (補助) | median>T/2 (補助) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in lifetime_df.iterrows():
        lines.append(
            f"| {r['cond']} | {int(r['T'])} | {int(r['n_trials'])} | {int(r['n_total_samples'])} | "
            f"**{r['p25_pooled']:.1f}** | "
            f"**{r['conditional_median']:.1f}** | "
            f"**{r['censoring_rate']:.1%}** | "
            f"{r['lifetime_median_mean']:.1f} | {r['lifetime_p90_mean']:.1f} | "
            f"{int(r['n_above_T_half'])}/{int(r['n_trials'])} |"
        )
    lines.append("")
    lines.append(f"**仮説 A 判定**: {hyp_a_evidence[1]}")
    lines.append("")
    lines.append("**Mac stage finding (継承)**: C2 (LOB uniform) は全 agent が roughly 同 pace で "
                 "生存 (p25 も T 近く)、C3 (LOB pareto) は下位 25% が早期退場 (Pareto tail で "
                 "wealth 失敗) — wealth-tail composition の persist が visualized。aggregate "
                 "(T=50000) の censoring_rate ≪ 1 との対比で、LOB friction が agent identity の "
                 "流動を実際に止めている定量証拠 (S1-secondary plan で Fig.4 / Fig.5 として申し送り予定)。")
    lines.append("")
    lines.append("**survival analysis (Kaplan-Meier 等) は引き続き Phase 2 scope 外** "
                 "(S2 plan v2 §0.7、S3 plan v2 修正 2 確定済)。")
    lines.append("")

    # KPI L1 暫定確認
    lines.append("### KPI L1 暫定確認 (S1 単 trial 値からの更新、S1-secondary 確定前)")
    lines.append("")
    lines.append("3 中 2 以上で符号と桁が一致 → satisfy。`tab_S3_interaction.csv` 参照。")
    lines.append("")
    lines.append("**plan A/B 分岐判定は出さない、S1-secondary plan で Yuito 承認後に確定**。")
    lines.append("")

    # Layer 2 (再掲)
    lines.append("### Layer 2 timescale concern (Phase 2 scope 外、再掲)")
    lines.append("")
    lines.append("Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を超える "
                 "長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + proposal "
                 "Limitations 節に明記する。")
    lines.append("")

    with open(readme_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    args = parser.parse_args()

    logger = setup_logger()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("S3 aggregate_full_summary — 4 条件 100 trial summary")
    logger.info("=" * 70)

    # Load combined ensemble_summary (400 行 = C0u+C0p+C2+C3 各 100)
    df = pd.read_parquet(DATA_DIR / "ensemble_summary.parquet")
    logger.info(f"[load] ensemble_summary: {len(df)} rows, "
                f"conds={sorted(df['cond'].unique().tolist())}")

    # Pooled bin_var (4 cond) + pattern 判定
    pooled = compute_pooled_bin_var_4cond(seeds, logger)
    lob_diff_ci = lob_diff_bootstrap(df, "bin_var_slope")
    pattern = classify_bin_var_pattern(pooled, lob_diff_ci)
    logger.info(f"[pattern] §3.7 v2: {pattern[0]} — {pattern[1]}")

    # Interaction (5 metrics, full)
    interaction_df = compute_interactions(df)
    interaction_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S3_interaction.csv", index=False)
    logger.info(f"[output] saved: {OUTPUTS_DIR / 'tables' / 'tab_S3_interaction.csv'}")

    # Lifetime evidence (§3.8 v2)
    lifetime_df = lifetime_evidence_table(df, seeds, logger)
    lifetime_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S3_lifetime.csv", index=False)
    logger.info(f"[output] saved: {OUTPUTS_DIR / 'tables' / 'tab_S3_lifetime.csv'}")
    hyp_a = hypothesis_A_evidence(lifetime_df)
    logger.info(f"[lifetime] §3.8 v2: {hyp_a[1]}")

    # Full summary table
    write_full_summary(df, pooled,
                       OUTPUTS_DIR / "tables" / "tab_S3_full_summary.csv", logger)

    # Figures
    plot_pooled_bin_var_2x2(pooled, pattern[0],
                            OUTPUTS_DIR / "figures" / "fig_S3_pooled_bin_var_2x2.png",
                            logger)
    plot_interaction_violin(df,
                            OUTPUTS_DIR / "figures" / "fig_S3_interaction_violin.png",
                            logger)
    plot_lifetime_distributions(seeds,
                                OUTPUTS_DIR / "figures" / "fig_S3_lifetime_distributions.png",
                                logger)

    # README append
    append_readme(df, pooled, pattern, interaction_df, lifetime_df, hyp_a,
                  YH006_1 / "README.md")
    logger.info(f"[output] appended README: {YH006_1 / 'README.md'}")

    # JSON summary for diff.md
    summary_for_diff = {
        "stage": "S3",
        "n_trials_per_cond": df.groupby("cond").size().to_dict(),
        "pooled_bin_var": pooled,
        "aggregate_diff": pooled.get("C0p", float("nan")) - pooled.get("C0u", float("nan")),
        "lob_diff_ci": list(lob_diff_ci),
        "interaction_value": (pooled.get("C3", float("nan")) - pooled.get("C2", float("nan")))
                            - (pooled.get("C0p", float("nan")) - pooled.get("C0u", float("nan"))),
        "pattern": pattern[0],
        "pattern_description": pattern[1],
        "interaction_metrics": interaction_df.to_dict(orient="records"),
        "lifetime_evidence": lifetime_df.to_dict(orient="records"),
        "hypothesis_A_primary_evidence": hyp_a[0],
        "hypothesis_A_message": hyp_a[1],
    }
    with open(LOGS_DIR / "S3_summary_for_diff.json", "w", encoding="utf-8") as f:
        json.dump(summary_for_diff, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {LOGS_DIR / 'S3_summary_for_diff.json'}")

    logger.info("=" * 70)
    logger.info("S3 aggregate_full_summary complete.")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
