"""C1 / C2 / C3 を seed=777 で順次実行し、adapter 経由で pickle 保存。

C_ticks は outputs/C_ticks_calibration.json から読む (先に calibrate_c_ticks.py 必須)。
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pams.runners import SequentialRunner  # noqa: E402

from configs.c1 import make_config as c1_config  # noqa: E402
from configs.c2 import make_config as c2_config  # noqa: E402
from configs.c3 import make_config as c3_config  # noqa: E402
from custom_saver import OrderTrackingSaver  # noqa: E402
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402
from yh006_to_yh005_adapter import build_yh005_compatible_dict  # noqa: E402


DEFAULT_SEED = 777


def run_condition(
    cond: str,
    c_ticks: float,
    seed: int = DEFAULT_SEED,
    warmup_steps: int = 200,
    main_steps: int = 1500,
    num_fcn: int = 30,
    num_sg: int = 100,
    max_normal_orders: int = 500,
) -> dict:
    """cond ∈ {"C1","C2","C3"} を実行して YH005 互換 dict を返す。"""
    if cond == "C1":
        cfg = c1_config(warmup_steps=warmup_steps, main_steps=main_steps,
                        max_normal_orders=max_normal_orders)
    elif cond == "C2":
        cfg = c2_config(warmup_steps=warmup_steps, main_steps=main_steps,
                        num_sg_agents=num_sg, c_ticks=c_ticks,
                        max_normal_orders=max_normal_orders)
    elif cond == "C3":
        cfg = c3_config(warmup_steps=warmup_steps, main_steps=main_steps,
                        num_sg_agents=num_sg, c_ticks=c_ticks,
                        max_normal_orders=max_normal_orders)
    else:
        raise ValueError(f"Unknown condition {cond}")
    cfg["FCNAgents"]["numAgents"] = num_fcn

    saver = OrderTrackingSaver()
    runner = SequentialRunner(
        settings=cfg,
        prng=random.Random(seed),
        logger=saver,
    )
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    result = build_yh005_compatible_dict(
        runner=runner,
        saver=saver,
        warmup_steps=warmup_steps,
        main_steps=main_steps,
    )
    result["_meta"]["runtime_sec"] = elapsed
    result["_meta"]["condition"] = cond
    result["_meta"]["seed"] = seed
    result["_meta"]["num_fcn"] = num_fcn
    result["_meta"]["num_sg"] = num_sg
    result["_meta"]["c_ticks"] = c_ticks
    result["_meta"]["main_steps"] = main_steps
    result["_meta"]["warmup_steps"] = warmup_steps
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--main", type=int, default=1500, dest="main_steps")
    parser.add_argument("--num-fcn", type=int, default=30)
    parser.add_argument("--num-sg", type=int, default=100)
    parser.add_argument("--max-normal-orders", type=int, default=500)
    parser.add_argument("--conditions", nargs="+", default=["C1", "C2", "C3"])
    args = parser.parse_args()

    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)

    calib_path = out_dir / "C_ticks_calibration.json"
    if calib_path.exists():
        with open(calib_path) as f:
            c_ticks = float(json.load(f)["c_ticks"])
    else:
        c_ticks = 0.03
        print(f"[run_experiment] warning: no calibration file, using c_ticks={c_ticks}")
    print(f"[run_experiment] c_ticks = {c_ticks:.6f}")

    for cond in args.conditions:
        print(f"\n[run_experiment] === {cond} ===")
        t0 = time.perf_counter()
        result = run_condition(
            cond=cond,
            c_ticks=c_ticks,
            seed=args.seed,
            warmup_steps=args.warmup,
            main_steps=args.main_steps,
            num_fcn=args.num_fcn,
            num_sg=args.num_sg,
            max_normal_orders=args.max_normal_orders,
        )
        total = time.perf_counter() - t0
        meta = result["_meta"]
        print(f"[run_experiment] {cond} done in {total:.1f}s  "
              f"(N_sg={meta['N_sg']}  T={meta['T']}  "
              f"num_round_trips={result['round_trips']['open_t'].size}  "
              f"num_subs={result['num_substitutions']}  "
              f"partial_close={meta['num_partial_closes']}  "
              f"zero_open={meta['num_zero_opens']})")

        pkl = out_dir / f"{cond}_result.pkl"
        with open(pkl, "wb") as f:
            pickle.dump(result, f)
        print(f"[run_experiment] saved: {pkl}")


if __name__ == "__main__":
    main()
