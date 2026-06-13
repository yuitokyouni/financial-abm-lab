"""Smoke test: run a tiny C3 instance to verify SpeculationAgent wires into PAMS.

C3 (FCN + SG Pareto) を num_sg_agents=20, iterationSteps=200 で走らせる。
- runner.main() が例外なく終わる
- submit_orders が呼ばれている (agent の submit_log に record が残る)
- round-trip event が発生している (少なくとも 1 件、ゼロなら警告)
- market_step_logs が収集されている
"""

from __future__ import annotations

import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pams.logs.market_step_loggers import MarketStepSaver  # noqa: E402
from pams.runners import SequentialRunner  # noqa: E402

from configs.c3 import make_config  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402


def main() -> None:
    cfg = make_config(
        warmup_steps=20,
        main_steps=80,
        num_sg_agents=15,
        c_ticks=0.03,
        max_normal_orders=300,
    )
    # Cut FCN population for smoke speed
    cfg["FCNAgents"]["numAgents"] = 20

    saver = MarketStepSaver()
    runner = SequentialRunner(
        settings=cfg,
        prng=random.Random(777),
        logger=saver,
    )
    runner.class_register(SpeculationAgent)
    t0 = time.perf_counter()
    runner.main()
    print(f"[smoke] runner.main() elapsed={time.perf_counter() - t0:.2f}s", flush=True)

    print(f"\n[smoke] market_step_logs: {len(saver.market_step_logs)} entries")
    if saver.market_step_logs:
        first = saver.market_step_logs[0]
        last = saver.market_step_logs[-1]
        print(f"[smoke]   first: t={first['market_time']} p={first['market_price']:.4f}")
        print(f"[smoke]   last:  t={last['market_time']} p={last['market_price']:.4f}")

    sg_agents = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    print(f"[smoke] SG agents: {len(sg_agents)}")

    total_submits = sum(len(a.submit_log) for a in sg_agents)
    total_rts = sum(len(a.round_trips) for a in sg_agents)
    total_subs = sum(a.num_substitutions for a in sg_agents)
    total_partial_close = sum(a.num_partial_closes for a in sg_agents)
    total_zero_opens = sum(a.num_zero_opens for a in sg_agents)
    print(f"[smoke]   total submits:         {total_submits}")
    print(f"[smoke]   total round-trips:     {total_rts}")
    print(f"[smoke]   total substitutions:   {total_subs}")
    print(f"[smoke]   total partial closes:  {total_partial_close}")
    print(f"[smoke]   total zero-fill opens: {total_zero_opens}")

    # SG cognitive wealth (comparable to YH005 w)
    sg_ws = [a.sg_wealth for a in sg_agents]
    if sg_ws:
        import statistics
        print(f"[smoke]   sg_wealth: min={min(sg_ws)} median={statistics.median(sg_ws):.1f} max={max(sg_ws)}")

    # PAMS LOB mark-to-market (diagnostic)
    mtms = []
    for a in sg_agents:
        asset = 0
        for mid, v in a.asset_volumes.items():
            asset = v
            break
        last_p = saver.market_step_logs[-1]["market_price"] if saver.market_step_logs else 0.0
        mtms.append(float(a.cash_amount) + asset * last_p)
    if mtms:
        import statistics as _s
        print(f"[smoke]   lob_mtm:   min={min(mtms):.1f} median={_s.median(mtms):.1f} max={max(mtms):.1f}")

    # Shared history state
    if hasattr(runner.simulator, "_yh006_history"):
        for mid, hist in runner.simulator._yh006_history.items():
            print(f"[smoke]   hist[market={mid}]: last_t={hist.last_t} P={hist.P} "
                  f"mu={hist.mu} h_series_len={len(hist.h_series)}")

    assert total_submits > 0, "SG agents did not submit any orders"
    assert len(saver.market_step_logs) >= 100, "market step logger did not collect full history"
    assert total_rts >= 1, "no round-trips generated"
    print("\n[smoke] ✓ PASS")


if __name__ == "__main__":
    main()
