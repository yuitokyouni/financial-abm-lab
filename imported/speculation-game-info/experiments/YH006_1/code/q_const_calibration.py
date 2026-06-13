"""S4 q_const calibration — C3 既存 100 trial parquet から ablation A1 用の固定注文サイズを較正.

GLOSSARY での当初設計: 「C3 pilot 5 trial から median(q_i(t))、5 trial の中央値」。
S3 完了で C3 100 trial 揃ったので、pooled / per-trial-median-of-medians を併走計算し、
両者が合致することを確認した上で **pooled median を主較正値** とする。

Yuito 確定方針 (S2 plan §0.7 修正 6): `q_const` は C2_A1 と C3_A1 の両方で同値を使う
(wealth → q 経路を切るための ablation design、両 wealth_mode で同 q を強制)。

Run (Windows):
  cd experiments/YH006_1
  python -m code.q_const_calibration [--cond C3] [--seed-base 1000] [--n-trials 100]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S4-cal")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S4_q_const_calibration.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def calibrate(
    cond: str, seeds: List[int], logger: logging.Logger,
) -> Dict[str, Any]:
    cond_dir = DATA_DIR / cond
    if not cond_dir.exists():
        raise FileNotFoundError(
            f"{cond_dir} 不在。S3 LOB ensemble 完走済の parquet が必要。"
        )

    per_trial_medians: List[float] = []
    pooled_q: List[int] = []
    n_rt_total = 0
    for seed in seeds:
        p = cond_dir / f"trial_{seed:04d}.parquet"
        if not p.exists():
            logger.warning(f"missing {p}, skip")
            continue
        df = pd.read_parquet(p, columns=["q"])
        if len(df) == 0:
            logger.warning(f"empty {p}, skip")
            continue
        q_arr = df["q"].to_numpy(dtype=np.int64)
        per_trial_medians.append(float(np.median(q_arr)))
        pooled_q.append(q_arr)
        n_rt_total += q_arr.size

    if not pooled_q:
        raise RuntimeError("no usable C3 trial parquets found")

    pooled = np.concatenate(pooled_q)
    pooled_median = float(np.median(pooled))
    pooled_p25 = float(np.percentile(pooled, 25))
    pooled_p75 = float(np.percentile(pooled, 75))
    pooled_mean = float(pooled.mean())
    median_of_trial_medians = float(np.median(per_trial_medians))
    sd_of_trial_medians = float(np.std(per_trial_medians, ddof=1))

    # Primary: pooled median (整数化、PAMS 注文サイズは int)
    q_const_primary = int(round(pooled_median))

    logger.info("=" * 70)
    logger.info(f"q_const calibration — cond={cond}, n_trials={len(per_trial_medians)}, n_rt_total={n_rt_total:,}")
    logger.info("=" * 70)
    logger.info(f"pooled q distribution:")
    logger.info(f"  median = {pooled_median:.2f} (→ q_const_primary = {q_const_primary})")
    logger.info(f"  mean   = {pooled_mean:.2f}")
    logger.info(f"  p25    = {pooled_p25:.2f}")
    logger.info(f"  p75    = {pooled_p75:.2f}")
    logger.info(f"per-trial median 統計 (n={len(per_trial_medians)} trial):")
    logger.info(f"  median of medians = {median_of_trial_medians:.2f}")
    logger.info(f"  SD of medians     = {sd_of_trial_medians:.3f}")
    logger.info(f"agreement check: |pooled_median - median_of_trial_medians| = "
                f"{abs(pooled_median - median_of_trial_medians):.3f}")

    return {
        "cond": cond,
        "n_trials": len(per_trial_medians),
        "n_rt_total": int(n_rt_total),
        "pooled_median": pooled_median,
        "pooled_mean": pooled_mean,
        "pooled_p25": pooled_p25,
        "pooled_p75": pooled_p75,
        "median_of_trial_medians": median_of_trial_medians,
        "sd_of_trial_medians": sd_of_trial_medians,
        "q_const_primary": q_const_primary,
        "timestamp": datetime.now().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cond", type=str, default="C3",
                        help="calibration source cond (default: C3)")
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    args = parser.parse_args()

    logger = setup_logger()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))
    result = calibrate(args.cond, seeds, logger)

    out_path = LOGS_DIR / "S4_q_const_calibration.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info(f"saved: {out_path}")
    logger.info(f"--> q_const = {result['q_const_primary']} (C2_A1 / C3_A1 で共通使用)")


if __name__ == "__main__":
    main()
