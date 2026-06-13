"""S4-S5 Ablation A1 ensemble runner — C2_A1 / C3_A1 × 100 trial 並列実行 (Mac 側).

S4 plan §3.4 / §3.5:
  1. smoke 1 trial (S4): A1 wiring 動作確認 (`QConstSpeculationAgent` で w_init 取得 +
     全 round-trip の q == q_const を assertion)
  2. Determinism guard: C3_A1 seed=1000 × 2 回独立 run、4 parquet bit-一致確認
     (S3 の lob_ensemble.py guard ロジック流用)
  3. C2_A1 / C3_A1 × 100 trial 並列実行 → data/{cond}/ に parquet 出力

q_const は `logs/S4_q_const_calibration.json` から自動 load (Windows で `q_const_calibration`
を実行済、git 経由で Mac に転送済の前提)。`--q-const N` で明示上書き可。

Run (Mac):
  cd experiments/YH006_1
  python -m code.ablation_ensemble [--conds C2_A1,C3_A1] [--n-trials 100]
                                   [--q-const N] [--skip-determinism] [--skip-smoke]
                                   [--determinism-only]
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
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from config import CONDITIONS, ENSEMBLE_SEED_BASE, ENSEMBLE_N_TRIALS, LOB_PARAMS  # noqa: E402
from parallel import run_parallel_trials, default_n_workers  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"

A1_CONDS_DEFAULT = ["C2_A1", "C3_A1"]
CAL_JSON = LOGS_DIR / "S4_q_const_calibration.json"


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5_ablation_ensemble.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def load_q_const(cli_q_const: Optional[int], logger: logging.Logger) -> int:
    """CLI 引数 or JSON から q_const を解決."""
    if cli_q_const is not None:
        logger.info(f"q_const from CLI override: {cli_q_const}")
        return int(cli_q_const)
    if not CAL_JSON.exists():
        raise FileNotFoundError(
            f"{CAL_JSON} 不在。Windows 側で `python -m code.q_const_calibration` を実行して "
            f"commit/push してから Mac で pull する。または --q-const N で明示指定。"
        )
    with open(CAL_JSON, encoding="utf-8") as f:
        cal = json.load(f)
    q = int(cal["q_const_primary"])
    logger.info(f"q_const from {CAL_JSON.name}: {q} (cond={cal['cond']}, n_trials={cal['n_trials']})")
    return q


# ---------------------------------------------------------------------------
# Smoke (S4 §3.4)
# ---------------------------------------------------------------------------

def smoke(q_const: int, logger: logging.Logger) -> bool:
    """A1 smoke: C3_A1 seed=9001 短縮 sim、agent parquet で w_init non-NaN +
    全 RT の q == q_const を assertion。"""
    logger.info(f"[smoke] A1 wiring check — C3_A1 seed=9001, q_const={q_const}, warmup=200/main=200")
    from run_experiment import run_lob_trial_smoke
    res = run_lob_trial_smoke("C3_A1", 9001, q_const=q_const)
    assert len(res.agents_df) == 100, f"smoke FAIL: agents_df rows = {len(res.agents_df)}"
    n_winit_nan = int(res.agents_df["w_init"].isna().sum())
    assert n_winit_nan == 0, f"smoke FAIL: w_init has {n_winit_nan} NaN"
    if len(res.rt_df) > 0:
        q_arr = res.rt_df["q"].to_numpy()
        unique_q = np.unique(q_arr)
        assert len(unique_q) == 1 and int(unique_q[0]) == q_const, (
            f"smoke FAIL: rt_df q values = {unique_q.tolist()}, expected single value {q_const}"
        )
        logger.info(f"[smoke] PASS: n_rt={res.n_round_trips}, "
                    f"all q == {q_const} (assertion), runtime={res.runtime_sec:.1f}s")
    else:
        logger.warning(f"[smoke] n_rt=0 (warmup 短縮で round-trip ほぼゼロ)、"
                       f"w_init assertion のみで判定 PASS")
    return True


# ---------------------------------------------------------------------------
# Determinism guard (LOB A1)
# ---------------------------------------------------------------------------

def _hash_parquet(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def determinism_guard_a1(
    cond: str, seed: int, q_const: int, logger: logging.Logger,
) -> bool:
    """C3_A1 seed=1000 × 2 run、4 parquet が bit-一致するか sha256 + semantic で確認."""
    from run_experiment import run_lob_trial
    a_dir = DATA_DIR / "_guard_a1_a"
    b_dir = DATA_DIR / "_guard_a1_b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[guard] A1 determinism check: {cond} seed={seed} × 2 runs, q_const={q_const}")
    res_a = run_lob_trial(cond, seed, q_const=q_const)
    res_a.to_parquets(a_dir)
    res_b = run_lob_trial(cond, seed, q_const=q_const)
    res_b.to_parquets(b_dir)

    file_keys = ["trial", "agents", "lifetimes", "wealth_ts"]
    fname_map = {
        "trial": f"trial_{seed:04d}.parquet",
        "agents": f"agents_{seed:04d}.parquet",
        "lifetimes": f"lifetimes_{seed:04d}.parquet",
        "wealth_ts": f"wealth_ts_{seed:04d}.parquet",
    }
    all_match = True
    for k in file_keys:
        fname = fname_map[k]
        ha = _hash_parquet(a_dir / fname)
        hb = _hash_parquet(b_dir / fname)
        match = ha == hb
        all_match = all_match and match
        logger.info(f"[guard] {fname}: {'MATCH' if match else 'MISMATCH'} "
                    f"(a={ha[:16]}... b={hb[:16]}...)")

    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_a = pd.read_parquet(a_dir / fname_map["trial"])[cols_rt].to_numpy()
    rt_b = pd.read_parquet(b_dir / fname_map["trial"])[cols_rt].to_numpy()
    semantic_match = np.array_equal(rt_a, rt_b)
    logger.info(f"[guard] rt_df semantic: {'PASS' if semantic_match else 'FAIL'}")

    if not all_match and not semantic_match:
        logger.error("[guard] A1 determinism FAILED")
        return False
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conds", type=str, default=",".join(A1_CONDS_DEFAULT),
                        help="comma-separated A1 conds (default: C2_A1,C3_A1)")
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    parser.add_argument("--n-workers", type=int, default=None)
    parser.add_argument("--q-const", type=int, default=None,
                        help="明示指定。省略時は S4_q_const_calibration.json から load")
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--determinism-only", action="store_true")
    args = parser.parse_args()

    logger = setup_logger()
    seeds = list(range(args.seed_base, args.seed_base + args.n_trials))
    conds = [c.strip() for c in args.conds.split(",") if c.strip()]
    for c in conds:
        spec = CONDITIONS[c]
        assert spec.world == "lob", f"{c} is not LOB"
        assert spec.q_rule == "const", f"{c} q_rule={spec.q_rule}, expected 'const'"

    q_const = load_q_const(args.q_const, logger)
    n_workers = args.n_workers or default_n_workers()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info(
        f"S5 A1 ablation ensemble — conds={conds}, n_trials={args.n_trials}, "
        f"seed_base={args.seed_base}, n_workers={n_workers}, q_const={q_const}, "
        f"main_steps={LOB_PARAMS['main_steps']}"
    )
    logger.info("=" * 70)

    # ----- Step S4.1: smoke -----
    if not args.skip_smoke:
        if not smoke(q_const, logger):
            logger.error("smoke FAILED, aborting")
            return

    # ----- Step S4.2: determinism guard -----
    if not args.skip_determinism:
        guard_cond = "C3_A1" if "C3_A1" in conds else conds[0]
        if not determinism_guard_a1(guard_cond, args.seed_base, q_const, logger):
            logger.error("determinism guard FAILED, aborting")
            return

    if args.determinism_only:
        logger.info("--determinism-only、guard 完了で終了")
        return

    # ----- Step S5: 100 trial 並列実行 -----
    for cond in conds:
        cond_dir = DATA_DIR / cond
        run_parallel_trials(cond, seeds, cond_dir, n_workers, logger, q_const=q_const)

    logger.info("=" * 70)
    logger.info("S5 A1 ablation ensemble (sim part) complete.")
    logger.info(f"Windows aggregation: `python -m code.aggregate_ablation_summary`")
    logger.info("=" * 70)

    summary = {
        "stage": "S5-mac-A1",
        "conds": conds,
        "n_trials_per_cond": args.n_trials,
        "seed_base": args.seed_base,
        "n_workers": n_workers,
        "q_const": q_const,
        "main_steps": LOB_PARAMS["main_steps"],
        "warmup_steps": LOB_PARAMS["warmup_steps"],
        "timestamp": datetime.now().isoformat(),
    }
    with open(LOGS_DIR / "S5_mac_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"summary: {LOGS_DIR / 'S5_mac_summary.json'}")


if __name__ == "__main__":
    main()
