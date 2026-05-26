"""S5.6 — Windows 側 集計 + 判定 (H_artifact_mmfcn / H_artifact_negated / ambiguous).

S5.6 plan v1 §3.4 / §3.5:
  - data/mmfcn_sensitivity/{setting}_{seed}/ から 4 parquet 読込
  - 設定別の n_rt (mean, range)、forced_retire_rate、lifetime p25 / conditional median /
    censoring 率を計算
  - mmfcn_2x / mmfcn_1x の RT 比で H_artifact_mmfcn / H_artifact_negated / ambiguous 判定
  - baseline (mmfcn_1x, seed=1000) と data/C3/trial_1000.parquet の bit-一致 / semantic
    一致を sanity check

Run (Windows、Mac sweep 完了後):
  cd experiments/YH006_1
  python -m code.aggregate_mmfcn_sensitivity
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
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

DATA_DIR = YH006_1 / "data"
OUTPUTS_DIR = YH006_1 / "outputs"
LOGS_DIR = YH006_1 / "logs"
SWEEP_DIR = DATA_DIR / "mmfcn_sensitivity"

DEFAULT_SETTINGS = ["mmfcn_05x", "mmfcn_1x", "mmfcn_2x", "mmfcn_4x"]
SETTING_ORDER_VOLUME = {
    "mmfcn_05x": 15, "mmfcn_1x": 30, "mmfcn_2x": 60, "mmfcn_4x": 120,
}
DEFAULT_SEEDS = [1000, 1001]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.6-agg")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.6_aggregation.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# baseline 一致確認 (§3.2)
# ---------------------------------------------------------------------------

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def check_baseline_consistency(
    seed: int, logger: logging.Logger,
) -> Dict[str, str]:
    """`mmfcn_1x_{seed}` と `data/C3/trial_{seed}.parquet` を比較.

    parquet bit-一致 (sha256) を check、不一致なら semantic 一致 (n_rt, 列値) を check。
    """
    new_trial = SWEEP_DIR / f"mmfcn_1x_{seed:04d}" / f"trial_{seed:04d}.parquet"
    ref_trial = DATA_DIR / "C3" / f"trial_{seed:04d}.parquet"
    if not new_trial.exists():
        return {"verdict": "missing_new",
                "message": f"baseline run not found: {new_trial}"}
    if not ref_trial.exists():
        return {"verdict": "missing_ref",
                "message": f"reference parquet not found: {ref_trial}"}

    new_sha = _sha256(new_trial)
    ref_sha = _sha256(ref_trial)
    if new_sha == ref_sha:
        logger.info(f"[baseline] mmfcn_1x seed={seed}: bit-一致 PASS (sha256={new_sha[:16]}...)")
        return {"verdict": "bit_identical",
                "message": f"sha256={new_sha[:16]}..."}
    # semantic 比較
    new_df = pd.read_parquet(new_trial)
    ref_df = pd.read_parquet(ref_trial)
    n_rt_match = len(new_df) == len(ref_df)
    cols_match = sorted(new_df.columns.tolist()) == sorted(ref_df.columns.tolist())
    msg = (f"bit-不一致 (new={new_sha[:16]}, ref={ref_sha[:16]}), "
           f"n_rt new={len(new_df)} ref={len(ref_df)}, cols_match={cols_match}")
    logger.warning(f"[baseline] mmfcn_1x seed={seed}: {msg}")
    if n_rt_match and cols_match:
        # 主要列値で semantic 一致 check (delta_g sum, q sum 等)
        if "delta_g" in new_df.columns:
            dg_diff = float(np.abs(new_df["delta_g"].sum() - ref_df["delta_g"].sum()))
            if dg_diff < 1e-6:
                return {"verdict": "semantic_identical", "message": msg}
        return {"verdict": "semantic_likely_identical", "message": msg}
    return {"verdict": "semantic_different", "message": msg}


# ---------------------------------------------------------------------------
# §3.4 集計
# ---------------------------------------------------------------------------

def collect_trial_stats(
    setting: str, seed: int,
) -> Optional[Dict[str, float]]:
    """1 (setting, seed) の 4 parquet から stats を抽出.

    Returns: dict with n_rt, forced_retire_rate, lifetime stats, plus
             proxy fill-ease metrics (rt_rate_per_agent_step, n_substitutions,
             agent_lifetime_mean) from existing parquet — true fill_rate
             requires Mac-side instrumentation 追加 (本 version では未測定)。
    """
    base = SWEEP_DIR / f"{setting}_{seed:04d}"
    trial_p = base / f"trial_{seed:04d}.parquet"
    agents_p = base / f"agents_{seed:04d}.parquet"
    lt_p = base / f"lifetimes_{seed:04d}.parquet"
    if not (trial_p.exists() and agents_p.exists() and lt_p.exists()):
        return None
    trial = pd.read_parquet(trial_p)
    agents = pd.read_parquet(agents_p)
    lt = pd.read_parquet(lt_p)
    n_rt = int(len(trial))
    # forced_retire_rate = forced_retired 数 / N_sg (= 100)
    forced_retire_rate = float(agents["forced_retired"].mean()) if "forced_retired" in agents.columns else float("nan")
    # n_substitutions (lifetime samples 数 - 100 = 中途交代回数の合計に近似)
    n_substitutions = max(0, int(len(lt)) - int(len(agents)))
    # SG fill 困難度 proxy: per agent-step RT rate
    # = n_rt / (N_sg × main_steps)、main_steps は LOB_PARAMS から
    from config import LOB_PARAMS  # noqa: E402
    n_sg = int(len(agents))
    main_steps = int(LOB_PARAMS["main_steps"])
    rt_rate_per_agent_step = n_rt / (n_sg * main_steps) if (n_sg * main_steps) else float("nan")
    # agent lifetime distribution (final lifetime per agent)
    agent_lifetime_mean = float(agents["lifetime"].mean()) if "lifetime" in agents.columns else float("nan")
    # lifetime sample stats
    if len(lt):
        lifetimes = lt["lifetime"].astype(float).to_numpy()
        censored = lt["censored"].astype(bool).to_numpy() if "censored" in lt.columns else np.zeros(len(lt), dtype=bool)
        p25 = float(np.percentile(lifetimes, 25))
        censoring_rate = float(censored.mean())
        cond_median = (float(np.median(lifetimes[~censored])) if (~censored).sum() > 0
                       else float("nan"))
        n_total = int(len(lt))
        n_censored = int(censored.sum())
    else:
        p25, cond_median, censoring_rate = float("nan"), float("nan"), float("nan")
        n_total, n_censored = 0, 0
    return {
        "setting": setting,
        "order_volume": SETTING_ORDER_VOLUME.get(setting, -1),
        "seed": seed,
        "n_rt": n_rt,
        "rt_rate_per_agent_step": rt_rate_per_agent_step,
        "n_substitutions": n_substitutions,
        "agent_lifetime_mean": agent_lifetime_mean,
        "forced_retire_rate": forced_retire_rate,
        "lifetime_p25": p25,
        "conditional_median": cond_median,
        "censoring_rate": censoring_rate,
        "n_lifetime_samples": n_total,
        "n_censored": n_censored,
    }


def aggregate_by_setting(per_trial_df: pd.DataFrame) -> pd.DataFrame:
    """設定別に mean/min/max を集約."""
    rows = []
    for setting in DEFAULT_SETTINGS:
        sub = per_trial_df[per_trial_df["setting"] == setting]
        if len(sub) == 0:
            continue
        rows.append({
            "setting": setting,
            "order_volume": SETTING_ORDER_VOLUME[setting],
            "n_trials": int(len(sub)),
            "n_rt_mean": float(sub["n_rt"].mean()),
            "n_rt_min": int(sub["n_rt"].min()),
            "n_rt_max": int(sub["n_rt"].max()),
            "rt_rate_per_agent_step_mean": float(sub["rt_rate_per_agent_step"].mean()),
            "n_substitutions_mean": float(sub["n_substitutions"].mean()),
            "agent_lifetime_mean": float(sub["agent_lifetime_mean"].mean()),
            "forced_retire_rate_mean": float(sub["forced_retire_rate"].mean()),
            "lifetime_p25_mean": float(sub["lifetime_p25"].mean()),
            "conditional_median_mean": float(sub["conditional_median"].mean()),
            "censoring_rate_mean": float(sub["censoring_rate"].mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# §3.5 判定
# ---------------------------------------------------------------------------

def classify_mmfcn_artifact(agg_df: pd.DataFrame) -> Tuple[str, str, Dict[str, float]]:
    """弾力性 (ε = d log(n_rt) / d log(orderVolume)) ベースの判定 (Yuito 2026-05-19).

    旧式 (ratio_2x / ratio_4x 閾値) は H_artifact_negated の 1.2 閾値が厳しく、
    実測 ratio_2x ≈ 1.24 で簡単に ambiguous に落ちる。経済学の elasticity 概念
    (ε=0 完全独立、ε=1 線形供給依存) で連続的に判定する方が頑健。

    判定基準 (Yuito 提示、本 version):
      ε ≤ 0.3  → MMFCN は副次的供給源 (独立性高)、Phase 2 finding 頑健
      ε ≥ 0.7  → MMFCN 強依存 (bottleneck)、Phase 2 結論 refactor
      0.3 < ε < 0.7 → 中間、Yuito 議論
    補助: SG fill_rate proper は parquet になく、代わりに `rt_rate_per_agent_step`
    の 4x/1x 比を proxy として併記 (理想は MMFCN saver 拡張、本 version では未実装)。
    """
    def n_rt(setting: str) -> float:
        sub = agg_df[agg_df["setting"] == setting]
        return float(sub["n_rt_mean"].iloc[0]) if len(sub) else float("nan")

    def rt_rate(setting: str) -> float:
        sub = agg_df[agg_df["setting"] == setting]
        return float(sub["rt_rate_per_agent_step_mean"].iloc[0]) if len(sub) else float("nan")

    rt_05x = n_rt("mmfcn_05x"); rt_1x = n_rt("mmfcn_1x")
    rt_2x = n_rt("mmfcn_2x"); rt_4x = n_rt("mmfcn_4x")
    rt_rate_1x = rt_rate("mmfcn_1x"); rt_rate_4x = rt_rate("mmfcn_4x")

    ratio_2x = rt_2x / rt_1x if rt_1x else float("nan")
    ratio_4x = rt_4x / rt_1x if rt_1x else float("nan")
    ratio_05x = rt_05x / rt_1x if rt_1x else float("nan")
    # 弾力性: 4x → 線形なら 4倍 → ε=1。1.42 倍なら ε = log(1.42)/log(4) ≈ 0.25
    elasticity_4x = float(np.log(ratio_4x) / np.log(4.0)) if ratio_4x and ratio_4x > 0 else float("nan")
    elasticity_2x = float(np.log(ratio_2x) / np.log(2.0)) if ratio_2x and ratio_2x > 0 else float("nan")
    # rt_rate proxy ratio (Yuito mandate: SG fill ease 代替)
    rt_rate_ratio_4x = (rt_rate_4x / rt_rate_1x
                        if rt_rate_1x and not np.isnan(rt_rate_1x) else float("nan"))

    ratios = {
        "n_rt_ratio_05x_over_1x": ratio_05x,
        "n_rt_ratio_2x_over_1x": ratio_2x,
        "n_rt_ratio_4x_over_1x": ratio_4x,
        "elasticity_4x": elasticity_4x,
        "elasticity_2x": elasticity_2x,
        "rt_rate_ratio_4x_over_1x_proxy": rt_rate_ratio_4x,
        "n_rt_baseline_1x": rt_1x,
        "rt_rate_per_agent_step_1x": rt_rate_1x,
    }

    if np.isnan(elasticity_4x):
        return ("inconclusive",
                "baseline mmfcn_1x or 4x missing — cannot compute elasticity",
                ratios)

    if elasticity_4x <= 0.3:
        verdict_msg = (
            f"elasticity ε(4x)={elasticity_4x:.3f} ≤ 0.3、"
            f"n_rt(4x)/(1x)={ratio_4x:.2f} (期待 4.0、線形供給依存ならば)、"
            f"rt_rate proxy ratio={rt_rate_ratio_4x:.2f} → "
            f"**MMFCN は副次的供給源 (独立性高)**、Phase 2 finding 頑健、S6 進行可"
        )
        return ("H_artifact_negated_strong", verdict_msg, ratios)
    if elasticity_4x >= 0.7:
        verdict_msg = (
            f"elasticity ε(4x)={elasticity_4x:.3f} ≥ 0.7、"
            f"n_rt(4x)/(1x)={ratio_4x:.2f} → "
            f"**MMFCN 強依存 (bottleneck)**、Phase 2 結論 refactor"
        )
        return ("H_artifact_mmfcn", verdict_msg, ratios)
    return ("ambiguous",
            f"elasticity ε(4x)={elasticity_4x:.3f} ∈ (0.3, 0.7)、"
            f"n_rt(4x)/(1x)={ratio_4x:.2f}、"
            f"rt_rate proxy={rt_rate_ratio_4x:.2f} → 中間、Yuito 議論", ratios)


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def plot_scan(
    per_trial_df: pd.DataFrame, agg_df: pd.DataFrame,
    out_path: Path, logger: logging.Logger,
) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(11, 9))

    x_setting = [SETTING_ORDER_VOLUME[s] for s in agg_df["setting"]]
    # (1) n_rt vs orderVolume
    ax = axes[0][0]
    ax.errorbar(x_setting, agg_df["n_rt_mean"],
                yerr=[agg_df["n_rt_mean"] - agg_df["n_rt_min"],
                      agg_df["n_rt_max"] - agg_df["n_rt_mean"]],
                fmt="o-", capsize=4)
    ax.set_xscale("log"); ax.set_xticks(x_setting); ax.set_xticklabels(x_setting)
    ax.set_xlabel("MMFCN orderVolume"); ax.set_ylabel("SG per-trial n_rt (mean, [min,max])")
    ax.set_title("n_rt vs MMFCN orderVolume")
    ax.grid(alpha=0.3)

    # (2) forced_retire_rate
    ax = axes[0][1]
    ax.plot(x_setting, agg_df["forced_retire_rate_mean"], "o-")
    ax.set_xscale("log"); ax.set_xticks(x_setting); ax.set_xticklabels(x_setting)
    ax.set_xlabel("MMFCN orderVolume"); ax.set_ylabel("forced_retire_rate (mean)")
    ax.set_title("Forced retirement rate vs MMFCN orderVolume")
    ax.grid(alpha=0.3)

    # (3) lifetime stats
    ax = axes[1][0]
    ax.plot(x_setting, agg_df["lifetime_p25_mean"], "o-", label="p25 (mean)")
    ax.plot(x_setting, agg_df["conditional_median_mean"], "s-", label="cond_median")
    ax.set_xscale("log"); ax.set_xticks(x_setting); ax.set_xticklabels(x_setting)
    ax.set_xlabel("MMFCN orderVolume"); ax.set_ylabel("lifetime (steps)")
    ax.set_title("Lifetime stats vs MMFCN orderVolume")
    ax.legend(); ax.grid(alpha=0.3)

    # (4) censoring rate
    ax = axes[1][1]
    ax.plot(x_setting, agg_df["censoring_rate_mean"], "o-")
    ax.set_xscale("log"); ax.set_xticks(x_setting); ax.set_xticklabels(x_setting)
    ax.set_xlabel("MMFCN orderVolume"); ax.set_ylabel("censoring rate")
    ax.set_title("Censoring rate vs MMFCN orderVolume")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"[output] saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger = setup_logger()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("S5.6 aggregate_mmfcn_sensitivity")
    logger.info("=" * 70)

    if not SWEEP_DIR.exists():
        logger.error(f"sweep data dir not found: {SWEEP_DIR}. Mac sweep 未実行?")
        return

    # §3.2 baseline 一致確認
    baseline_checks = {}
    for seed in DEFAULT_SEEDS:
        baseline_checks[seed] = check_baseline_consistency(seed, logger)

    # §3.4 全 (setting, seed) 集計
    per_trial_rows = []
    for setting in DEFAULT_SETTINGS:
        for seed in DEFAULT_SEEDS:
            stats = collect_trial_stats(setting, seed)
            if stats is None:
                logger.warning(f"[collect] {setting} seed={seed}: parquet missing")
                continue
            per_trial_rows.append(stats)
            logger.info(
                f"[collect] {setting} seed={seed}: n_rt={stats['n_rt']:,} "
                f"forced_retire={stats['forced_retire_rate']:.3f} "
                f"p25={stats['lifetime_p25']:.1f} cens={stats['censoring_rate']:.1%}"
            )
    per_trial_df = pd.DataFrame(per_trial_rows)
    if len(per_trial_df) == 0:
        logger.error("no per-trial stats collected. abort.")
        return

    agg_df = aggregate_by_setting(per_trial_df)
    agg_df.to_csv(OUTPUTS_DIR / "tables" / "tab_S5.6_mmfcn_sensitivity.csv",
                  index=False)
    logger.info(f"[output] saved: tab_S5.6_mmfcn_sensitivity.csv ({len(agg_df)} rows)")

    # §3.5 判定
    verdict_name, verdict_msg, ratios = classify_mmfcn_artifact(agg_df)
    logger.info(f"[verdict] §3.5: {verdict_name} — {verdict_msg}")

    # figure
    plot_scan(per_trial_df, agg_df,
              OUTPUTS_DIR / "figures" / "fig_S5.6_mmfcn_scan.png", logger)

    # summary JSON
    summary = {
        "stage": "S5.6",
        "baseline_checks": baseline_checks,
        "per_trial_stats": per_trial_df.to_dict(orient="records"),
        "aggregate": agg_df.to_dict(orient="records"),
        "ratios": ratios,
        "verdict": verdict_name,
        "verdict_message": verdict_msg,
        "note": "mmfcn_fill_rate (plan §2.4) は OrderTrackingSaver の "
                "log 追加 export を要するため本 version では未測定。判定は "
                "n_rt + forced_retire + lifetime のみで実施。",
    }
    out_json = LOGS_DIR / "S5.6_summary_for_diff.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {out_json}")

    logger.info("=" * 70)
    logger.info(f"S5.6 aggregation complete. Verdict: {verdict_name}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
