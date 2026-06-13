"""C2 で step ごとに book / expire_list / agent state の size を計測し
何が O(T) で grow しているか特定。
"""
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


class ProbeSaver(OrderTrackingSaver):
    def __init__(self, runner_ref=None):
        super().__init__()
        self.t_last = None
        self.runner = runner_ref
    def process_market_step_end_log(self, log):
        super().process_market_step_end_log(log)
        t = log.market.get_time()
        now = time.perf_counter()
        dt = (now - self.t_last) if self.t_last else 0.0
        self.t_last = now
        if t in (10, 50, 100, 150, 200, 250, 280, 300, 320, 340):
            mk = log.market
            bq = len(mk.buy_order_book.priority_queue)
            sq = len(mk.sell_order_book.priority_queue)
            be = len(mk.buy_order_book.expire_time_list)
            se = len(mk.sell_order_book.expire_time_list)
            sum_expire_slots = sum(len(v) for v in mk.buy_order_book.expire_time_list.values())
            sum_expire_slots += sum(len(v) for v in mk.sell_order_book.expire_time_list.values())
            # agent states
            sg_total_rts = 0
            sg_total_actions = 0
            sg_total_submits = 0
            sg_total_sub_events = 0
            sg_total_outstanding = 0
            mm_total = 0
            for a in self.runner.simulator.agents:
                if isinstance(a, SpeculationAgent):
                    sg_total_rts += len(a.round_trips)
                    sg_total_actions += len(a.action_log)
                    sg_total_submits += len(a.submit_log)
                    sg_total_sub_events += len(a.substitute_events)
                    for lst in a._outstanding.values():
                        sg_total_outstanding += len(lst)
                else:
                    mm_total += 1
            hist = getattr(self.runner.simulator, "_yh006_history", {})
            h_series_len = 0
            for h in hist.values():
                h_series_len += len(h.h_series)
            print(f"[probe t={t:4d}] dt={dt*1000:8.1f}ms "
                  f"buy_q={bq:4d} sell_q={sq:4d} expireL(b/s)={be}/{se} slots={sum_expire_slots} "
                  f"rts={sg_total_rts:4d} acts={sg_total_actions} subs_ev={sg_total_sub_events} "
                  f"outstd={sg_total_outstanding} hseries={h_series_len}", flush=True)


def main():
    cfg = make_config(warmup_steps=50, main_steps=350, num_sg_agents=100,
                      c_ticks=28.0, max_normal_orders=2000)
    cfg["FCNAgents"]["numAgents"] = 30
    saver = ProbeSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    saver.runner = runner
    runner.class_register(SpeculationAgent); runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    print(f"\n[probe] total = {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
