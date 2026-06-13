"""C2 with per-step timing to find where it hangs."""
import random, sys, time, warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pams.runners import SequentialRunner
from configs.c2 import make_config
from custom_saver import OrderTrackingSaver
from mm_fcn_agent import MMFCNAgent
from speculation_agent import SpeculationAgent


class TimedSaver(OrderTrackingSaver):
    def __init__(self):
        super().__init__()
        self.step_times = []
        self._last = None
    def process_market_step_end_log(self, log):
        super().process_market_step_end_log(log)
        now = time.perf_counter()
        if self._last is None:
            self._last = now
        else:
            dt = now - self._last
            self.step_times.append((log.market.get_time(), dt))
            if dt > 0.5 or log.market.get_time() % 50 == 0:
                print(f"[c2] t={log.market.get_time()}  dt={dt*1000:.1f}ms", flush=True)
            self._last = now


def main():
    cfg = make_config(warmup_steps=50, main_steps=300, num_sg_agents=100,
                      c_ticks=28.0, max_normal_orders=2000)
    cfg["FCNAgents"]["numAgents"] = 30
    saver = TimedSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(SpeculationAgent); runner.class_register(MMFCNAgent)

    print("[c2] starting...", flush=True)
    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0
    print(f"[c2] total = {elapsed:.1f}s")

    # show top 5 slowest steps
    st = sorted(saver.step_times, key=lambda x: -x[1])[:5]
    print("[c2] top 5 slow steps:")
    for t, dt in st:
        print(f"  t={t}  dt={dt:.3f}s")


if __name__ == "__main__":
    main()
