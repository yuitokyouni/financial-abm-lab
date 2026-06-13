"""S5.6 — MMFCN orderVolume sensitivity scan (Mac sim 専用).

S5.6 plan v1 §3.3:
  - C3 setup (LOB Pareto) で MMFCN の orderVolume を 4 設定で scan
  - 各設定 seed=1000, 1001 の 2 trial、計 8 trial を multiprocessing で並列実行
  - 出力: data/mmfcn_sensitivity/{setting}_{seed}/{trial,agents,lifetimes,wealth_ts}.parquet

Phase 1 後方互換 hook (S4 §0.4 と同 protocol):
  - `mmfcn_order_volume=None` は既存挙動 bit-一致 (`mmfcn_1x` baseline は data/C3/ と一致を確認)
  - 非 None で cfg["FCNAgents"]["orderVolume"] を override

Run (Mac、PAMS 必要):
  cd experiments/YH006_1
  python -m code.mmfcn_sensitivity \\
      --mmfcn-order-volumes 15,30,60,120 --seeds 1000,1001 --n-workers 8
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

HERE = Path(__file__).resolve().parent
YH006_1 = HERE.parent
for _p in (str(YH006_1), str(HERE)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

import multiprocessing as mp  # noqa: E402

DATA_DIR = YH006_1 / "data"
LOGS_DIR = YH006_1 / "logs"
SWEEP_DIR = DATA_DIR / "mmfcn_sensitivity"


def setting_label(order_volume: int) -> str:
    """orderVolume の数値から human-readable な設定 label を生成.

    baseline (orderVolume=30) は "mmfcn_1x"、それ以外は ratio で命名。
    """
    ratio = order_volume / 30
    if ratio == 0.5:
        return "mmfcn_05x"
    if ratio == 1.0:
        return "mmfcn_1x"
    if ratio == 2.0:
        return "mmfcn_2x"
    if ratio == 4.0:
        return "mmfcn_4x"
    return f"mmfcn_ov{order_volume}"


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "runtime").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("S5.6")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOGS_DIR / "runtime" / f"{ts}_S5.6_mmfcn_sensitivity.log",
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def _worker_trial(
    args: Tuple[str, int, str, int, Optional[int]],
) -> Tuple[str, int, int, float, int, int, Optional[str]]:
    """args: (cond, seed, out_dir_str, order_volume, baseline_flag)
    return: (cond, seed, order_volume, runtime_sec, n_rt, n_sub, err)

    baseline_flag (None or 0/1) は将来拡張用、現状未使用。
    """
    cond, seed, out_str, order_vol, _flag = args
    try:
        from run_experiment import run_one_trial
        out_dir = Path(out_str)
        # mmfcn_1x (= orderVolume 30) は既存挙動と bit-一致を保つために None で呼ぶ
        mmfcn_ov = None if order_vol == 30 else order_vol
        result = run_one_trial(
            cond, seed, out_dir=out_dir,
            is_lob_smoke=False, q_const=None,
            mmfcn_order_volume=mmfcn_ov,
        )
        return (cond, seed, order_vol, result.runtime_sec,
                result.n_round_trips, result.n_substitutions, None)
    except Exception:
        import traceback
        return (cond, seed, order_vol, 0.0, 0, 0, traceback.format_exc())


def run_sweep(
    cond: str, order_volumes: List[int], seeds: List[int],
    n_workers: int, logger: logging.Logger,
) -> List[dict]:
    """4 設定 × 2 seed = 8 trial を multiprocessing で並列実行.

    各 (setting, seed) で `data/mmfcn_sensitivity/{setting}_{seed}/` に 4 parquet 出力。
    """
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)

    job_args: List[Tuple[str, int, str, int, Optional[int]]] = []
    for ov in order_volumes:
        label = setting_label(ov)
        for seed in seeds:
            out = SWEEP_DIR / f"{label}_{seed:04d}"
            out.mkdir(parents=True, exist_ok=True)
            job_args.append((cond, seed, str(out), ov, None))

    logger.info(
        f"[sweep] cond={cond} n_jobs={len(job_args)} n_workers={n_workers} "
        f"order_volumes={order_volumes} seeds={seeds}"
    )

    results: List[dict] = []
    t0 = time.perf_counter()
    with mp.Pool(processes=n_workers) as pool:
        for i, (c, s, ov, rt_sec, n_rt, n_sub, err) in enumerate(
            pool.imap_unordered(_worker_trial, job_args), 1
        ):
            label = setting_label(ov)
            if err:
                logger.error(f"[sweep] {label} seed={s}: ERROR\n{err}")
                results.append({
                    "setting": label, "order_volume": ov, "seed": s,
                    "runtime_sec": 0.0, "n_rt": 0, "n_sub": 0,
                    "error": err.splitlines()[-1] if err else None,
                })
            else:
                logger.info(
                    f"[sweep] {label} seed={s} done ({i}/{len(job_args)}): "
                    f"runtime={rt_sec:.1f}s n_rt={n_rt:,} n_sub={n_sub}"
                )
                results.append({
                    "setting": label, "order_volume": ov, "seed": s,
                    "runtime_sec": rt_sec, "n_rt": n_rt, "n_sub": n_sub,
                    "error": None,
                })
    elapsed = time.perf_counter() - t0
    logger.info(f"[sweep] all done: total={elapsed:.1f}s")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cond", default="C3",
                        help="LOB condition (default: C3 = LOB Pareto baseline)")
    parser.add_argument("--mmfcn-order-volumes", default="15,30,60,120",
                        help="comma-separated MMFCN orderVolume 値")
    parser.add_argument("--seeds", default="1000,1001",
                        help="comma-separated seeds")
    parser.add_argument("--n-workers", type=int, default=8)
    args = parser.parse_args()

    logger = setup_logger()

    order_volumes = [int(x) for x in args.mmfcn_order_volumes.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]

    logger.info("=" * 70)
    logger.info("S5.6 MMFCN sensitivity scan")
    logger.info("=" * 70)

    results = run_sweep(args.cond, order_volumes, seeds, args.n_workers, logger)

    summary = {
        "stage": "S5.6",
        "cond": args.cond,
        "order_volumes": order_volumes,
        "seeds": seeds,
        "n_jobs": len(results),
        "runs": results,
    }
    out_json = LOGS_DIR / "S5.6_mac_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"[output] saved: {out_json}")
    logger.info("=" * 70)
    logger.info("S5.6 sweep complete (Mac side).")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
