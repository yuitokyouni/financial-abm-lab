"""Parity: 同一 seed で 2 回走らせて結果が一致することを確認.

C3 を mini (num_sg=10, iterationSteps=80) で 2 回実行、以下を比較:
- mid-price 時系列
- round-trips 全フィールド

PAMS は random.Random を使うため、bit-一致までは固定 Python 実装で担保される。
"""

from __future__ import annotations

import random
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402

from pams.logs.market_step_loggers import MarketStepSaver  # noqa: E402
from pams.runners import SequentialRunner  # noqa: E402

from configs.c3 import make_config  # noqa: E402
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402
from yh006_to_yh005_adapter import build_yh005_compatible_dict  # noqa: E402


def _run_once(seed: int) -> dict:
    cfg = make_config(
        warmup_steps=20, main_steps=80,
        num_sg_agents=10, c_ticks=0.03, max_normal_orders=200,
    )
    cfg["FCNAgents"]["numAgents"] = 15
    saver = MarketStepSaver()
    runner = SequentialRunner(
        settings=cfg, prng=random.Random(seed), logger=saver,
    )
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)
    runner.main()
    return build_yh005_compatible_dict(
        runner=runner, saver=saver, warmup_steps=20, main_steps=80,
    )


def test_parity_seed_777():
    a = _run_once(777)
    b = _run_once(777)
    assert np.array_equal(a["prices"], b["prices"]), "prices diverge"
    for k in ("open_t", "close_t", "entry_action", "entry_quantity", "delta_G", "agent_idx"):
        assert np.array_equal(a["round_trips"][k], b["round_trips"][k]), \
            f"round_trips[{k!r}] diverge"


def test_different_seeds_diverge():
    a = _run_once(777)
    b = _run_once(42)
    # 異なる seed なら price 系列は (殆ど) 一致しない
    assert not np.array_equal(a["prices"], b["prices"]), \
        "seeds 777 vs 42 produced identical prices — RNG plumbing suspect"


if __name__ == "__main__":
    test_parity_seed_777()
    test_different_seeds_diverge()
    print("[parity] ✓ both tests pass")
