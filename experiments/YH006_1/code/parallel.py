"""trial 単位の multiprocessing wrapper.

Brief §3 S2 並列化注意: trial 単位、N_core 自動検出 + `--n-workers` で上書き可。
S2 plan v2 worker 数 default = `min(os.cpu_count(), 8)` (Yuito 承認 #2)。
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def default_n_workers() -> int:
    cpu = os.cpu_count() or 1
    return min(cpu, 8)


def _worker_run_trial(
    args: Tuple[str, int, str, Optional[int], Optional[int], Optional[int]],
) -> Tuple[str, int, float, int, int, Optional[str]]:
    """Worker 関数 — 1 trial 実行 + parquet 出力 + 結果サマリ返り。

    args: (cond_name, seed, out_dir_str, q_const_or_None,
           mmfcn_order_volume_or_None, main_steps_or_None)
    return: (cond, seed, runtime_sec, n_rt, n_sub, error_str_or_None)
    """
    cond, seed, out_str, q_const, mmfcn_ov, main_steps = args
    try:
        # Workerプロセス内 import (top-level import は heavy & forks 不要)
        from run_experiment import run_one_trial
        out_dir = Path(out_str)
        result = run_one_trial(
            cond, seed, out_dir=out_dir, is_lob_smoke=False,
            q_const=q_const, mmfcn_order_volume=mmfcn_ov,
            main_steps=main_steps,
        )
        return (cond, seed, result.runtime_sec, result.n_round_trips,
                result.n_substitutions, None)
    except Exception as e:
        import traceback
        return (cond, seed, 0.0, 0, 0, traceback.format_exc())


def run_parallel_trials(
    cond: str,
    seeds: List[int],
    out_dir: Path,
    n_workers: Optional[int] = None,
    logger: Optional[logging.Logger] = None,
    q_const: Optional[int] = None,
    mmfcn_order_volume: Optional[int] = None,
    main_steps: Optional[int] = None,
) -> List[Tuple[int, float, int, int, Optional[str]]]:
    """seeds × cond を並列実行、(seed, runtime, n_rt, n_sub, err) のリストを返す。

    S4-S5 (A1 ablation): q_const を渡すと QConstSpeculationAgent 経路へ。
    S5.6 (MMFCN sensitivity): mmfcn_order_volume を渡すと cfg override 経路へ。
    S5.8 (equilibration check): main_steps を渡すと LOB run 長 override 経路へ。
    いずれも None 経路は既存挙動と bit-一致。
    """
    if n_workers is None:
        n_workers = default_n_workers()
    if logger is None:
        logger = logging.getLogger("parallel")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    args = [(cond, seed, str(out_dir), q_const, mmfcn_order_volume, main_steps)
            for seed in seeds]
    logger.info(
        f"[parallel] cond={cond} n_seeds={len(seeds)} n_workers={n_workers} out={out_dir}"
    )

    results: List[Tuple[int, float, int, int, Optional[str]]] = []
    t_start = time.perf_counter()
    with mp.Pool(processes=n_workers) as pool:
        for i, (c, s, rt_sec, n_rt, n_sub, err) in enumerate(
            pool.imap_unordered(_worker_run_trial, args), 1
        ):
            results.append((s, rt_sec, n_rt, n_sub, err))
            if err:
                logger.error(f"[parallel] {c} seed={s}: ERROR\n{err}")
            else:
                logger.info(
                    f"[parallel] {c} seed={s} done ({i}/{len(seeds)}): "
                    f"runtime={rt_sec:.1f}s n_rt={n_rt:,} n_sub={n_sub}"
                )
    elapsed = time.perf_counter() - t_start
    logger.info(
        f"[parallel] cond={cond} all done: total={elapsed:.1f}s, "
        f"throughput={len(seeds) / max(elapsed, 1e-9):.2f} trial/s"
    )
    return sorted(results, key=lambda r: r[0])
