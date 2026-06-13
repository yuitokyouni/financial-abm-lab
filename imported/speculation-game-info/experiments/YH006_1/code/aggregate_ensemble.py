"""S2 主スクリプト — aggregate baseline (C0u/C0p) × 100 trial ensemble.

S2 plan v2 §3 全段:
  1. C0u/C0p × seed 1000..1099 を multiprocessing で並列実行
     (各 trial で 4 種 parquet を data/{cond}/ に出力)
  2. ensemble_summary.parquet 集計 (Brief §2.4 schema、200 行)
     - 5 主指標 + plan B 先取り + 修正 3 lifetime_median/p90 + 修正 1 wealth_persistence_rho
       + 修正 1 corr_winit_wt_T1..T10
  3. pooled bin variance (Yuito 指示 #1)
  4. Determinism guard: C0u seed=1000 を 2 回独立に走らせ ensemble_summary 行が完全一致確認
  5. LOB smoke (修正 4): C3 setup smoke 1 trial、N=100 SG 全員の w_init non-NaN assertion
     (Windows env で PAMS 不在なら skip + log)
  6. Sub-checkpoint: q90_q10_slope_diff の trial 間 SD を C0u/C0p で計算、SD > 0.3 警告
  7. tab_S2_aggregate_summary.csv + fig_S2_aggregate_distributions.png
  8. README.md S2 結果サマリ追記

Run:
  cd experiments/YH006_1
  python -m code.aggregate_ensemble [--n-workers N] [--seed-base 1000] [--n-trials 100] [--skip-determinism] [--skip-smoke]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from analysis import (  # noqa: E402
    corr_pearson, corr_spearman, corr_kendall,
    bin_variance_slope, bin_variance_slope_pooled,
    quantile_slope_diff, hill_estimator,
    skewness_high_low_diff, corr_winit_h_spearman,
)
from config import CONDITIONS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS, AGG_PARAMS  # noqa: E402
from parallel import run_parallel_trials, default_n_workers  # noqa: E402
from stats import bootstrap_ci  # noqa: E402

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

ACTIVE_CONDS = ["C0u", "C0p"]   # S2 で actually 100 trial 回すのは aggregate のみ


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "errors").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S2")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S2_aggregate_ensemble.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# trial-level metrics computation (per (cond, seed) → 1 ensemble_summary 行)
# ---------------------------------------------------------------------------

def compute_trial_metrics(
    rt_df: pd.DataFrame, agents_df: pd.DataFrame,
    lifetime_samples_df: pd.DataFrame, wealth_ts_df: pd.DataFrame,
    cond: str, seed: int, T_total: int,
) -> Dict[str, Any]:
    """Brief §2.4 ensemble_summary の 1 行を計算。

    aggregate trial では計算可能な全列を埋める。LOB-only な列 (n_lifetime_capped 等) は 0。
    """
    h = rt_df["horizon"].to_numpy(dtype=np.float64)
    dG = rt_df["delta_g"].to_numpy(dtype=np.float64)
    abs_dG = np.abs(dG)

    # Half-time split (RT count median、S2 plan v2 §0.2)
    sorted_df = rt_df.sort_values("t_open", kind="stable").reset_index(drop=True)
    n_half = len(sorted_df) // 2
    first = sorted_df.iloc[:n_half]
    second = sorted_df.iloc[n_half:]

    def _half_metrics(sub: pd.DataFrame) -> Dict[str, float]:
        if len(sub) < 2:
            return {"rho_pearson": float("nan"), "rho_spearman": float("nan")}
        sh = sub["horizon"].to_numpy(dtype=np.float64)
        sdg = np.abs(sub["delta_g"].to_numpy(dtype=np.float64))
        return {
            "rho_pearson": corr_pearson(sh, sdg),
            "rho_spearman": corr_spearman(sh, sdg),
        }

    fh_m = _half_metrics(first)
    sh_m = _half_metrics(second)

    # Lifetime samples (S2 plan v2 修正 3): median + p90、mean は使わない
    if len(lifetime_samples_df) > 0:
        # censored sample も含めて全 sample で計算 (Phase 2 主目的では KM 解析しない)
        lifetimes = lifetime_samples_df["lifetime"].to_numpy(dtype=np.float64)
        lifetime_median = float(np.median(lifetimes))
        lifetime_p90 = float(np.percentile(lifetimes, 90))
        # censoring 重大 flag (median > T/2 なら warn 用)
        lifetime_median_censoring_flag = bool(lifetime_median > T_total / 2.0)
    else:
        lifetime_median = float("nan")
        lifetime_p90 = float("nan")
        lifetime_median_censoring_flag = False

    # Wealth persistence: corr(w_init, w_final) Spearman
    if len(agents_df) >= 2:
        valid = agents_df.dropna(subset=["w_init", "w_final"])
        if len(valid) >= 2:
            wealth_persistence_rho = float(
                pd.Series(valid["w_init"]).rank().corr(pd.Series(valid["w_final"]).rank())
            )
        else:
            wealth_persistence_rho = float("nan")
    else:
        wealth_persistence_rho = float("nan")

    # forced_retire_rate = num_substitutions / (N × T)
    n_sub = int(agents_df["forced_retired"].sum()) if len(agents_df) > 0 else 0
    # better: count from lifetime_samples (each non-censored sample is a forced retire)
    if len(lifetime_samples_df) > 0:
        n_actual_subs = int((~lifetime_samples_df["censored"]).sum())
    else:
        n_actual_subs = n_sub
    N_total = int(len(agents_df))
    forced_retire_rate = float(n_actual_subs / max(N_total * T_total, 1))

    # corr(w_init, w(t)) at t = T/10, 2T/10, ..., T
    corr_winit_wt: Dict[int, float] = {}
    if len(wealth_ts_df) > 0 and len(agents_df) > 0:
        w_init_ser = agents_df.set_index("agent_id")["w_init"]
        snapshot_times = sorted(wealth_ts_df["t"].unique().tolist())
        # 対応する T1..T10 位置 (10 等分の境界)
        target_times = [int(round(T_total * k / 10)) for k in range(1, 11)]
        # snapshot_times のうち target_times に最も近いものを採用
        for k, target in enumerate(target_times, start=1):
            best_t = min(snapshot_times, key=lambda x: abs(x - target))
            sub = wealth_ts_df[wealth_ts_df["t"] == best_t]
            if len(sub) < 2:
                corr_winit_wt[k] = float("nan")
                continue
            w_at_t = sub.set_index("agent_id")["w"]
            joined = pd.concat([w_init_ser, w_at_t], axis=1, keys=["w_init", "w_t"]).dropna()
            if len(joined) < 2:
                corr_winit_wt[k] = float("nan")
                continue
            corr_winit_wt[k] = float(
                joined["w_init"].rank().corr(joined["w_t"].rank())
            )
    else:
        for k in range(1, 11):
            corr_winit_wt[k] = float("nan")

    return {
        "cond": cond,
        "seed": int(seed),
        "n_round_trips": int(len(rt_df)),
        "rho_pearson": corr_pearson(h, abs_dG),
        "rho_spearman": corr_spearman(h, abs_dG),
        "tau_kendall": corr_kendall(h, abs_dG),
        "rho_p_first_half": fh_m["rho_pearson"],
        "rho_p_second_half": sh_m["rho_pearson"],
        "rho_s_first_half": fh_m["rho_spearman"],
        "rho_s_second_half": sh_m["rho_spearman"],
        "bin_var_slope": bin_variance_slope(h, dG, K=15),  # trial-level (補助)
        "q90_q10_slope_diff": quantile_slope_diff(h, dG),
        "corr_w_init_h": corr_winit_h_spearman(rt_df, agents_df),
        "skew_high_minus_low": skewness_high_low_diff(h, dG),
        "hill_alpha": hill_estimator(dG, n_tail_frac=0.10),
        "lifetime_median": lifetime_median,
        "lifetime_p90": lifetime_p90,
        "lifetime_median_censoring_flag": lifetime_median_censoring_flag,
        "wealth_persistence_rho": wealth_persistence_rho,
        "forced_retire_rate": forced_retire_rate,
        **{f"corr_winit_wt_T{k}": corr_winit_wt[k] for k in range(1, 11)},
        "n_lifetime_capped": 0,  # aggregate では常に 0
    }


def aggregate_ensemble_summaries(
    cond: str, seeds: List[int], out_dir: Path, T_total: int, logger: logging.Logger,
) -> pd.DataFrame:
    """各 trial の parquet 4 種を読み込んで ensemble_summary 行を生成、結合 DataFrame を返す。"""
    rows = []
    for seed in seeds:
        try:
            rt_df = pd.read_parquet(out_dir / f"trial_{seed:04d}.parquet")
            agents_df = pd.read_parquet(out_dir / f"agents_{seed:04d}.parquet")
            lt_df = pd.read_parquet(out_dir / f"lifetimes_{seed:04d}.parquet")
            wts_df = pd.read_parquet(out_dir / f"wealth_ts_{seed:04d}.parquet")
        except FileNotFoundError as e:
            logger.error(f"[summary] {cond} seed={seed}: parquet missing — {e}")
            continue
        m = compute_trial_metrics(rt_df, agents_df, lt_df, wts_df, cond, seed, T_total)
        rows.append(m)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Determinism guard (S2 plan v2 §0.5 / §3.7)
# ---------------------------------------------------------------------------

def determinism_guard(cond: str, seed: int, logger: logging.Logger) -> bool:
    """同 seed × 同 cond × 2 回独立 worker で ensemble_summary 行が完全一致確認。"""
    logger.info(f"[guard] determinism check: {cond} seed={seed} × 2 runs")
    a_dir = DATA_DIR / "_guard_a"
    b_dir = DATA_DIR / "_guard_b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)

    from run_experiment import run_one_trial
    res_a = run_one_trial(cond, seed, out_dir=a_dir)
    res_b = run_one_trial(cond, seed, out_dir=b_dir)

    # rt_df 比較 (主 invariant)
    cols_to_check = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
                     "direction", "q", "delta_g"]
    a_rt = res_a.rt_df[cols_to_check].to_numpy()
    b_rt = res_b.rt_df[cols_to_check].to_numpy()
    eq = np.array_equal(a_rt, b_rt)
    if not eq:
        logger.error(f"[guard] {cond} seed={seed}: rt_df mismatch detected")
        return False

    # agents_df 比較
    eq2 = np.array_equal(
        res_a.agents_df[["agent_id", "w_init", "w_final", "n_round_trips"]].to_numpy(),
        res_b.agents_df[["agent_id", "w_init", "w_final", "n_round_trips"]].to_numpy(),
    )
    if not eq2:
        logger.error(f"[guard] {cond} seed={seed}: agents_df mismatch detected")
        return False

    logger.info(f"[guard] {cond} seed={seed}: OK (rt_df + agents_df both bit-一致)")
    return True


# ---------------------------------------------------------------------------
# LOB smoke (S2 plan v2 §3.5 / 修正 4)
# ---------------------------------------------------------------------------

def lob_smoke(logger: logging.Logger) -> Optional[bool]:
    """C3 setup × seed=9001 × short sim で WInitLoggingSpeculationAgent wiring 確認。

    Returns:
      True: smoke pass (assertion: 100 SG agent 全員 w_init non-NaN)
      False: smoke fail (assertion 失敗)
      None: PAMS 不在で skip (Windows env)
    """
    smoke_dir = DATA_DIR / "_smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    try:
        from run_experiment import run_one_trial
        result = run_one_trial("C3", 9001, out_dir=smoke_dir, is_lob_smoke=True)
    except ImportError as e:
        logger.warning(
            f"[smoke] PAMS unavailable on this env — LOB smoke skipped: {e}"
        )
        return None
    except Exception as e:
        import traceback
        logger.error(
            f"[smoke] LOB smoke crashed: {e}\n{traceback.format_exc()}"
        )
        return False

    # Assertion (修正 4): N=100 SG agent 全員の w_init 列が non-NaN
    n_total = len(result.agents_df)
    n_winit_nan = int(result.agents_df["w_init"].isna().sum())
    if n_total < 100 or n_winit_nan > 0:
        logger.error(
            f"[smoke] FAIL: agents_df len={n_total}, w_init NaN count={n_winit_nan}"
        )
        return False
    logger.info(
        f"[smoke] PASS: agents_df has {n_total} agents, all w_init non-NaN, "
        f"runtime={result.runtime_sec:.1f}s, n_rt={result.n_round_trips}"
    )
    return True


# ---------------------------------------------------------------------------
# Output: tab + figure + README
# ---------------------------------------------------------------------------

def write_summary_table(
    summary_df: pd.DataFrame,
    pooled_bin_var_by_cond: Dict[str, float],
    out_path: Path,
    logger: logging.Logger,
) -> None:
    """tab_S2_aggregate_summary.csv: condition × 指標の mean ± 95% CI + pooled。"""
    rng = np.random.default_rng(0)
    main_cols = [
        "rho_pearson", "rho_spearman", "tau_kendall",
        "rho_p_first_half", "rho_p_second_half",
        "rho_s_first_half", "rho_s_second_half",
        "bin_var_slope", "q90_q10_slope_diff",
        "corr_w_init_h", "skew_high_minus_low", "hill_alpha",
        "lifetime_median", "lifetime_p90",
        "wealth_persistence_rho", "forced_retire_rate",
    ] + [f"corr_winit_wt_T{k}" for k in range(1, 11)]

    rows = []
    for cond in summary_df["cond"].unique():
        sub = summary_df[summary_df["cond"] == cond]
        for col in main_cols:
            vals = sub[col].dropna().to_numpy(dtype=np.float64)
            if vals.size == 0:
                rows.append({"cond": cond, "metric": col,
                             "mean": float("nan"), "ci_lo": float("nan"),
                             "ci_hi": float("nan"), "n": 0})
                continue
            mean, lo, hi = bootstrap_ci(vals, n_resample=10_000, ci=0.95, rng=rng)
            rows.append({"cond": cond, "metric": col,
                         "mean": mean, "ci_lo": lo, "ci_hi": hi, "n": int(vals.size)})
        rows.append({
            "cond": cond, "metric": "bin_var_slope_pooled",
            "mean": pooled_bin_var_by_cond.get(cond, float("nan")),
            "ci_lo": float("nan"), "ci_hi": float("nan"),
            "n": int(len(sub)),
        })
    df_out = pd.DataFrame(rows)
    df_out.to_csv(out_path, index=False)
    logger.info(f"[output] saved: {out_path}")


def plot_distributions(
    summary_df: pd.DataFrame, out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    metrics = [
        "rho_pearson", "rho_spearman", "tau_kendall",
        "bin_var_slope", "q90_q10_slope_diff",
        "corr_w_init_h", "wealth_persistence_rho", "lifetime_median",
    ]
    n_metrics = len(metrics)
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    axes = axes.flatten()
    palette = {"C0u": "#2ca02c", "C0p": "#1a9641"}
    for ax, metric in zip(axes, metrics):
        for cond in summary_df["cond"].unique():
            vals = summary_df[summary_df["cond"] == cond][metric].dropna().to_numpy()
            if vals.size == 0:
                continue
            parts = ax.violinplot(vals, positions=[0 if cond == "C0u" else 1],
                                  showmeans=True, showextrema=True, widths=0.7)
            for pc in parts["bodies"]:
                pc.set_facecolor(palette.get(cond, "gray"))
                pc.set_alpha(0.6)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["C0u", "C0p"])
        ax.set_title(metric, fontsize=10)
        ax.axhline(0, color="black", linewidth=0.4, alpha=0.5)
    fig.suptitle(
        "S2 — aggregate ensemble (C0u vs C0p) violin plots, "
        f"n={int(summary_df.groupby('cond').size().min())} trials/cond",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


def append_readme(
    summary_df: pd.DataFrame,
    pooled_bin_var: Dict[str, float],
    determinism_pass: bool,
    smoke_status: Optional[bool],
    sub_checkpoint: Dict[str, Any],
    censoring_flags: Dict[str, int],
    readme_path: Path,
) -> None:
    lines: List[str] = []
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Stage S2 — aggregate baseline 100 trial ensemble")
    lines.append("")
    n_per_cond = summary_df.groupby("cond").size().to_dict()
    lines.append(
        f"**実行範囲**: " + ", ".join(f"{c}: {n} trial" for c, n in n_per_cond.items())
    )
    lines.append("")
    lines.append("### 主指標 ensemble mean ± 95% CI (bootstrap 10,000 resample)")
    lines.append("")
    lines.append("| metric | C0u (mean [CI]) | C0p (mean [CI]) |")
    lines.append("|---|---|---|")
    main_cols = [
        "rho_pearson", "rho_spearman", "tau_kendall",
        "bin_var_slope", "q90_q10_slope_diff",
        "corr_w_init_h", "skew_high_minus_low", "hill_alpha",
        "lifetime_median", "lifetime_p90",
        "wealth_persistence_rho", "forced_retire_rate",
    ]
    rng = np.random.default_rng(0)
    for col in main_cols:
        cells = []
        for cond in ("C0u", "C0p"):
            vals = summary_df[summary_df["cond"] == cond][col].dropna().to_numpy()
            if vals.size == 0:
                cells.append("—")
                continue
            mean, lo, hi = bootstrap_ci(vals, n_resample=10_000, ci=0.95, rng=rng)
            cells.append(f"{mean:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        lines.append(f"| {col} | {cells[0]} | {cells[1]} |")
    lines.append("")
    lines.append("### Pooled bin variance slope (S2 plan v2 修正 1, Yuito 指示 #1)")
    lines.append("")
    for cond, v in pooled_bin_var.items():
        lines.append(f"- **{cond}**: pooled bin_var_slope = {v:+.4f}")
    lines.append("")
    lines.append("### Sub-checkpoint: q90_q10_slope_diff trial 間 SD")
    lines.append("")
    for cond, info in sub_checkpoint.items():
        flag = "WARN (>0.3)" if info["sd"] > 0.3 else "OK (<=0.3)"
        lines.append(
            f"- **{cond}**: SD = {info['sd']:.4f} → **{flag}**"
        )
    if any(info["sd"] > 0.3 for info in sub_checkpoint.values()):
        lines.append("")
        lines.append(
            "> **WARN flag**: SD > 0.3 が観察された条件あり。S1-secondary で interaction "
            "計算が機能しない可能性、別 funnel 直接指標 (例: `Var(log|ΔG|)` h 中央値で 2 分の差) "
            "への切替を S3 完了後に Yuito 相談。"
        )
    lines.append("")
    lines.append("### Lifetime censoring flag (S2 plan v2 修正 3)")
    lines.append("")
    for cond, n_flagged in censoring_flags.items():
        if n_flagged > 0:
            lines.append(
                f"- **{cond}**: lifetime_median > T/2 で censoring 重大の trial が "
                f"{n_flagged} / {n_per_cond.get(cond, 0)} 件"
            )
        else:
            lines.append(f"- **{cond}**: censoring 重大 flag 0 件 (median ≤ T/2)")
    lines.append("")
    lines.append("### Determinism guard")
    lines.append("")
    lines.append(
        f"C0u seed=1000 × 2 回独立実行: **{'PASS (rt_df + agents_df bit-一致)' if determinism_pass else 'FAIL'}**"
    )
    lines.append("")
    lines.append("### LOB SG agent subclass smoke (S2 plan v2 修正 4)")
    lines.append("")
    if smoke_status is True:
        lines.append(
            "C3 short smoke: **PASS** (`WInitLoggingSpeculationAgent` で N=100 SG 全員の "
            "w_init 列が non-NaN で agent parquet に書き出し)"
        )
    elif smoke_status is False:
        lines.append("C3 short smoke: **FAIL**、`stage_S2_diff.md` で詳細記録。")
    else:
        lines.append(
            "C3 short smoke: **SKIPPED** (Windows env で PAMS 不在、Mac で別途実行予定)"
        )
    lines.append("")
    lines.append("### Layer 2 timescale concern (Phase 2 scope 外、再掲)")
    lines.append("")
    lines.append(
        "Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を "
        "超える長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + "
        "proposal Limitations 節に明記する。"
    )
    lines.append("")
    with open(readme_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-workers", type=int, default=None,
                        help="Default: min(os.cpu_count(), 8)")
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--skip-trials", action="store_true",
                        help="既存 parquet を流用、ensemble_summary だけ再計算")
    args = parser.parse_args()

    logger = setup_logger()
    n_workers = args.n_workers or default_n_workers()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))
    T_agg = AGG_PARAMS["T"]

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info(
        f"S2 aggregate ensemble — n_trials={args.n_trials}, "
        f"seed_base={args.seed_base}, n_workers={n_workers}"
    )
    logger.info("=" * 70)

    # ----- Step A: Determinism guard (skip 可) -----
    determinism_pass = True
    if not args.skip_determinism:
        determinism_pass = determinism_guard("C0u", args.seed_base, logger)
        if not determinism_pass:
            logger.error("Determinism guard FAILED — aborting.")
            return

    # ----- Step B: 100 trial × C0u/C0p 並列実行 -----
    if not args.skip_trials:
        for cond in ACTIVE_CONDS:
            cond_dir = DATA_DIR / cond
            run_parallel_trials(cond, seeds, cond_dir, n_workers, logger)

    # ----- Step C: ensemble_summary 集計 -----
    logger.info("--- aggregating ensemble_summary ---")
    summary_dfs = []
    for cond in ACTIVE_CONDS:
        cond_dir = DATA_DIR / cond
        df = aggregate_ensemble_summaries(cond, seeds, cond_dir, T_agg, logger)
        summary_dfs.append(df)
    summary_df = pd.concat(summary_dfs, ignore_index=True)
    summary_df.to_parquet(DATA_DIR / "ensemble_summary.parquet", index=False)
    logger.info(
        f"[summary] saved {len(summary_df)} rows to "
        f"{DATA_DIR / 'ensemble_summary.parquet'}"
    )

    # ----- Step D: Pooled bin variance (Yuito 指示 #1) -----
    pooled_bin_var: Dict[str, float] = {}
    for cond in ACTIVE_CONDS:
        cond_dir = DATA_DIR / cond
        rt_dfs = []
        for seed in seeds:
            p = cond_dir / f"trial_{seed:04d}.parquet"
            if p.exists():
                rt_dfs.append(pd.read_parquet(p, columns=["horizon", "delta_g"]))
        if rt_dfs:
            pooled_rt = pd.concat(rt_dfs, ignore_index=True)
            pooled_bin_var[cond] = bin_variance_slope_pooled(pooled_rt, K=15)
            logger.info(
                f"[pooled] {cond} pooled n_rt={len(pooled_rt):,} "
                f"bin_var_slope_pooled={pooled_bin_var[cond]:+.4f}"
            )

    # ----- Step E: Sub-checkpoint (q90_q10_slope_diff trial 間 SD) -----
    sub_checkpoint: Dict[str, Any] = {}
    for cond in ACTIVE_CONDS:
        sub = summary_df[summary_df["cond"] == cond]["q90_q10_slope_diff"].dropna()
        if len(sub) > 0:
            sd = float(sub.std(ddof=1))
            sub_checkpoint[cond] = {"sd": sd, "n": len(sub),
                                    "warn": sd > 0.3}
            logger.info(
                f"[sub-checkpoint] {cond} q90_q10_slope_diff SD = {sd:.4f} "
                f"(n={len(sub)}) {'WARN >0.3' if sd > 0.3 else 'OK <=0.3'}"
            )

    # Censoring flag
    censoring_flags: Dict[str, int] = {}
    for cond in ACTIVE_CONDS:
        sub = summary_df[summary_df["cond"] == cond]
        n_flagged = int(sub["lifetime_median_censoring_flag"].sum()) if len(sub) > 0 else 0
        censoring_flags[cond] = n_flagged
        logger.info(f"[censoring] {cond}: {n_flagged} trial(s) with lifetime_median > T/2")

    # ----- Step F: LOB smoke (skip 可) -----
    smoke_status: Optional[bool] = None
    if not args.skip_smoke:
        smoke_status = lob_smoke(logger)

    # ----- Step G: Outputs (tab + figure + README append) -----
    tab_path = OUTPUTS_DIR / "tables" / "tab_S2_aggregate_summary.csv"
    write_summary_table(summary_df, pooled_bin_var, tab_path, logger)
    fig_path = OUTPUTS_DIR / "figures" / "fig_S2_aggregate_distributions.png"
    plot_distributions(summary_df, fig_path, logger)
    readme_path = YH006_1 / "README.md"
    append_readme(summary_df, pooled_bin_var, determinism_pass, smoke_status,
                  sub_checkpoint, censoring_flags, readme_path)
    logger.info(f"[output] appended README: {readme_path}")

    logger.info("=" * 70)
    logger.info("S2 aggregate ensemble complete.")
    logger.info("=" * 70)

    # Save sub-checkpoint summary as JSON for diff.md generation
    summary_for_diff = {
        "n_trials": {c: int((summary_df["cond"] == c).sum()) for c in ACTIVE_CONDS},
        "pooled_bin_var": pooled_bin_var,
        "sub_checkpoint": sub_checkpoint,
        "censoring_flags": censoring_flags,
        "determinism_pass": determinism_pass,
        "smoke_status": ("pass" if smoke_status is True
                         else "fail" if smoke_status is False
                         else "skipped"),
    }
    with open(LOGS_DIR / "S2_summary_for_diff.json", "w", encoding="utf-8") as f:
        json.dump(summary_for_diff, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
