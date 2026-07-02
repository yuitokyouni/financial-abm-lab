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
        # #37: delta_G = entry_action × (P[close_t] − P[open_t]) は cognitive_prices
        # から厳密に再構成できる (複数 seed で実測 mismatch = 0.0000%)。旧許容 50%
        # では 49% が壊れても通り回帰ガードとして無意味だったため、厳密一致を要求する。
        # 万一 main session 境界の再縫合で off-by-one が生じるなら、その最初の 1 件で
        # 落ちて設計上の仮定を再検討できる。
        assert mismatch == 0, (
            f"delta_G mismatch: {mismatch}/{len(dG_expected)} round-trips で "
            f"entry_action×ΔP と保存 delta_G が不一致 (厳密一致を期待)"
        )


if __name__ == "__main__":
    test_roundtrip_invariants()
    print("[roundtrip-invariants] ✓ pass")
