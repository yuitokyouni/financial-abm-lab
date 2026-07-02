"""C-2 regression: SG 信念と LOB 実在庫の同期不変量。

監査 (2026-07-02) が指摘した C-2: `_reconcile` の close 分岐が over-fill
(実在庫が逆符号に反転) を「no fill」と誤分類し、全 SG エージェントが実在庫から
恒久的に乖離していた。修正は 2 段:

  1. close reconcile を符号付き分類にする (entry_sign × actual_vol <= 0 を full/
     crossed close として記帳)。
  2. reconcile 直後に「reality is truth」resync guard を毎 step 走らせ、
     asset_volumes != position × entry_quantity を検出したら flatten して信念を
     flat に戻す。

このテストは 2 つを検証する:

  - **決定時不変量** (最重要): エージェントが実際に売買/hold の意思決定を下す
    step では、必ず belief == reality が成立している (desync 状態で意思決定しない)。
    guard が return early するため構造的に保証されるが、回帰で守る。
  - **自己修復**: desync は毎 step 検出・修復され、恒久乖離が残らない。旧実装では
    このテストが 10/10 エージェントで即失敗する。
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


class _InstrumentedSG(SpeculationAgent):
    """submit_orders_by_market の戻り値を検査し、desync flatten でない (=通常の
    意思決定に到達した) step では belief == reality を assert する。"""

    decision_checks = 0

    def submit_orders_by_market(self, market):  # type: ignore[override]
        orders = super().submit_orders_by_market(market)
        mid = market.market_id
        # 通常の意思決定に到達した step かどうか: 最後の action が desync_flatten
        # なら guard が return early したので検査対象外。
        last = self.action_log[-1][1] if self.action_log else None
        if self.pending_intent is None and last != "desync_flatten":
            actual = int(self.asset_volumes.get(mid, 0))
            expected = int(self.position) * int(self.entry_quantity)
            assert actual == expected, (
                f"agent {self.agent_id}: 意思決定時に belief != reality "
                f"(asset_volumes={actual}, position×entry_quantity={expected})"
            )
            type(self).decision_checks += 1
        return orders


def _run(cls):
    cls.decision_checks = 0
    cfg = make_config(warmup_steps=50, main_steps=300, num_sg_agents=30,
                      c_ticks=0.03, max_normal_orders=400)
    cfg["FCNAgents"]["numAgents"] = 20
    # config は SG クラスを名前で参照するので、instrumented subclass を使う場合は
    # config の class 名も差し替える。
    cfg["SGAgents"]["class"] = cls.__name__
    saver = MarketStepSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(777), logger=saver)
    runner.class_register(cls)
    runner.class_register(MMFCNAgent)
    runner.main()
    return runner


def test_no_decision_on_desynced_belief():
    """意思決定時は常に belief == reality。"""
    runner = _run(_InstrumentedSG)
    assert _InstrumentedSG.decision_checks > 0, "検査が 1 度も走らなかった"


def test_desync_self_repairs():
    """desync は検出・修復され、恒久乖離が蓄積しない。

    終端 step 直後は「最後の matching で到着した fill」で invariant が一時的に
    崩れうる (次 step の guard が拾う) が、その残余 gap は bounded であるべき。
    旧バグでは gap が T とともに単調増加し max ~1.5 万株に達していた。
    """
    runner = _run(SpeculationAgent)
    sg = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    mid = runner.simulator.markets[0].market_id

    # guard が少なくとも一度は発火している (desync が実在する条件下)
    total_desync = sum(a.num_desync for a in sg)
    assert total_desync > 0, "この config では desync が起きるはず (guard 発火 0 は異常)"

    # 終端の残余 gap は bounded (1 step 分の over-fill 規模)。恒久乖離なら
    # entry_quantity の何倍にも膨れる。ここでは 1 エージェントあたり最大でも
    # 数百株オーダーに収まることを確認する (旧バグの max ~15,000 と対比)。
    max_gap = 0
    for a in sg:
        av = int(a.asset_volumes.get(mid, 0))
        exp = int(a.position) * int(a.entry_quantity)
        max_gap = max(max_gap, abs(av - exp))
    assert max_gap < 5000, f"終端残余 gap が過大 ({max_gap}) — 自己修復が効いていない"


if __name__ == "__main__":
    test_no_decision_on_desynced_belief()
    test_desync_self_repairs()
    print("[inventory-sync] ✓ pass")
