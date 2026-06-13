"""C_ticks 較正: C1 (FCN only) を走らせて median(|Δmid|)×3 を出力。

SPEC.md §3.2(e) の手順そのまま。結果は outputs/C_ticks_calibration.json に保存し、
C2/C3 の config 生成時に読み込む。
"""

from __future__ import annotations

import json
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

from pams.logs.market_step_loggers import MarketStepSaver  # noqa: E402
from pams.runners import SequentialRunner  # noqa: E402

from configs.c1 import make_config  # noqa: E402

DEFAULT_SEED = 777


def calibrate(
    warmup_steps: int = 200,
    main_steps: int = 1500,
    num_fcn: int = 30,
    max_normal_orders: int = 500,
    seed: int = DEFAULT_SEED,
    out_path: str | None = None,
) -> dict:
    cfg = make_config(warmup_steps=warmup_steps, main_steps=main_steps,
                      max_normal_orders=max_normal_orders)
    cfg["FCNAgents"]["numAgents"] = num_fcn

    saver = MarketStepSaver()
    runner = SequentialRunner(
        settings=cfg,
        prng=random.Random(seed),
        logger=saver,
    )
    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    prices = [
        log["market_price"]
        for log in sorted(saver.market_step_logs, key=lambda x: x["market_time"])
        if log["market_time"] >= warmup_steps
    ]
    arr = np.asarray(prices, dtype=np.float64)
    diffs = np.diff(arr)
    abs_diffs = np.abs(diffs)
    abs_diffs_nz = abs_diffs[abs_diffs > 0]  # zero diffs (no trade step) は除外

    median_abs = float(np.median(abs_diffs)) if abs_diffs.size > 0 else 0.0
    median_abs_nz = float(np.median(abs_diffs_nz)) if abs_diffs_nz.size > 0 else 0.0
    c_ticks = 3.0 * (median_abs_nz if median_abs_nz > 0 else max(median_abs, 1e-6))

    result = {
        "config": {
            "warmup_steps": warmup_steps,
            "main_steps": main_steps,
            "num_fcn": num_fcn,
            "max_normal_orders": max_normal_orders,
            "seed": seed,
        },
        "runtime_sec": elapsed,
        "num_price_samples": int(arr.size),
        "num_diffs": int(diffs.size),
        "num_diffs_nonzero": int(abs_diffs_nz.size),
        "median_abs_dmid": median_abs,
        "median_abs_dmid_nonzero": median_abs_nz,
        "mean_abs_dmid": float(abs_diffs.mean()) if abs_diffs.size > 0 else 0.0,
        "c_ticks": c_ticks,
        "price_min": float(arr.min()) if arr.size else 0.0,
        "price_max": float(arr.max()) if arr.size else 0.0,
        "price_mean": float(arr.mean()) if arr.size else 0.0,
    }

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
    return result


def main() -> None:
    out = HERE / "outputs" / "C_ticks_calibration.json"
    result = calibrate(out_path=str(out))
    print(f"[calibrate] elapsed={result['runtime_sec']:.1f}s")
    print(f"[calibrate] T={result['num_price_samples']}  "
          f"price mean={result['price_mean']:.4f}  "
          f"[{result['price_min']:.4f}, {result['price_max']:.4f}]")
    print(f"[calibrate] |Δmid|: median={result['median_abs_dmid']:.6f}  "
          f"nonzero-median={result['median_abs_dmid_nonzero']:.6f}  "
          f"mean={result['mean_abs_dmid']:.6f}")
    print(f"[calibrate] c_ticks = 3 × {result['median_abs_dmid_nonzero']:.6f} = "
          f"{result['c_ticks']:.6f}")
    print(f"[calibrate] saved: {out}")


if __name__ == "__main__":
    main()
