"""C2 (uniform wealth SG) standalone diagnostic."""
from __future__ import annotations

import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pams.runners import SequentialRunner
from configs.c2 import make_config
from custom_saver import OrderTrackingSaver
from mm_fcn_agent import MMFCNAgent
from speculation_agent import SpeculationAgent


def main():
    print("[c2] building config", flush=True)
    cfg = make_config(warmup_steps=100, main_steps=600,
                      num_sg_agents=100, c_ticks=28.0,
                      max_normal_orders=2000)
    cfg["FCNAgents"]["numAgents"] = 30

    saver = OrderTrackingSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)

    print("[c2] runner.main() starting", flush=True)
    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0
    print(f"[c2] elapsed = {elapsed:.1f}s", flush=True)

    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    print(f"[c2] num SG = {len(sgs)}")
    subs = sum(a.num_substitutions for a in sgs)
    rts = sum(len(a.round_trips) for a in sgs)
    print(f"[c2] total_subs = {subs}")
    print(f"[c2] total_round_trips = {rts}")


if __name__ == "__main__":
    main()
