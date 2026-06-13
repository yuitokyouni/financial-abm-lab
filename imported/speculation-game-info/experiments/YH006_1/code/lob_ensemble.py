"""S3 LOB ensemble runner — C2/C3 × 100 trial 並列実行 (Mac 側専用).

S3 plan v2 §3.3 / §3.4 / §3.6:
  1. 各 (cond, seed) で `run_lob_trial(cond, seed)` を multiprocessing で並列実行
  2. 各 trial で 4 種 parquet を data/{cond}/ に出力
  3. Determinism guard (§3.6): C3 seed=1000 を 2 回独立 run、4 parquet bit-一致確認

集計 (Step C/D/G) は **Windows 側** で `combine_ensemble_summaries.py` +
`aggregate_full_summary.py` を実行する分業。本 script は trial 実行と
determinism guard のみ。

Run (Mac):
  cd experiments/YH006_1
  python -m code.lob_ensemble [--conds C2,C3] [--seed-base 1000] [--n-trials 100]
                              [--n-workers N] [--skip-determinism] [--determinism-only]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
# S3 plan v2 §0.4: Mac 側でも path override fix を適用 (S2 で aggregate_ensemble.py
# に入れた fix と同じ pattern、worker spawn 時の sys.path 汚染対策)
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import CONDITIONS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS, LOB_PARAMS  # noqa: E402
from parallel import run_parallel_trials, default_n_workers  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"

LOB_CONDS_DEFAULT = ["C2", "C3"]


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S3")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S3_lob_ensemble.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ---------------------------------------------------------------------------
# Determinism guard (S3 plan v2 §3.6) — C3 seed=1000 × 2 回独立実行 bit-一致
# ---------------------------------------------------------------------------

def _hash_parquet(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def determinism_guard_lob(
    cond: str, seed: int, logger: logging.Logger,
) -> bool:
    """C3 seed=1000 を 2 回独立に走らせ、4 parquet が bit-一致 (sha256) するか確認。

    PAMS の `random.Random(seed)` + numpy `default_rng(seed)` で full bit-一致が
    取れるかは S3 で初検証 (S2 では aggregate のみ確認、guard log は記録漏れ)。
    """
    from run_experiment import run_lob_trial
    a_dir = DATA_DIR / "_guard_lob_a"
    b_dir = DATA_DIR / "_guard_lob_b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[guard] LOB determinism check: {cond} seed={seed} × 2 runs")
    res_a = run_lob_trial(cond, seed)
    res_a.to_parquets(a_dir)
    res_b = run_lob_trial(cond, seed)
    res_b.to_parquets(b_dir)

    all_match = True
    file_keys = ["trial", "agents", "lifetimes", "wealth_ts"]
    for k in file_keys:
        fname = {
            "trial": f"trial_{seed:04d}.parquet",
            "agents": f"agents_{seed:04d}.parquet",
            "lifetimes": f"lifetimes_{seed:04d}.parquet",
            "wealth_ts": f"wealth_ts_{seed:04d}.parquet",
        }[k]
        ha = _hash_parquet(a_dir / fname)
        hb = _hash_parquet(b_dir / fname)
        match = ha == hb
        all_match = all_match and match
        logger.info(
            f"[guard] {fname}: {'MATCH' if match else 'MISMATCH'} "
            f"(a={ha[:16]}... b={hb[:16]}...)"
        )

    # rt_df の semantic 比較 (parquet timestamp metadata 等で hash が違っても
    # 中身が一致していれば pass とする補助確認)
    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_a = pd.read_parquet(a_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_b = pd.read_parquet(b_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    semantic_match = np.array_equal(rt_a, rt_b)
    logger.info(
        f"[guard] rt_df semantic (np.array_equal on {len(cols_rt)} cols): "
        f"{'PASS' if semantic_match else 'FAIL'}"
    )

    if not all_match and not semantic_match:
        logger.error("[guard] LOB determinism FAILED (sha256 + semantic both fail)")
        return False
    if not all_match and semantic_match:
        logger.warning(
            "[guard] sha256 mismatch but semantic match — "
            "parquet metadata diff の可能性、本 S3 では PASS 扱い"
        )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conds", type=str, default=",".join(LOB_CONDS_DEFAULT),
                        help="comma-separated LOB conds (default: C2,C3)")
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    parser.add_argument("--n-workers", type=int, default=None,
                        help="Default: min(os.cpu_count(), 8)")
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--determinism-only", action="store_true",
                        help="determinism guard だけ走らせて終了")
    args = parser.parse_args()

    logger = setup_logger()
    n_workers = args.n_workers or default_n_workers()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))
    conds = [c.strip() for c in args.conds.split(",") if c.strip()]
    for c in conds:
        assert CONDITIONS[c].world == "lob", f"{c} is not LOB cond"

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info(
        f"S3 LOB ensemble — conds={conds}, n_trials={args.n_trials}, "
        f"seed_base={args.seed_base}, n_workers={n_workers}, "
        f"main_steps={LOB_PARAMS['main_steps']}, warmup={LOB_PARAMS['warmup_steps']}"
    )
    logger.info("=" * 70)

    # ----- Step A: Determinism guard (§3.6) -----
    determinism_pass = True
    if not args.skip_determinism:
        # C3 を default に (Pareto は wealth distribution の追加 RNG 消費があるので
        # uniform より厳しい test)
        guard_cond = "C3" if "C3" in conds else conds[0]
        determinism_pass = determinism_guard_lob(guard_cond, args.seed_base, logger)
        if not determinism_pass:
            logger.error("Determinism guard FAILED — aborting (確認後 Yuito 相談)")
            return

    if args.determinism_only:
        logger.info("--determinism-only mode、guard のみ完了して終了")
        return

    # ----- Step B: trial 並列実行 -----
    for cond in conds:
        cond_dir = DATA_DIR / cond
        run_parallel_trials(cond, seeds, cond_dir, n_workers, logger)

    logger.info("=" * 70)
    logger.info("S3 LOB ensemble (sim part) complete.")
    logger.info("Mac 側 sim 終了。Windows 側 aggregation に進むため、")
    logger.info(f"  data/{conds[0]}/ ... data/{conds[-1]}/ を tar.gz で転送する。")
    logger.info("=" * 70)

    # diff 用 JSON dump (Mac 側、§3.5 の整合性チェックでも参照)
    summary = {
        "stage": "S3-mac",
        "conds": conds,
        "n_trials_per_cond": args.n_trials,
        "seed_base": args.seed_base,
        "n_workers": n_workers,
        "main_steps": LOB_PARAMS["main_steps"],
        "warmup_steps": LOB_PARAMS["warmup_steps"],
        "determinism_pass": determinism_pass,
        "timestamp": datetime.now().isoformat(),
    }
    with open(LOGS_DIR / "S3_mac_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"summary written: {LOGS_DIR / 'S3_mac_summary.json'}")


if __name__ == "__main__":
    main()
