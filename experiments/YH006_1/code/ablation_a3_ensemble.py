"""S6 A3 ablation runner — C3_A3 × 100 trial (Mac 側専用).

S6 plan §3.4-§3.6:
  0. C3 等価チェック (fail-fast): hook 追加後の default 経路 (C3, lifetime_cap
     なし) を seed=1000 で 1 run、archived `data/C3/` と semantic 一致確認。
     aggregate parity (Windows 27 件) は LOB agent を通らないため、
     `_should_force_retire=False` 経路の LOB bit-一致はこのチェックが確定する
  1. A3 smoke: C3_A3 seed=1000 を 1 run、cap が効いていることを assertion
     (lifetime 上限 + substitution 数 + capped 退場の支配)
  2. determinism guard: C3_A3 seed=1000 × 2 独立 run、semantic 一致
  3. C3_A3 × seed 1000-1099 並列実行 → `data/C3_A3/` に 4 schema parquet

τ_max は `logs/S6_tau_max_calibration.json` から auto-load (= 121, p25 × 0.5)。

Run (Mac):
  cd experiments/YH006_1
  python -m code.ablation_a3_ensemble --determinism-only   # §0-§2 のみ
  python -m code.ablation_a3_ensemble                      # 100 trial
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

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

COND_A3 = "C3_A3"
BASELINE_COND = "C3"
# capped lifetime の許容 slack: warmup (初代の在籍は warmup 中から数える) +
# pending in-flight による 1-数 step 延期 + stale-flatten 1 step
LIFETIME_SLACK = LOB_PARAMS["warmup_steps"] + 50


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S6")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S6_a3_ensemble.log", encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def load_tau_max() -> int:
    p = LOGS_DIR / "S6_tau_max_calibration.json"
    with open(p, encoding="utf-8") as f:
        cal = json.load(f)
    return int(cal["tau_max"])


# ---------------------------------------------------------------------------
# §0 C3 等価チェック — hook default 経路の LOB bit-一致 (S5.8 と同 pattern)
# ---------------------------------------------------------------------------

def c3_equivalence_check(seed: int, logger: logging.Logger) -> bool:
    from run_experiment import run_lob_trial
    ref_dir = DATA_DIR / BASELINE_COND
    if not (ref_dir / f"trial_{seed:04d}.parquet").exists():
        logger.error(f"[c3-check] archived C3 data なし: {ref_dir}")
        return False

    logger.info(f"[c3-check] {BASELINE_COND} seed={seed} を hook 追加後 code で実行")
    out_dir = DATA_DIR / "_guard_a3_c3_equiv"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_lob_trial(BASELINE_COND, seed).to_parquets(out_dir)

    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_new = pd.read_parquet(out_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_ref = pd.read_parquet(ref_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_match = np.array_equal(rt_new, rt_ref)

    cols_lt = ["t_birth", "t_end", "censored"]
    lt_new = pd.read_parquet(out_dir / f"lifetimes_{seed:04d}.parquet")
    lt_ref = pd.read_parquet(ref_dir / f"lifetimes_{seed:04d}.parquet")
    lt_match = (
        sorted(map(tuple, lt_new[cols_lt].to_numpy().tolist()))
        == sorted(map(tuple, lt_ref[cols_lt].to_numpy().tolist()))
    )
    logger.info(
        f"[c3-check] rt_df: {'MATCH' if rt_match else 'MISMATCH'} | "
        f"lifetimes: {'MATCH' if lt_match else 'MISMATCH'}"
    )
    return rt_match and lt_match


# ---------------------------------------------------------------------------
# §1 A3 smoke — cap が効いていることの assertion (plan §3.4)
# ---------------------------------------------------------------------------

def a3_smoke(seed: int, tau_max: int, logger: logging.Logger):
    from run_experiment import run_lob_trial
    logger.info(f"[smoke] {COND_A3} seed={seed} tau_max={tau_max} を 1 run")
    res = run_lob_trial(COND_A3, seed, tau_max=tau_max)
    lt = res.lifetime_samples_df
    n_agents = len(res.agents_df)
    n_sub = res.n_substitutions

    # (1) agent 数 >= N_sg (force-retire で世代数が増えるのは lifetimes 側)
    assert n_agents >= LOB_PARAMS["N_sg"], \
        f"agents_df {n_agents} < N_sg {LOB_PARAMS['N_sg']}"
    # (2) lifetime 上限: cap + slack (warmup + in-flight 延期)
    life_max = int(lt["lifetime"].max())
    assert life_max <= tau_max + LIFETIME_SLACK, \
        f"lifetime max {life_max} > tau_max {tau_max} + slack {LIFETIME_SLACK} — cap が効いていない"
    # (3) substitution が C3 baseline (数件) から激増しているか
    #     期待 order: ~N_sg × main_steps / tau_max ≈ 100 × 1500 / 121 ≈ 1200
    assert n_sub >= 200, \
        f"n_substitutions {n_sub} < 200 — cap 退場が支配的でない (hook が動いていない疑い)"
    # (4) capped 退場 (lifetime ≈ tau_max 帯) が uncensored 退場の過半
    unc = lt[~lt["censored"].astype(bool)]
    capped = (unc["lifetime"] >= tau_max - 1).sum()
    frac = capped / max(len(unc), 1)
    assert frac >= 0.5, \
        f"capped 退場比率 {frac:.2f} < 0.5 — bankruptcy 退場が想定外に支配的"
    logger.info(
        f"[smoke] PASS: n_agents={n_agents} n_sub={n_sub} "
        f"lifetime_max={life_max} capped_frac={frac:.2f}"
    )
    return res


# ---------------------------------------------------------------------------
# §2 determinism guard — C3_A3 seed=1000 × 2 semantic 一致
# ---------------------------------------------------------------------------

def determinism_guard_a3(seed: int, tau_max: int, logger: logging.Logger) -> bool:
    from run_experiment import run_lob_trial
    a_dir = DATA_DIR / "_guard_a3_a"
    b_dir = DATA_DIR / "_guard_a3_b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[guard] {COND_A3} seed={seed} × 2 runs (tau_max={tau_max})")
    run_lob_trial(COND_A3, seed, tau_max=tau_max).to_parquets(a_dir)
    run_lob_trial(COND_A3, seed, tau_max=tau_max).to_parquets(b_dir)

    cols_rt = ["agent_id", "rt_idx", "t_open", "t_close", "horizon",
               "direction", "q", "delta_g"]
    rt_a = pd.read_parquet(a_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_b = pd.read_parquet(b_dir / f"trial_{seed:04d}.parquet")[cols_rt].to_numpy()
    rt_match = np.array_equal(rt_a, rt_b)
    lt_a = pd.read_parquet(a_dir / f"lifetimes_{seed:04d}.parquet")
    lt_b = pd.read_parquet(b_dir / f"lifetimes_{seed:04d}.parquet")
    lt_match = lt_a.equals(lt_b)
    logger.info(
        f"[guard] rt_df: {'MATCH' if rt_match else 'MISMATCH'} | "
        f"lifetimes: {'MATCH' if lt_match else 'MISMATCH'}"
    )
    return rt_match and lt_match


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-base", type=int, default=ENSEMBLE_SEED_BASE)
    parser.add_argument("--n-trials", type=int, default=ENSEMBLE_N_TRIALS)
    parser.add_argument("--n-workers", type=int, default=None)
    parser.add_argument("--tau-max", type=int, default=None,
                        help="default: logs/S6_tau_max_calibration.json から auto")
    parser.add_argument("--skip-c3-check", action="store_true")
    parser.add_argument("--skip-determinism", action="store_true")
    parser.add_argument("--determinism-only", action="store_true")
    args = parser.parse_args()

    logger = setup_logger()
    tau_max = args.tau_max if args.tau_max is not None else load_tau_max()
    n_workers = args.n_workers or default_n_workers()
    seeds: List[int] = list(range(args.seed_base, args.seed_base + args.n_trials))
    assert CONDITIONS[COND_A3].lifetime_cap, f"{COND_A3} is not A3 cond"

    logger.info("=" * 70)
    logger.info(
        f"S6 A3 ablation — cond={COND_A3}, tau_max={tau_max}, "
        f"n_trials={args.n_trials}, n_workers={n_workers}"
    )
    logger.info("=" * 70)

    # §0 C3 等価チェック (hook default 経路の LOB bit-一致、fail-fast)
    c3_pass = True
    if not args.skip_c3_check:
        c3_pass = c3_equivalence_check(args.seed_base, logger)
        if not c3_pass:
            logger.error(
                "[c3-check] FAILED — hook default 経路が既存挙動を破壊。"
                "100 trial を中止して Yuito 相談 (plan §5 stop trigger)"
            )
            return

    # §1 A3 smoke (assertion fail は例外で停止 = plan §5 stop trigger)
    a3_smoke(args.seed_base, tau_max, logger)

    # §2 determinism guard
    determinism_pass = True
    if not args.skip_determinism:
        determinism_pass = determinism_guard_a3(args.seed_base, tau_max, logger)
        if not determinism_pass:
            logger.error("[guard] FAILED — subclass 副作用疑い、Yuito 相談")
            return

    if args.determinism_only:
        logger.info("--determinism-only mode、§0-§2 完了して終了")
        return

    # §3 100 trial 並列実行
    cond_dir = DATA_DIR / COND_A3
    results = run_parallel_trials(
        COND_A3, seeds, cond_dir, n_workers, logger, tau_max=tau_max,
    )
    errs = [(s, err) for (s, rt, _, _, err) in results if err]
    if errs:
        logger.error(f"[main] {len(errs)} trial errored — 確認要")
    slow = [s for (s, rt, _, _, err) in results if err is None and rt > 6 * 3600]
    if slow:
        logger.error(f"[main] seeds {slow} が 6 時間/trial 超過 — stop trigger (plan §5)")

    summary = {
        "stage": "S6-mac",
        "cond": COND_A3,
        "tau_max": tau_max,
        "n_trials": args.n_trials,
        "seed_base": args.seed_base,
        "n_workers": n_workers,
        "c3_equivalence_pass": c3_pass,
        "determinism_pass": determinism_pass,
        "n_errors": len(errs),
        "runtimes_sec": {str(s): rt for (s, rt, _, _, err) in results if err is None},
        "timestamp": datetime.now().isoformat(),
    }
    with open(LOGS_DIR / "S6_mac_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"summary written: {LOGS_DIR / 'S6_mac_summary.json'}")

    logger.info("=" * 70)
    logger.info("S6 A3 ensemble (sim part) complete. git add data/ logs/ && commit && push")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
