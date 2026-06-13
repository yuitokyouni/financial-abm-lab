"""S3 Windows 側 step 1: Mac から転送された LOB parquet を ensemble_summary に結合.

S3 plan v2 §3.5:
  1. Mac から転送された data/C2/ data/C3/ の整合性チェック (file 数、1 trial 読み)
  2. 既存 data/ensemble_summary.parquet (S2 完走時 200 行 = C0u/C0p) を読む
  3. C2/C3 各 100 trial の trial-level metrics を計算 (aggregate_ensemble.py の
     `aggregate_ensemble_summaries` を流用、T_total = LOB_PARAMS["main_steps"])
  4. 4 条件結合 400 行版を data/ensemble_summary.parquet に上書き保存

Run (Windows):
  cd experiments/YH006_1
  python -m code.combine_ensemble_summaries [--conds C2,C3]
                                            [--seed-base 1000] [--n-trials 100]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from aggregate_ensemble import aggregate_ensemble_summaries  # noqa: E402
from config import CONDITIONS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS, LOB_PARAMS  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"

LOB_CONDS_DEFAULT = ["C2", "C3"]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S3-combine")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S3_combine.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def integrity_check(
    cond: str, seeds: List[int], cond_dir: Path, logger: logging.Logger,
) -> bool:
    """Mac 転送 parquet の整合性チェック (§3.5 step 3)."""
    expected_files = 4 * len(seeds)
    actual_files = sum(1 for _ in cond_dir.glob("*.parquet"))
    logger.info(f"[integrity] {cond}: {actual_files} / {expected_files} parquet files")
    if actual_files != expected_files:
        logger.error(
            f"[integrity] FAIL: {cond} expected {expected_files} files, got {actual_files}"
        )
        return False

    sample_seed = seeds[0]
    sample_paths = {
        "rt": cond_dir / f"trial_{sample_seed:04d}.parquet",
        "agents": cond_dir / f"agents_{sample_seed:04d}.parquet",
        "lifetimes": cond_dir / f"lifetimes_{sample_seed:04d}.parquet",
        "wealth_ts": cond_dir / f"wealth_ts_{sample_seed:04d}.parquet",
    }
    for k, p in sample_paths.items():
        if not p.exists():
            logger.error(f"[integrity] FAIL: missing {p}")
            return False
        df = pd.read_parquet(p)
        logger.info(f"[integrity] {cond} sample {k}: {len(df)} rows, cols={list(df.columns)}")

    agents_df = pd.read_parquet(sample_paths["agents"])
    n_winit_nan = int(agents_df["w_init"].isna().sum())
    if n_winit_nan > 0:
        logger.error(
            f"[integrity] FAIL: {cond} sample agents.w_init has {n_winit_nan} NaN "
            f"(WInitLoggingSpeculationAgent wiring 不具合の可能性)"
        )
        return False
    logger.info(f"[integrity] {cond}: OK")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conds", type=str, default=",".join(LOB_CONDS_DEFAULT))
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    args = parser.parse_args()

    logger = setup_logger()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))
    conds = [c.strip() for c in args.conds.split(",") if c.strip()]
    for c in conds:
        assert CONDITIONS[c].world == "lob", f"{c} is not LOB cond"

    logger.info("=" * 70)
    logger.info(f"S3 combine — conds={conds}, n_trials={args.n_trials}")
    logger.info("=" * 70)

    # ----- Step 1: integrity check -----
    for cond in conds:
        cond_dir = DATA_DIR / cond
        if not integrity_check(cond, seeds, cond_dir, logger):
            logger.error(f"integrity check failed for {cond} — aborting")
            return

    # ----- Step 2: read existing ensemble_summary (S2 200 rows, C0u/C0p) -----
    existing_path = DATA_DIR / "ensemble_summary.parquet"
    if existing_path.exists():
        df_agg = pd.read_parquet(existing_path)
        logger.info(f"[load] existing ensemble_summary: {len(df_agg)} rows, "
                    f"conds={sorted(df_agg['cond'].unique().tolist())}")
        df_agg = df_agg[df_agg["cond"].isin(["C0u", "C0p"])].copy()
        logger.info(f"[load] kept C0u/C0p rows: {len(df_agg)}")
    else:
        logger.warning(f"[load] {existing_path} 不在、aggregate 行は空で開始")
        df_agg = pd.DataFrame()

    # ----- Step 3: compute LOB ensemble_summary rows -----
    T_lob = LOB_PARAMS["main_steps"]
    lob_dfs = []
    for cond in conds:
        cond_dir = DATA_DIR / cond
        logger.info(f"[lob] computing ensemble_summary for {cond} (T={T_lob})...")
        df = aggregate_ensemble_summaries(cond, seeds, cond_dir, T_lob, logger)
        logger.info(f"[lob] {cond}: {len(df)} rows")
        lob_dfs.append(df)

    df_lob = pd.concat(lob_dfs, ignore_index=True)

    # ----- Step 4: combine + save -----
    if len(df_agg) > 0:
        df_full = pd.concat([df_agg, df_lob], ignore_index=True)
    else:
        df_full = df_lob
    df_full.to_parquet(existing_path, index=False)
    logger.info(
        f"[save] {existing_path}: {len(df_full)} rows "
        f"(conds={sorted(df_full['cond'].unique().tolist())})"
    )

    cnt = df_full.groupby("cond").size().to_dict()
    logger.info(f"[counts] per-cond: {cnt}")

    logger.info("=" * 70)
    logger.info("S3 combine complete. Next: aggregate_full_summary.py")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
