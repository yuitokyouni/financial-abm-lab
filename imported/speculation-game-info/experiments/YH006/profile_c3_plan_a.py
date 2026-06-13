"""Profile C3 (seed=777) under Plan A: MARKET_ORDER + self-cancel.

報告項目:
- 実行時間
- cProfile top 10 関数 (cumulative)
- remain_executable_orders の累積時間 (slow path 発火量)
"""

from __future__ import annotations

import cProfile
import pstats
import random
import sys
import warnings
from io import StringIO
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pams.logs.market_step_loggers import MarketStepSaver  # noqa: E402
from pams.runners import SequentialRunner  # noqa: E402

from configs.c3 import make_config  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402


def run():
    cfg = make_config(warmup_steps=200, main_steps=1500,
                      num_sg_agents=100, c_ticks=28.006,
                      max_normal_orders=500)
    cfg["FCNAgents"]["numAgents"] = 30
    saver = MarketStepSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(SpeculationAgent)
    runner.main()
    return runner, saver


if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    runner, saver = run()
    pr.disable()

    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(25)
    print(s.getvalue())

    # Summary from agent state
    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    total_submits = sum(a.close_submits for a in sgs)
    total_full = sum(a.close_full_matches for a in sgs)
    total_partial = sum(a.close_partial_matches for a in sgs)
    total_cancelled = sum(a.close_cancelled for a in sgs)
    total_cancels_sent = sum(a.num_cancels_sent for a in sgs)
    total_rts = sum(len(a.round_trips) for a in sgs)
    total_subs = sum(a.num_substitutions for a in sgs)
    total_zero_opens = sum(a.num_zero_opens for a in sgs)

    print("\n=== Plan A C3 close accounting ===")
    print(f"close_submits           = {total_submits}")
    print(f"close_full_matches      = {total_full}  ({total_full / max(total_submits,1) * 100:.1f}%)")
    print(f"close_partial_matches   = {total_partial}  ({total_partial / max(total_submits,1) * 100:.1f}%)")
    print(f"close_cancelled         = {total_cancelled}  ({total_cancelled / max(total_submits,1) * 100:.1f}%)")
    print(f"total round_trips       = {total_rts}")
    print(f"num_substitutions       = {total_subs}")
    print(f"num_cancels_sent        = {total_cancels_sent}")
    print(f"num_zero_opens          = {total_zero_opens}")

    # Horizon stats
    import numpy as np
    horizons = []
    for a in sgs:
        for rt in a.round_trips:
            h = rt["close_t"] - rt["open_t"]
            if h > 0:
                horizons.append(h)
    h = np.array(horizons)
    if h.size > 0:
        print("\n=== horizon stats (成功 round-trip のみ) ===")
        print(f"n      = {h.size}")
        print(f"median = {np.median(h):.1f}")
        print(f"mean   = {h.mean():.2f}")
        print(f"max    = {h.max()}")
        print(f"p90    = {np.percentile(h, 90):.1f}")

    # Wealth
    ws = np.array([a.sg_wealth for a in sgs])
    print(f"\nsg_wealth: min={ws.min()} median={np.median(ws):.0f} max={ws.max()}")
