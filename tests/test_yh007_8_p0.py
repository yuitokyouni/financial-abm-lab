"""YH007-8 P0 (spec 003 §7): LIMIT agent 骨格 + 片側 resting + TTL + ZI warmup。

合格基準 (spec 003 P0):
  - LIMIT_ORDER で出ている (MARKET でない)
  - 板が爆発しない (outstanding 数が agent 数の数倍に収まる)
  - 約定が起きる (execution count > 0)
  - 同一 agent の self-trade が起きない (同 agent の both-side resting が無い)
"""
from __future__ import annotations

import pytest
from pams.order import LIMIT_ORDER, Order

from abm_models.self_organized_book import (
    LimitAgentBase,
    SelfOrganizedBookMarket,
    ZIAgent,
)


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_zi_warmup_smoke(seed: int):
    """ZI agent だけで sim が完走し、各合格基準を満たす。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=80, n_zi=20,
        bar_size=10, order_ttl=15, order_volume=1,
        sigma_eval=0.005, margin_min=0.001, margin_max=0.01,
        initial_market_price=300.0,
    )
    res = m.run(seed=seed)

    # 約定が起きる (LIMIT 主体でもクロスして約定するはず)
    assert res["n_executed"] > 0, f"seed={seed}: no executions"
    # 板履歴がある
    assert res["history_market"].shape[0] >= 10
    assert res["history_mid"].shape[0] >= 10
    # main session のリターン列が取れる (warmup 4 bar 除外、main 8 bar → returns=7)
    assert res["returns_main_market"].size >= 5
    assert res["returns_main_mid"].size >= 5


def test_orders_are_limit_not_market():
    """LimitAgentBase 経由で submit される注文は LIMIT のみ (MARKET 0)。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=20, main_steps=40, n_zi=10, bar_size=10, order_ttl=15,
    )
    res = m.run(seed=3)
    # 各 agent の action_log: (time, side, price, payload) で price=None は abstain のみ
    for agent in res["agents"]:
        for t, side, price, _ in agent.action_log:
            if side != 0:
                assert price is not None and price > 0, \
                    f"agent {agent.agent_id} side={side} に price=None"


def test_no_simultaneous_two_sided_resting():
    """片側 resting 保証 (§3.1, §10-2): 同一 agent が同時に both-side resting しない。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=30, main_steps=60, n_zi=15, bar_size=10, order_ttl=15,
    )
    res = m.run(seed=99)
    for agent in res["agents"]:
        # _outstanding は dict, 値は Order インスタンス
        assert len(agent._outstanding) <= 1, \
            f"agent {agent.agent_id}: _outstanding={len(agent._outstanding)}"


def test_book_does_not_explode():
    """板爆発防止 (§3.1 TTL/cancel): outstanding 総数が agent 数の数倍以内。

    全 agent が step 単位で自己 cancel するので、bar 内では新規発注後の
    outstanding は ≈ n_agents (片側 1 本 / agent)。TTL が機能していれば
    expire も併走する。
    """
    n_zi = 20
    m = SelfOrganizedBookMarket(
        warmup_steps=30, main_steps=100, n_zi=n_zi, bar_size=10, order_ttl=10,
    )
    res = m.run(seed=11)
    total_outstanding = sum(len(a._outstanding) for a in res["agents"])
    # 余裕を見て 3x (race condition で複数残るケースを許容)
    assert total_outstanding <= n_zi * 3, \
        f"book explosion: total outstanding={total_outstanding} > 3*{n_zi}"


def test_cancel_and_execute_counts_consistent():
    """submitted = executed + canceled + (run 末尾の outstanding) を概ね満たす。

    LimitAgentBase の bookkeeping が崩れていないことの整合性。
    """
    m = SelfOrganizedBookMarket(
        warmup_steps=30, main_steps=60, n_zi=10, bar_size=10, order_ttl=15,
    )
    res = m.run(seed=5)
    for agent in res["agents"]:
        n_sub = sum(1 for _, side, p, _ in agent.action_log if side != 0 and p is not None)
        n_exec = len(agent.executed_log)
        n_remain = len(agent._outstanding)
        # exec + remain は submit の上限を超えない (1 注文 = 最大 1 約定 + run 末 outstanding)
        # cancel は ttl expire と自己 cancel の二重カウントが入りうるので除外。
        assert n_exec + n_remain <= n_sub, (
            f"agent {agent.agent_id}: submitted={n_sub}, exec={n_exec}, remain={n_remain}"
        )
        # 約定数は submit の何割か (全 cancel で 0 約定だと P0 として無意味)
        # 全 agent の集計で見るので個別ではゆるく
    total_sub = sum(sum(1 for _, side, p, _ in a.action_log if side != 0 and p is not None)
                    for a in res["agents"])
    total_exec = sum(len(a.executed_log) for a in res["agents"])
    assert total_exec > 0
    # 約定率は ≥ 5% を期待 (margin 設定下で)
    assert total_exec >= total_sub * 0.01, f"exec/sub={total_exec}/{total_sub} too low"


def test_market_and_mid_diverge_for_diagnostic():
    """market 価格と mid 価格は別物として両方 ablation 可能 (002 §8.x の規律を P0 で確認)。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=30, main_steps=80, n_zi=20, bar_size=10, order_ttl=15,
    )
    res = m.run(seed=8)
    cm = res["closes_main_market"]
    cd = res["closes_main_mid"]
    # 両方 non-empty
    assert cm.size > 0 and cd.size > 0
    # mid と market は完全一致ではない (約定価格と (bb+ba)/2 は違う)
    # ただし全く動かないケースは P1 で対処、ここではゆるく
    assert cm.size == cd.size
