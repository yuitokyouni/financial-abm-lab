"""S5.5 — aggregate sub-sample 再分析: RT 数 / 時間軸 disparity 制御.

S5.5 plan v1 §3.1-§3.5:
  - 4 condition (C0u/C0p/C2/C3) の per-trial / pooled RT count 実測
  - aggregate (C0u/C0p) を 2 種類 sub-sample 化:
      aggregate_T1500: t_open < 1500 で抽出 (時間軸を LOB と揃える)
      aggregate_RT10k: t_open 昇順で最初 10,000 RT (LOB の 10x order)
  - aggregate_T1500 では sim T=1500 を仮定し lifetime の re-censoring + p25
  - 4 sub-sample × 4 cond で pooled bin_var slope + trial-level 5 主指標 CI
  - H_micro / H_artifact 判定 (pooled bin_var slope 絶対値 0.15 / 0.30 境界)

Run (Windows、PAMS 不要):
  cd experiments/YH006_1
  python -m code.subsample_aggregate
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from analysis import (  # noqa: E402
    bin_variance_slope, bin_variance_slope_pooled,
    corr_pearson, corr_spearman, corr_kendall,
    quantile_slope_diff,
)
from config import ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS  # noqa: E402
from stats import bootstrap_ci  # noqa: E402

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

ALL_CONDS = ["C0u", "C0p", "C2", "C3"]
AGG_CONDS = ["C0u", "C0p"]
LOB_CONDS = ["C2", "C3"]

T_LOB = 1500
N_RT_RT10K = 10_000

MAIN_METRICS_5 = ["rho_pearson", "rho_spearman", "tau_kendall",
                  "bin_var_slope", "q90_q10_slope_diff"]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.5")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.5_subsample.log", encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# §3.1 RT count 実測 + §3.2 sub-sample 抽出
# ---------------------------------------------------------------------------

def load_trial_rt(cond: str, seed: int,
                  cols: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
    p = DATA_DIR / cond / f"trial_{seed:04d}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p, columns=cols)


def extract_subsample(
    rt: pd.DataFrame, sample_kind: str,
) -> pd.DataFrame:
    """sub-sample 抽出.

    sample_kind:
      "full" → そのまま
      "T1500" → t_open < 1500 でフィルタ
      "RT10k" → t_open 昇順 sort 後最初 10,000 行 (n < 10k なら全件)
    """
    if sample_kind == "full":
        return rt
    if sample_kind == "T1500":
        return rt[rt["t_open"] < T_LOB]
    if sample_kind == "RT10k":
        sorted_rt = rt.sort_values("t_open", kind="stable")
        return sorted_rt.head(N_RT_RT10K)
    raise ValueError(f"unknown sample_kind: {sample_kind}")


def measure_rt_counts(
    seeds: List[int], logger: logging.Logger,
) -> pd.DataFrame:
    """4 cond × 4 sub-sample (full / T1500 / RT10k / —) の per-trial / pooled RT 数を出す.

    LOB cond (C2/C3) は sub-sample を取らず "full" 値のみを記録 (LOB が比較対象基準)。
    """
    rows = []
    for cond in ALL_CONDS:
        # full の per-trial / pooled 集計
        per_trial = []
        for seed in seeds:
            rt = load_trial_rt(cond, seed, cols=["t_open"])
            if rt is None:
                continue
            per_trial.append(len(rt))
        if not per_trial:
            logger.warning(f"[rt_count] {cond}: no trial parquet, skipping")
            continue
        arr = np.array(per_trial)
        pooled = int(arr.sum())
        rows.append({
            "cond": cond, "sample_kind": "full",
            "n_trial": int(arr.size),
            "n_rt_per_trial_mean": float(arr.mean()),
            "n_rt_per_trial_sd": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            "n_rt_pooled": pooled,
        })
        logger.info(
            f"[rt_count] {cond} full: n_trial={arr.size} "
            f"per_trial_mean={arr.mean():,.1f} ± {arr.std(ddof=1):,.1f} "
            f"pooled={pooled:,}"
        )

        if cond not in AGG_CONDS:
            continue

        # aggregate 限定: T1500 / RT10k の RT 数も測る
        for sk in ("T1500", "RT10k"):
            per_trial_sub = []
            for seed in seeds:
                rt = load_trial_rt(cond, seed, cols=["t_open"])
                if rt is None:
                    continue
                sub = extract_subsample(rt, sk)
                per_trial_sub.append(len(sub))
            arr_sub = np.array(per_trial_sub)
            pooled_sub = int(arr_sub.sum())
            rows.append({
                "cond": cond, "sample_kind": sk,
                "n_trial": int(arr_sub.size),
                "n_rt_per_trial_mean": float(arr_sub.mean()),
                "n_rt_per_trial_sd": float(arr_sub.std(ddof=1)) if arr_sub.size > 1 else 0.0,
                "n_rt_pooled": pooled_sub,
            })
            logger.info(
                f"[rt_count] {cond} {sk}: per_trial_mean={arr_sub.mean():,.1f} "
                f"pooled={pooled_sub:,}"
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# §3.3 censoring / lifetime 再計算 (aggregate_T1500)
# ---------------------------------------------------------------------------

def recensor_lifetime_T1500(
    cond: str, seeds: List[int], T_window: int = T_LOB,
) -> Tuple[float, float, float, int, int]:
    """aggregate (C0u/C0p) を T=T_window で打ち切った lifetime stats を返す.

    各 sample:
      - t_birth >= T_window: drop (start 後)
      - t_end <= T_window: keep as is (lifetime = t_end - t_birth, censored=元の値)
      - t_birth < T_window < t_end: lifetime = T_window - t_birth, censored=True

    Returns: (p25, conditional_median, censoring_rate, n_total, n_censored)
    """
    all_lifetimes: List[int] = []
    all_censored: List[bool] = []
    for seed in seeds:
        p = DATA_DIR / cond / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt = pd.read_parquet(p)
        if len(lt) == 0:
            continue
        in_window = lt[lt["t_birth"] < T_window].copy()
        # 元 sample が t_end <= T_window なら そのまま (元の censored 値を継承)
        # t_birth < T_window <= t_end なら T_window で打ち切り = censored
        clip = in_window["t_end"] > T_window
        in_window.loc[clip, "lifetime"] = T_window - in_window.loc[clip, "t_birth"]
        new_censored = in_window["censored"].astype(bool) | clip
        all_lifetimes.extend(in_window["lifetime"].astype(int).tolist())
        all_censored.extend(new_censored.tolist())

    if not all_lifetimes:
        return (float("nan"), float("nan"), float("nan"), 0, 0)

    arr = np.array(all_lifetimes, dtype=np.float64)
    cens = np.array(all_censored, dtype=bool)
    p25 = float(np.percentile(arr, 25))
    censoring_rate = float(cens.mean())
    if (~cens).sum() > 0:
        cond_median = float(np.median(arr[~cens]))
    else:
        cond_median = float("nan")
    return (p25, cond_median, censoring_rate, int(arr.size), int(cens.sum()))


def lifetime_stats_lob(
    cond: str, seeds: List[int],
) -> Tuple[float, float, float, int, int]:
    """LOB cond の lifetime stats を既存 parquet からそのまま返す (T=1500 で既に censoring 済)."""
    all_lifetimes: List[int] = []
    all_censored: List[bool] = []
    for seed in seeds:
        p = DATA_DIR / cond / f"lifetimes_{seed:04d}.parquet"
        if not p.exists():
            continue
        lt = pd.read_parquet(p)
        if len(lt) == 0:
            continue
        all_lifetimes.extend(lt["lifetime"].astype(int).tolist())
        all_censored.extend(lt["censored"].astype(bool).tolist())
    if not all_lifetimes:
        return (float("nan"), float("nan"), float("nan"), 0, 0)
    arr = np.array(all_lifetimes, dtype=np.float64)
    cens = np.array(all_censored, dtype=bool)
    p25 = float(np.percentile(arr, 25))
    censoring_rate = float(cens.mean())
    cond_median = (float(np.median(arr[~cens])) if (~cens).sum() > 0
                   else float("nan"))
    return (p25, cond_median, censoring_rate, int(arr.size), int(cens.sum()))


# ---------------------------------------------------------------------------
# §3.4 trial-level 5 主指標 + pooled bin_var
# ---------------------------------------------------------------------------

def compute_trial_metrics(rt: pd.DataFrame) -> Dict[str, float]:
    """1 trial の rt sub-sample から 5 主指標を計算."""
    if len(rt) == 0:
        return {m: float("nan") for m in MAIN_METRICS_5}
    h = rt["horizon"].to_numpy(dtype=np.float64)
    dG = rt["delta_g"].to_numpy(dtype=np.float64)
    abs_dG = np.abs(dG)
    return {
        "rho_pearson": corr_pearson(h, abs_dG),
        "rho_spearman": corr_spearman(h, abs_dG),
        "tau_kendall": corr_kendall(h, abs_dG),
        "bin_var_slope": bin_variance_slope(h, dG, K=15),
        "q90_q10_slope_diff": quantile_slope_diff(h, dG),
    }


def compute_sample_summary(
    cond: str, sample_kind: str, seeds: List[int], logger: logging.Logger,
    compute_trial_metrics_flag: bool = True,
) -> Tuple[float, pd.DataFrame, int]:
    """1 (cond, sample_kind) ペアの pooled bin_var + trial-level 100 行 summary.

    compute_trial_metrics_flag=False のときは pooled bin_var のみ計算、
    trial-level metrics は NaN で埋める (full agg の QuantReg @1M RT を回避)。
    sub-sample (T1500/RT10k) は full sub-sample size が小さいので fully 計算。

    Returns: (pooled_bin_var_slope, trial_df, n_rt_pooled)
    """
    rt_concat: List[pd.DataFrame] = []
    rows: List[Dict[str, float]] = []
    n_total = 0
    for seed in seeds:
        rt = load_trial_rt(cond, seed,
                           cols=["agent_id", "t_open", "horizon", "delta_g"])
        if rt is None:
            continue
        sub = extract_subsample(rt, sample_kind)
        rt_concat.append(sub[["horizon", "delta_g"]])
        n_total += len(sub)
        if compute_trial_metrics_flag:
            row = compute_trial_metrics(sub)
        else:
            row = {m: float("nan") for m in MAIN_METRICS_5}
        row.update({"cond": cond, "sample_kind": sample_kind, "seed": seed,
                    "n_rt": int(len(sub))})
        rows.append(row)
    trial_df = pd.DataFrame(rows)

    if not rt_concat:
        return float("nan"), trial_df, 0
    t0 = time.perf_counter()
    pooled_rt = pd.concat(rt_concat, ignore_index=True)
    pooled_slope = bin_variance_slope_pooled(pooled_rt, K=15)
    logger.info(
        f"[bin_var_pooled] {cond}/{sample_kind}: "
        f"n_pooled={len(pooled_rt):,} pooled_bin_var_slope={pooled_slope:+.4f} "
        f"(took {time.perf_counter()-t0:.1f}s)"
    )
    return pooled_slope, trial_df, n_total


def trial_level_ci(values: np.ndarray) -> Tuple[float, float, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    return bootstrap_ci(arr, n_resample=10_000, ci=0.95,
                        rng=np.random.default_rng(0))


# ---------------------------------------------------------------------------
# §3.5 判定 + figure
# ---------------------------------------------------------------------------

def classify_micro_vs_artifact(
    rt10k_pooled: Dict[str, float],
) -> Tuple[str, str]:
    """RT10k 版の aggregate pooled bin_var slope 絶対値で 3 区分判定.

    H_artifact 強支持: 両方 |slope| <= 0.15 (LOB 範囲)
    H_micro 強支持:   両方 |slope| >= 0.30 (full aggregate 水準維持)
    その他: ambiguous
    """
    c0u = rt10k_pooled.get("C0u", float("nan"))
    c0p = rt10k_pooled.get("C0p", float("nan"))
    if np.isnan(c0u) or np.isnan(c0p):
        return ("inconclusive", "RT10k sub-sample の pooled bin_var slope が NaN")
    abs_c0u, abs_c0p = abs(c0u), abs(c0p)
    if abs_c0u <= 0.15 and abs_c0p <= 0.15:
        return ("H_artifact",
                f"RT10k pooled bin_var slope (C0u={c0u:+.4f}, C0p={c0p:+.4f}) "
                f"両方が |slope| ≤ 0.15、LOB 範囲 (−0.05〜−0.18) に近づいた → "
                f"H_artifact (sample / window artifact) 強支持、Phase 2 結論 refactor 検討")
    if abs_c0u >= 0.30 and abs_c0p >= 0.30:
        return ("H_micro",
                f"RT10k pooled bin_var slope (C0u={c0u:+.4f}, C0p={c0p:+.4f}) "
                f"両方が |slope| ≥ 0.30、full aggregate 水準 (−0.40 / −0.29) を保持 → "
                f"H_micro (LOB microstructure 真効果) 強支持、S6 進行可")
    return ("ambiguous",
            f"RT10k pooled bin_var slope (C0u={c0u:+.4f}, C0p={c0p:+.4f}) "
            f"が中間 (0.15 < |slope| < 0.30 のいずれか) → 判定保留、Yuito 議論")


def plot_results(
    pooled_by_sample: Dict[str, Dict[str, float]],
    lifetime_table: pd.DataFrame,
    out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(11, 9))

    # 上段: grouped bar 4 cond × 4 sample
    samples_order = ["full_agg", "T1500_agg", "RT10k_agg", "LOB"]
    conds_legend = ["C0u", "C0p", "C2", "C3"]
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641",
               "C2": "#d62728", "C3": "#a50f15"}
    x = np.arange(len(samples_order))
    width = 0.20
    for i, cond in enumerate(conds_legend):
        ys = []
        for sk in samples_order:
            ys.append(pooled_by_sample.get(sk, {}).get(cond, np.nan))
        ax_top.bar(x + (i - 1.5) * width, ys, width=width,
                   label=cond, color=palette[cond])
    ax_top.axhline(0, color="black", linewidth=0.4)
    ax_top.set_xticks(x); ax_top.set_xticklabels(samples_order)
    ax_top.set_ylabel("pooled bin_var_slope")
    ax_top.set_title("S5.5 pooled bin_var_slope: 4 conds × 4 sub-samples")
    ax_top.legend(ncol=4)
    ax_top.grid(axis="y", alpha=0.3)

    # 下段: wealth diff (pareto - uniform) for each sub-sample
    diffs = []
    for sk in samples_order:
        d = pooled_by_sample.get(sk, {})
        if sk == "LOB":
            diff = d.get("C3", np.nan) - d.get("C2", np.nan)
        else:
            diff = d.get("C0p", np.nan) - d.get("C0u", np.nan)
        diffs.append(diff)
    ax_bottom.bar(x, diffs, color=["#aaaa55", "#aa5555", "#5555aa", "#444444"])
    ax_bottom.axhline(0, color="black", linewidth=0.4)
    ax_bottom.set_xticks(x); ax_bottom.set_xticklabels(samples_order)
    ax_bottom.set_ylabel("bin_var_slope diff (pareto − uniform)")
    ax_bottom.set_title("S5.5 wealth diff per sub-sample (= 一段 interaction 直感)")
    for xi, d in enumerate(diffs):
        if not np.isnan(d):
            ax_bottom.text(xi, d, f"{d:+.3f}", ha="center",
                           va="bottom" if d > 0 else "top", fontsize=9)
    ax_bottom.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    seeds = list(range(ENSEMBLE_SEED_BASE,
                       ENSEMBLE_SEED_BASE + ENSEMBLE_N_TRIALS))

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("S5.5 subsample_aggregate — 4 cond × 4 sub-sample 再分析")
    logger.info("=" * 70)

    # §3.1 RT 数 実測
    rt_count_df = measure_rt_counts(seeds, logger)
    rt_count_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S5.5_rt_counts.csv",
                       index=False)

    # §3.2 + §3.4 各 (cond, sample_kind) で pooled + trial 5 metrics
    # 戦略 (高速化):
    #   - full agg (C0u/C0p): pooled bin_var のみ生計算、trial-level は既存
    #     ensemble_summary.parquet から流用 (S2 で既に 100 trial 計算済)
    #   - T1500 / RT10k: per-trial 31k / 10k RT で trial-level 5 metrics 計算
    #     (QuantReg もこのサイズなら ~1 秒/trial で OK)
    #   - LOB (C2/C3): pooled bin_var のみ生計算、trial-level は ensemble_summary
    #     から流用 (S3 で 100 trial 計算済)
    pooled_by_sample: Dict[str, Dict[str, float]] = {
        "full_agg": {}, "T1500_agg": {}, "RT10k_agg": {}, "LOB": {},
    }
    trial_dfs: List[pd.DataFrame] = []

    # 既存 ensemble_summary.parquet を load (full agg / LOB の trial-level 値の出所)
    ensemble = pd.read_parquet(DATA_DIR / "ensemble_summary.parquet")
    logger.info(f"[load] ensemble_summary: {len(ensemble)} rows, "
                f"conds={sorted(ensemble['cond'].unique().tolist())}")

    def _ensemble_trial_df(cond: str, sk_label: str) -> pd.DataFrame:
        """ensemble_summary から (cond) の trial-level 5 主指標を抽出して
        trial_df (n_trial 行) を返す."""
        sub = ensemble[ensemble["cond"] == cond].copy()
        rows = []
        for _, r in sub.iterrows():
            rows.append({
                "cond": cond, "sample_kind": sk_label,
                "seed": int(r["seed"]) if "seed" in r else -1,
                "n_rt": int(r.get("n_round_trips", r.get("n_rt", 0))),
                "rho_pearson": float(r.get("rho_pearson", float("nan"))),
                "rho_spearman": float(r.get("rho_spearman", float("nan"))),
                "tau_kendall": float(r.get("tau_kendall", float("nan"))),
                "bin_var_slope": float(r.get("bin_var_slope", float("nan"))),
                "q90_q10_slope_diff": float(r.get("q90_q10_slope_diff", float("nan"))),
            })
        return pd.DataFrame(rows)

    # aggregate (C0u/C0p) × {full, T1500, RT10k}
    for cond in AGG_CONDS:
        for sk_int, sk_ext in [("full", "full_agg"),
                               ("T1500", "T1500_agg"),
                               ("RT10k", "RT10k_agg")]:
            do_trial = (sk_int != "full")  # full は重いので skip
            pooled_slope, trial_df, _ = compute_sample_summary(
                cond, sk_int, seeds, logger,
                compute_trial_metrics_flag=do_trial,
            )
            pooled_by_sample[sk_ext][cond] = pooled_slope
            if not do_trial:
                # ensemble_summary から trial-level 値を引く
                trial_df_ens = _ensemble_trial_df(cond, sk_ext)
                trial_dfs.append(trial_df_ens)
            else:
                # sub-sample 計算経路: sample_kind を sk_ext (= T1500_agg / RT10k_agg) に統一
                trial_df = trial_df.copy()
                trial_df["sample_kind"] = sk_ext
                trial_dfs.append(trial_df)

    # LOB (C2/C3) × full のみ — pooled bin_var を生計算、trial-level は ensemble_summary 流用
    for cond in LOB_CONDS:
        pooled_slope, _, _ = compute_sample_summary(
            cond, "full", seeds, logger, compute_trial_metrics_flag=False,
        )
        pooled_by_sample["LOB"][cond] = pooled_slope
        trial_dfs.append(_ensemble_trial_df(cond, "LOB"))

    trial_all = pd.concat(trial_dfs, ignore_index=True)
    trial_all.to_parquet(
        DATA_DIR / "ensemble_summary_subsample.parquet", index=False,
    )
    logger.info(
        f"[output] saved: {DATA_DIR / 'ensemble_summary_subsample.parquet'} "
        f"({len(trial_all)} rows)"
    )

    # §3.3 lifetime stats (aggregate_T1500 で re-censoring、LOB はそのまま)
    lifetime_rows = []
    for cond in AGG_CONDS:
        # full aggregate (T=50000、censoring ~0.9%)
        p25_f, cm_f, cr_f, n_f, ncen_f = lifetime_stats_lob(cond, seeds)  # 既存値そのまま
        lifetime_rows.append({
            "cond": cond, "sample_kind": "full_agg",
            "T_window": 50_000, "p25": p25_f,
            "conditional_median": cm_f, "censoring_rate": cr_f,
            "n_total_samples": n_f, "n_censored": ncen_f,
        })
        # T1500 で打ち切り直し
        p25_t, cm_t, cr_t, n_t, ncen_t = recensor_lifetime_T1500(cond, seeds)
        lifetime_rows.append({
            "cond": cond, "sample_kind": "T1500_agg",
            "T_window": T_LOB, "p25": p25_t,
            "conditional_median": cm_t, "censoring_rate": cr_t,
            "n_total_samples": n_t, "n_censored": ncen_t,
        })
        # RT10k は時間軸を切らないので full と同じ (copy)
        lifetime_rows.append({
            "cond": cond, "sample_kind": "RT10k_agg",
            "T_window": 50_000, "p25": p25_f,
            "conditional_median": cm_f, "censoring_rate": cr_f,
            "n_total_samples": n_f, "n_censored": ncen_f,
        })
        logger.info(
            f"[lifetime] {cond} full: p25={p25_f:.1f} cm={cm_f:.1f} "
            f"cens_rate={cr_f:.1%} n={n_f}; T1500 cap: p25={p25_t:.1f} "
            f"cm={cm_t:.1f} cens_rate={cr_t:.1%} n={n_t}"
        )
    for cond in LOB_CONDS:
        p25, cm, cr, n_total, n_cen = lifetime_stats_lob(cond, seeds)
        lifetime_rows.append({
            "cond": cond, "sample_kind": "LOB",
            "T_window": T_LOB, "p25": p25,
            "conditional_median": cm, "censoring_rate": cr,
            "n_total_samples": n_total, "n_censored": n_cen,
        })
        logger.info(
            f"[lifetime] {cond} LOB: p25={p25:.1f} cm={cm:.1f} "
            f"cens_rate={cr:.1%} n={n_total}"
        )

    lifetime_df = pd.DataFrame(lifetime_rows)
    lifetime_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S5.5_lifetime_subsample.csv",
                       index=False)

    # §3.4 main comparison table: 4 sub-sample × 4 cond × (pooled + 5 metric CI)
    rows = []
    for (sk_label, cond) in [
        ("full_agg", "C0u"), ("full_agg", "C0p"),
        ("T1500_agg", "C0u"), ("T1500_agg", "C0p"),
        ("RT10k_agg", "C0u"), ("RT10k_agg", "C0p"),
        ("LOB", "C2"), ("LOB", "C3"),
    ]:
        trials = trial_all[(trial_all["cond"] == cond) &
                           (trial_all["sample_kind"] == sk_label)]
        row = {
            "sample_kind": sk_label,
            "cond": cond,
            "n_trial": int(len(trials)),
            "n_rt_per_trial_mean": float(trials["n_rt"].mean()) if len(trials) else float("nan"),
            "n_rt_pooled": int(trials["n_rt"].sum()) if len(trials) else 0,
            "pooled_bin_var_slope": pooled_by_sample.get(sk_label, {}).get(cond, float("nan")),
        }
        for metric in MAIN_METRICS_5:
            if len(trials):
                m, lo, hi = trial_level_ci(trials[metric].to_numpy())
            else:
                m, lo, hi = float("nan"), float("nan"), float("nan")
            row[f"{metric}_mean"] = m
            row[f"{metric}_ci_lo"] = lo
            row[f"{metric}_ci_hi"] = hi
        # lifetime stats (sk_label と cond から lifetime_df を引く)
        lt_row = lifetime_df[(lifetime_df["sample_kind"] == sk_label) &
                             (lifetime_df["cond"] == cond)]
        if len(lt_row):
            row["p25_lifetime"] = float(lt_row["p25"].iloc[0])
            row["censoring_rate"] = float(lt_row["censoring_rate"].iloc[0])
        else:
            row["p25_lifetime"] = float("nan")
            row["censoring_rate"] = float("nan")
        rows.append(row)
    comp_df = pd.DataFrame(rows)
    comp_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S5.5_subsample_comparison.csv",
                   index=False)
    logger.info(f"[output] saved: tab_S5.5_subsample_comparison.csv "
                f"({len(comp_df)} rows)")

    # §3.5 判定
    verdict_name, verdict_msg = classify_micro_vs_artifact(
        pooled_by_sample["RT10k_agg"]
    )
    logger.info(f"[verdict] §3.5: {verdict_name} — {verdict_msg}")

    # §3.6 figure
    plot_results(pooled_by_sample, lifetime_df,
                 OUTPUTS_DIR / "figures" / "fig_S5.5_microstructure_vs_artifact.png",
                 logger)

    # summary JSON
    summary = {
        "stage": "S5.5",
        "n_trials_per_cond": int(ENSEMBLE_N_TRIALS),
        "T_LOB_window": T_LOB,
        "n_rt_rt10k": N_RT_RT10K,
        "rt_counts": rt_count_df.to_dict(orient="records"),
        "pooled_bin_var_by_sample": pooled_by_sample,
        "verdict": verdict_name,
        "verdict_message": verdict_msg,
        "lifetime_table": lifetime_df.to_dict(orient="records"),
        "comparison_table_path": str(OUTPUTS_DIR / "tables" / "tab_S5.5_subsample_comparison.csv"),
    }
    out_json = LOGS_DIR / "S5.5_summary_for_diff.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {out_json}")

    logger.info("=" * 70)
    logger.info(f"S5.5 complete. Verdict: {verdict_name}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
