"""S5 Windows 側 — A1 ablation aggregation + KPI L2 判定.

S4 plan §3.6 / §3.7 / §3.8:
  1. Mac から転送された data/C2_A1/ data/C3_A1/ の整合性チェック (file 数、1 trial 読み)
  2. ensemble_summary.parquet を 400 → 600 行に拡張 (C0u/C0p/C2/C3 + C2_A1/C3_A1)
  3. A1 interaction = (C3_A1 − C2_A1) − (C0p − C0u) を 5 metrics × full で計算、bootstrap CI
  4. Pooled bin_var_slope 6 cond + A1 interaction value
  5. Shrinkage = S3 interaction − A1 interaction、bootstrap CI で「縮小は有意か」
  6. KPI L2 判定: shrinkage ≥ 50% かつ shrinkage CI が 0 を含まない
  7. tab_S5_ablation_interaction.csv, fig_S5_ablation_shrinkage.png, README 追記,
     S5_summary_for_diff.json

Run (Windows、Mac sim 完了後):
  cd experiments/YH006_1
  python -m code.aggregate_ablation_summary
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

from aggregate_ensemble import aggregate_ensemble_summaries  # noqa: E402
from analysis import bin_variance_slope_pooled  # noqa: E402
from config import CONDITIONS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS, LOB_PARAMS  # noqa: E402
from stats import bootstrap_ci  # noqa: E402

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"

A1_CONDS = ["C2_A1", "C3_A1"]
ALL_6_CONDS = ["C0u", "C0p", "C2", "C3", "C2_A1", "C3_A1"]
INTERACTION_METRICS = [
    "rho_pearson", "rho_spearman", "tau_kendall",
    "bin_var_slope", "q90_q10_slope_diff",
]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5-agg")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5_ablation_agg.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Integrity check (S3 と同 pattern)
# ---------------------------------------------------------------------------

def integrity_check(
    cond: str, seeds: List[int], q_const_expected: int, logger: logging.Logger,
) -> bool:
    cond_dir = DATA_DIR / cond
    expected_files = 4 * len(seeds)
    actual_files = sum(1 for _ in cond_dir.glob("*.parquet"))
    logger.info(f"[integrity] {cond}: {actual_files} / {expected_files} parquet files")
    if actual_files != expected_files:
        logger.error(f"[integrity] FAIL: expected {expected_files}, got {actual_files}")
        return False

    sample_seed = seeds[0]
    rt_p = cond_dir / f"trial_{sample_seed:04d}.parquet"
    if not rt_p.exists():
        logger.error(f"[integrity] FAIL: missing {rt_p}")
        return False
    rt_df = pd.read_parquet(rt_p)
    if len(rt_df) > 0:
        unique_q = sorted(rt_df["q"].unique().tolist())
        if unique_q != [q_const_expected]:
            logger.error(
                f"[integrity] FAIL: {cond} sample has q values {unique_q}, "
                f"expected single value [{q_const_expected}] (A1 ablation violation)"
            )
            return False
        logger.info(f"[integrity] {cond} sample: n_rt={len(rt_df)}, q == {q_const_expected} ✓")
    else:
        logger.warning(f"[integrity] {cond} sample n_rt=0 (許容、warmup 短縮の可能性)")
    logger.info(f"[integrity] {cond}: OK")
    return True


# ---------------------------------------------------------------------------
# Combine ensemble_summary 400 → 600 rows
# ---------------------------------------------------------------------------

def combine_to_600_rows(seeds: List[int], logger: logging.Logger) -> pd.DataFrame:
    existing_path = DATA_DIR / "ensemble_summary.parquet"
    if not existing_path.exists():
        raise FileNotFoundError(f"{existing_path} 不在。S3 aggregation 完了済が前提")
    df_existing = pd.read_parquet(existing_path)
    logger.info(f"[load] existing ensemble_summary: {len(df_existing)} rows, "
                f"conds={sorted(df_existing['cond'].unique().tolist())}")
    df_existing = df_existing[df_existing["cond"].isin(["C0u", "C0p", "C2", "C3"])].copy()

    T_lob = LOB_PARAMS["main_steps"]
    a1_dfs = []
    for cond in A1_CONDS:
        cond_dir = DATA_DIR / cond
        logger.info(f"[A1] computing ensemble_summary for {cond} (T={T_lob})...")
        df = aggregate_ensemble_summaries(cond, seeds, cond_dir, T_lob, logger)
        logger.info(f"[A1] {cond}: {len(df)} rows")
        a1_dfs.append(df)
    df_a1 = pd.concat(a1_dfs, ignore_index=True)

    df_full = pd.concat([df_existing, df_a1], ignore_index=True)
    df_full.to_parquet(existing_path, index=False)
    cnt = df_full.groupby("cond").size().to_dict()
    logger.info(f"[save] {existing_path}: {len(df_full)} rows, per-cond: {cnt}")
    return df_full


# ---------------------------------------------------------------------------
# A1 interaction + KPI L2
# ---------------------------------------------------------------------------

def compute_a1_interactions(
    df: pd.DataFrame, n_resample: int = 10_000,
) -> pd.DataFrame:
    """A1 interaction = (C3_A1 - C2_A1) - (C0p - C0u) per trial pair, bootstrap CI."""
    rng = np.random.default_rng(0)
    rows = []
    for metric in INTERACTION_METRICS:
        c0u = df[df["cond"] == "C0u"][metric].dropna().to_numpy()
        c0p = df[df["cond"] == "C0p"][metric].dropna().to_numpy()
        c2_a1 = df[df["cond"] == "C2_A1"][metric].dropna().to_numpy()
        c3_a1 = df[df["cond"] == "C3_A1"][metric].dropna().to_numpy()
        n = min(c0u.size, c0p.size, c2_a1.size, c3_a1.size)
        if n == 0:
            rows.append({"metric": metric, "interaction_mean": float("nan"),
                         "ci_lo": float("nan"), "ci_hi": float("nan"), "n": 0})
            continue
        inter = (c3_a1[:n] - c2_a1[:n]) - (c0p[:n] - c0u[:n])
        m, lo, hi = bootstrap_ci(inter, n_resample=n_resample, ci=0.95, rng=rng)
        rows.append({"metric": metric, "interaction_mean": float(m),
                     "ci_lo": float(lo), "ci_hi": float(hi), "n": int(n)})
    return pd.DataFrame(rows)


def load_s3_interactions() -> pd.DataFrame:
    """S3 で生成済の tab_S3_interaction.csv を読み込み."""
    p = OUTPUTS_DIR / "tables" / "tab_S3_interaction.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} 不在。S3 aggregation 完了済が前提。")
    return pd.read_csv(p)


def compute_shrinkage(
    df: pd.DataFrame, s3_inter: pd.DataFrame, a1_inter: pd.DataFrame,
    n_resample: int = 10_000,
) -> pd.DataFrame:
    """Shrinkage = S3_interaction - A1_interaction、各 metric で bootstrap CI 算出.

    bootstrap: trial-level S3 interaction 値 (100 個) と A1 interaction 値 (100 個) を
    それぞれ resample、mean の差で delta_shrinkage を構成。L2 判定基準:
    - shrinkage_ratio = |A1| / |S3| ≤ 0.5 (50% 以上縮小)
    - shrinkage CI が 0 を含まない (縮小が statistical に 有意)
    """
    rng = np.random.default_rng(0)
    s3_map = {r["metric"]: r for _, r in s3_inter.iterrows()}
    a1_map = {r["metric"]: r for _, r in a1_inter.iterrows()}

    rows = []
    for metric in INTERACTION_METRICS:
        # trial-level interaction arrays for S3 (C3-C2)-(C0p-C0u) and A1 (C3_A1-C2_A1)-(C0p-C0u)
        c0u = df[df["cond"] == "C0u"][metric].dropna().to_numpy()
        c0p = df[df["cond"] == "C0p"][metric].dropna().to_numpy()
        c2 = df[df["cond"] == "C2"][metric].dropna().to_numpy()
        c3 = df[df["cond"] == "C3"][metric].dropna().to_numpy()
        c2_a1 = df[df["cond"] == "C2_A1"][metric].dropna().to_numpy()
        c3_a1 = df[df["cond"] == "C3_A1"][metric].dropna().to_numpy()
        n = min(c0u.size, c0p.size, c2.size, c3.size, c2_a1.size, c3_a1.size)
        if n == 0:
            rows.append({"metric": metric, "s3_mean": float("nan"),
                         "a1_mean": float("nan"), "shrinkage_mean": float("nan"),
                         "shrinkage_lo": float("nan"), "shrinkage_hi": float("nan"),
                         "shrinkage_ratio": float("nan"), "L2_pass": False, "n": 0})
            continue
        s3_arr = (c3[:n] - c2[:n]) - (c0p[:n] - c0u[:n])
        a1_arr = (c3_a1[:n] - c2_a1[:n]) - (c0p[:n] - c0u[:n])
        delta = s3_arr - a1_arr
        s3_mean = float(s3_arr.mean())
        a1_mean = float(a1_arr.mean())
        d_m, d_lo, d_hi = bootstrap_ci(delta, n_resample=n_resample, ci=0.95, rng=rng)
        # ratio: |A1| / |S3| (smaller = more shrinkage)
        if abs(s3_mean) > 1e-10:
            ratio = abs(a1_mean) / abs(s3_mean)
        else:
            ratio = float("nan")
        # L2: shrinkage ≥ 50% (ratio ≤ 0.5) AND shrinkage CI doesn't contain 0
        ci_excludes_zero = (d_lo > 0) or (d_hi < 0)
        l2_pass = (ratio <= 0.5) and ci_excludes_zero
        rows.append({
            "metric": metric,
            "s3_mean": s3_mean,
            "a1_mean": a1_mean,
            "shrinkage_mean": float(d_m),
            "shrinkage_lo": float(d_lo),
            "shrinkage_hi": float(d_hi),
            "shrinkage_ratio": ratio,
            "ci_excludes_zero": bool(ci_excludes_zero),
            "L2_pass": bool(l2_pass),
            "n": int(n),
        })
    return pd.DataFrame(rows)


def compute_pooled_bin_var_6cond(
    seeds: List[int], logger: logging.Logger,
) -> Dict[str, float]:
    pooled: Dict[str, float] = {}
    for cond in ALL_6_CONDS:
        cond_dir = DATA_DIR / cond
        if not cond_dir.exists():
            logger.warning(f"[pooled] {cond}: dir not found, skip")
            pooled[cond] = float("nan")
            continue
        rt_dfs = []
        for seed in seeds:
            p = cond_dir / f"trial_{seed:04d}.parquet"
            if p.exists():
                rt_dfs.append(pd.read_parquet(p, columns=["horizon", "delta_g"]))
        if not rt_dfs:
            pooled[cond] = float("nan")
            continue
        pooled_rt = pd.concat(rt_dfs, ignore_index=True)
        pooled[cond] = bin_variance_slope_pooled(pooled_rt, K=15)
        logger.info(f"[pooled] {cond}: n_rt={len(pooled_rt):,} "
                    f"bin_var_slope_pooled={pooled[cond]:+.4f}")
    return pooled


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def plot_shrinkage(
    s3_inter: pd.DataFrame, a1_inter: pd.DataFrame, shrinkage_df: pd.DataFrame,
    out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    metrics = INTERACTION_METRICS
    n = len(metrics)
    fig, ax = plt.subplots(figsize=(max(7, 1.2 * n + 5), 5))
    x = np.arange(n)
    width = 0.35
    s3_means = [float(s3_inter[s3_inter["metric"] == m]["interaction_mean"].iloc[0])
                if (s3_inter["metric"] == m).any() else 0 for m in metrics]
    s3_lo = [float(s3_inter[s3_inter["metric"] == m]["ci_lo"].iloc[0])
             if (s3_inter["metric"] == m).any() else 0 for m in metrics]
    s3_hi = [float(s3_inter[s3_inter["metric"] == m]["ci_hi"].iloc[0])
             if (s3_inter["metric"] == m).any() else 0 for m in metrics]
    a1_means = [float(a1_inter[a1_inter["metric"] == m]["interaction_mean"].iloc[0])
                if (a1_inter["metric"] == m).any() else 0 for m in metrics]
    a1_lo = [float(a1_inter[a1_inter["metric"] == m]["ci_lo"].iloc[0])
             if (a1_inter["metric"] == m).any() else 0 for m in metrics]
    a1_hi = [float(a1_inter[a1_inter["metric"] == m]["ci_hi"].iloc[0])
             if (a1_inter["metric"] == m).any() else 0 for m in metrics]
    s3_err = [np.array(s3_means) - np.array(s3_lo), np.array(s3_hi) - np.array(s3_means)]
    a1_err = [np.array(a1_means) - np.array(a1_lo), np.array(a1_hi) - np.array(a1_means)]
    ax.bar(x - width / 2, s3_means, width, yerr=s3_err, capsize=4,
           color="#1f77b4", alpha=0.8, label="S3 baseline (C3 - C2) - (C0p - C0u)")
    ax.bar(x + width / 2, a1_means, width, yerr=a1_err, capsize=4,
           color="#d62728", alpha=0.8, label="A1 ablation (C3_A1 - C2_A1) - (C0p - C0u)")
    ax.axhline(0, color="black", linewidth=0.4, alpha=0.5)
    ax.set_xticks(x); ax.set_xticklabels(metrics, rotation=20, ha="right")
    ax.set_ylabel("Interaction value")
    # annotate L2 pass/fail
    for i, m in enumerate(metrics):
        row = shrinkage_df[shrinkage_df["metric"] == m]
        if len(row) > 0:
            l2 = bool(row["L2_pass"].iloc[0])
            ratio = float(row["shrinkage_ratio"].iloc[0])
            ax.annotate(
                f"L2 {'PASS' if l2 else 'fail'}\nratio={ratio:.2f}",
                xy=(i, max(a1_hi[i], s3_hi[i])),
                xytext=(0, 8), textcoords="offset points",
                ha="center", fontsize=8,
                color="green" if l2 else "gray",
            )
    ax.legend(loc="best", fontsize=9)
    ax.set_title("S5 — A1 ablation: interaction shrinkage vs S3 baseline\n"
                 "(L2 pass = shrinkage >= 50% AND CI excludes 0)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# README append
# ---------------------------------------------------------------------------

def append_readme(
    df: pd.DataFrame, q_const: int, pooled: Dict[str, float],
    s3_inter: pd.DataFrame, a1_inter: pd.DataFrame, shrinkage_df: pd.DataFrame,
    readme_path: Path,
) -> None:
    lines: List[str] = []
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Stage S5 — A1 ablation (C2_A1 / C3_A1) + KPI L2 判定")
    lines.append("")
    n_per_cond = df.groupby("cond").size().to_dict()
    lines.append("**実行範囲**: " + ", ".join(f"{c}: {n} trial" for c, n in n_per_cond.items()))
    lines.append("")
    lines.append(f"**q_const** = {q_const} (C3 100 trial の pooled median から較正、`logs/S4_q_const_calibration.json`)")
    lines.append("")

    # Pooled bin_var 6 cond
    lines.append("### Pooled bin_var_slope (6 条件)")
    lines.append("")
    lines.append("| cond | pooled bin_var_slope |")
    lines.append("|---|---:|")
    for c in ALL_6_CONDS:
        v = pooled.get(c, float("nan"))
        lines.append(f"| {c} | {v:+.4f} |")
    lines.append("")

    # S3 vs A1 interaction + shrinkage
    lines.append("### A1 interaction shrinkage vs S3 baseline (5 metrics)")
    lines.append("")
    lines.append("| metric | S3 mean [CI] | A1 mean [CI] | shrinkage [CI] | ratio | L2 |")
    lines.append("|---|---|---|---|---:|---|")
    s3_map = {r["metric"]: r for _, r in s3_inter.iterrows()}
    a1_map = {r["metric"]: r for _, r in a1_inter.iterrows()}
    for _, r in shrinkage_df.iterrows():
        m = r["metric"]
        s3 = s3_map.get(m)
        a1 = a1_map.get(m)
        s3_cell = (f"{s3['interaction_mean']:+.4f} [{s3['ci_lo']:+.4f}, {s3['ci_hi']:+.4f}]"
                   if s3 is not None else "—")
        a1_cell = (f"{a1['interaction_mean']:+.4f} [{a1['ci_lo']:+.4f}, {a1['ci_hi']:+.4f}]"
                   if a1 is not None else "—")
        sh = f"{r['shrinkage_mean']:+.4f} [{r['shrinkage_lo']:+.4f}, {r['shrinkage_hi']:+.4f}]"
        ratio_str = f"{r['shrinkage_ratio']:.3f}" if not np.isnan(r['shrinkage_ratio']) else "—"
        l2 = "**PASS**" if r["L2_pass"] else "fail"
        lines.append(f"| {m} | {s3_cell} | {a1_cell} | {sh} | {ratio_str} | {l2} |")
    lines.append("")
    lines.append("**L2 判定基準**: shrinkage ratio ≤ 0.5 (= 50% 以上縮小) AND shrinkage CI が 0 を含まない")
    lines.append("")
    l2_pass_count = int(shrinkage_df["L2_pass"].sum())
    lines.append(f"**L2 pass 件数: {l2_pass_count} / {len(INTERACTION_METRICS)}**")
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
    logger.info("S5 A1 ablation aggregation — 6 cond ensemble + L2 judgment")
    logger.info("=" * 70)

    # Load q_const from calibration
    cal_path = LOGS_DIR / "S4_q_const_calibration.json"
    if not cal_path.exists():
        raise FileNotFoundError(f"{cal_path} 不在。S4 calibration 完走済が前提")
    with open(cal_path, encoding="utf-8") as f:
        q_const = int(json.load(f)["q_const_primary"])
    logger.info(f"q_const = {q_const}")

    # Integrity
    for cond in A1_CONDS:
        if not integrity_check(cond, seeds, q_const, logger):
            logger.error(f"integrity failed for {cond}, aborting")
            return

    # Combine 400 → 600 rows
    df = combine_to_600_rows(seeds, logger)

    # Pooled bin_var 6 cond
    pooled = compute_pooled_bin_var_6cond(seeds, logger)

    # A1 interactions + shrinkage
    a1_inter = compute_a1_interactions(df)
    a1_inter.to_csv(OUTPUTS_DIR / "tables" / "tab_S5_ablation_interaction.csv", index=False)
    logger.info(f"[output] saved: tab_S5_ablation_interaction.csv")

    s3_inter = load_s3_interactions()
    shrinkage_df = compute_shrinkage(df, s3_inter, a1_inter)
    shrinkage_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S5_shrinkage.csv", index=False)
    logger.info(f"[output] saved: tab_S5_shrinkage.csv")
    for _, r in shrinkage_df.iterrows():
        logger.info(
            f"[L2] {r['metric']}: S3={r['s3_mean']:+.4f} → A1={r['a1_mean']:+.4f}, "
            f"shrinkage={r['shrinkage_mean']:+.4f} [{r['shrinkage_lo']:+.4f}, {r['shrinkage_hi']:+.4f}], "
            f"ratio={r['shrinkage_ratio']:.3f}, L2={'PASS' if r['L2_pass'] else 'fail'}"
        )

    # Figure
    plot_shrinkage(s3_inter, a1_inter, shrinkage_df,
                   OUTPUTS_DIR / "figures" / "fig_S5_ablation_shrinkage.png",
                   logger)

    # README append
    append_readme(df, q_const, pooled, s3_inter, a1_inter, shrinkage_df,
                  YH006_1 / "README.md")
    logger.info(f"[output] appended README")

    # JSON for diff
    summary = {
        "stage": "S5",
        "q_const": q_const,
        "n_trials_per_cond": {c: int((df["cond"] == c).sum()) for c in ALL_6_CONDS},
        "pooled_bin_var": pooled,
        "a1_interaction": a1_inter.to_dict(orient="records"),
        "s3_interaction": s3_inter.to_dict(orient="records"),
        "shrinkage": shrinkage_df.to_dict(orient="records"),
        "L2_pass_count": int(shrinkage_df["L2_pass"].sum()),
        "L2_total_metrics": int(len(INTERACTION_METRICS)),
    }
    with open(LOGS_DIR / "S5_summary_for_diff.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: S5_summary_for_diff.json")

    logger.info("=" * 70)
    logger.info(f"S5 aggregation complete. L2 pass: {summary['L2_pass_count']}/{summary['L2_total_metrics']}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
