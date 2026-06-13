"""Profile C2 small to find bottleneck."""
import cProfile, pstats, random, sys, warnings
from io import StringIO
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pams.runners import SequentialRunner
from configs.c2 import make_config
from custom_saver import OrderTrackingSaver
from mm_fcn_agent import MMFCNAgent
from speculation_agent import SpeculationAgent


def run():
    cfg = make_config(warmup_steps=50, main_steps=150, num_sg_agents=50, c_ticks=28.0, max_normal_orders=500)
    cfg["FCNAgents"]["numAgents"] = 15
    saver = OrderTrackingSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(SpeculationAgent); runner.class_register(MMFCNAgent)
    runner.main()


pr = cProfile.Profile(); pr.enable()
run()
pr.disable()
s = StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(15)
print(s.getvalue())
