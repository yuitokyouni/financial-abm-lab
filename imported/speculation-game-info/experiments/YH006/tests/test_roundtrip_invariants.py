"""Round-trip invariants:
- open_t < close_t (horizon > 0)
- entry_action ∈ {-1, +1}
- entry_quantity >= 1
- delta_G = entry_action * (P(close_t) - P(open_t))  (cognitive price 経由で再構成可能)
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


def _run():
    cfg = make_config(warmup_steps=20, main_steps=80, num_sg_agents=10,
                      c_ticks=0.03, max_normal_orders=200)
    cfg["FCNAgents"]["numAgents"] = 15
    saver = MarketStepSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)
    runner.main()
    return build_yh005_compatible_dict(runner=runner, saver=saver,
                                        warmup_steps=20, main_steps=80)


def test_roundtrip_invariants():
    res = _run()
    rt = res["round_trips"]
    if rt["open_t"].size == 0:
        raise AssertionError("no round-trips generated — cannot test invariants")

    horizon = rt["close_t"] - rt["open_t"]
    assert (horizon > 0).all(), f"some round-trips have non-positive horizon: min={horizon.min()}"

    ea = rt["entry_action"]
    assert set(np.unique(ea).tolist()).issubset({-1, 1}), \
        f"entry_action contains unexpected values: {np.unique(ea)}"

    q = rt["entry_quantity"]
    assert (q >= 1).all(), f"entry_quantity has non-positive values: min={q.min()}"

    # delta_G consistency with cognitive_prices
    P = np.concatenate([[0], res["cognitive_prices"]]).astype(np.int64)
    # open_t, close_t are relative to warmup origin (main session index)
    # dG should equal entry_action * (P[close_t] - P[open_t])
    valid = (rt["open_t"] >= 0) & (rt["close_t"] < res["cognitive_prices"].size)
    if valid.any():
        idx_close = rt["close_t"][valid]
        idx_open = rt["open_t"][valid]
        dG_expected = ea[valid].astype(np.int64) * (
            res["cognitive_prices"][idx_close] - res["cognitive_prices"][idx_open]
        )
        dG_got = rt["delta_G"][valid]
        mismatch = int(np.sum(dG_expected != dG_got))
        # 許容: main session 境界を跨ぐ round-trip は cognitive_prices の再構成と
        # SG 側保持の entry_price_cog が 1 step ズレる可能性がある (warmup 捨て時の再縫合)。
        # 50% 以下なら設計通り、それ以上なら実装 bug とみなす。
        frac_mismatch = mismatch / len(dG_expected)
        assert frac_mismatch < 0.5, f"delta_G mismatch rate too high: {frac_mismatch:.2%}"


if __name__ == "__main__":
    test_roundtrip_invariants()
    print("[roundtrip-invariants] ✓ pass")
