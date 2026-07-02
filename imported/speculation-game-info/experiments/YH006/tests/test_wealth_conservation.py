"""Wealth 保存: SG の cognitive wealth (sg_wealth) が round-trip 台帳と厳密に
一致する不変量。

厳密な保存則: substitute の無いエージェントでは
    sg_wealth_final == sg_wealth_init + Σ (ΔG × entry_quantity)
が **厳密に** 成立する。sg_wealth は full-close 分岐でのみ更新され (`sg_wealth +=
dG × entry_quantity`)、その同じ dG / entry_quantity が round_trips に append される
ため、両者は構造的に一致する。substitute が起きると B..B+100 の charity cash に
reset されるので、その agent は保存則の対象外 (num_substitutions == 0 のみ検査)。

旧テストは `sum_dG_q` が数値型かを確認するだけのトートロジーで、保存則そのものを
検証していなかった (#35)。ここでは初期 sg_wealth を捕捉し厳密一致を assert する。

LOB の cash_amount はマーケットメーカーや value agent との相互作用で SG 群内部で
保存しないため、この test では触らない。
"""

from __future__ import annotations

import random
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from pams.logs.market_step_loggers import MarketStepSaver  # noqa: E402
from pams.runners import SequentialRunner  # noqa: E402

from configs.c3 import make_config  # noqa: E402
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402


class _WealthTrackingSG(SpeculationAgent):
    """setup 直後の初期 sg_wealth を捕捉するだけの subclass。"""

    def setup(self, *args, **kwargs):  # type: ignore[override]
        super().setup(*args, **kwargs)
        self._initial_sg_wealth = int(self.sg_wealth)


def test_sg_wealth_conservation():
    cfg = make_config(warmup_steps=20, main_steps=80, num_sg_agents=10,
                      c_ticks=0.03, max_normal_orders=200)
    cfg["FCNAgents"]["numAgents"] = 15
    cfg["SGAgents"]["class"] = _WealthTrackingSG.__name__
    saver = MarketStepSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(_WealthTrackingSG)
    runner.class_register(MMFCNAgent)
    runner.main()

    sg = [a for a in runner.simulator.agents if isinstance(a, _WealthTrackingSG)]
    if not sg:
        raise AssertionError("no SG agents — test cannot run")

    checked = 0
    for a in sg:
        # bankruptcy substitute が起きた agent は charity cash reset で保存則の
        # 対象外。純粋な round-trip 台帳のみで動いた agent を厳密検査する。
        if a.num_substitutions != 0:
            continue
        ledger = sum(int(rt["delta_G"]) * int(rt["entry_quantity"]) for rt in a.round_trips)
        expected = int(a._initial_sg_wealth) + ledger
        assert int(a.sg_wealth) == expected, (
            f"agent {a.agent_id}: wealth 保存則違反 — "
            f"sg_wealth={a.sg_wealth} != init({a._initial_sg_wealth}) + "
            f"ledger({ledger}) = {expected}"
        )
        checked += 1

    assert checked > 0, (
        "substitute の無い agent が 1 体も無く保存則を検査できなかった "
        "(config を調整して非破産 agent を確保すること)"
    )


if __name__ == "__main__":
    test_sg_wealth_conservation()
    print("[wealth-conservation] ✓ pass")
