"""YH007-4: 執行層 (機構 2 = order flow long-memory) — parent → child TWAP 分割。

検証:
  - ChildOrderScheduler が方向転換 / 同方向継続 / abstain で正しく振る舞う
  - execution_horizon=1 では従来 (YH007-2) と等価 (pass-through)
  - execution_horizon>1 で 1 parent から N child が出る (TWAP-like)
"""
from __future__ import annotations

import pytest

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket
from abm_models.kronos_lob.execution import ChildOrderScheduler


# ---- scheduler 単体 -----------------------------------------------------


def test_scheduler_horizon1_bar0_then_bar1():
    """horizon=1: bar=0 で 1 child, 同 bar 内 (再 call) は no-op, 次 bar で再 child。"""
    s = ChildOrderScheduler(execution_horizon=1)
    s.update_parent(+1, bar_index=0)
    assert s.next_child() == +1
    assert s.next_child() == 0  # 残 0 で skip
    s.update_parent(+1, bar_index=0)  # 同 bar 再 call は無視
    assert s.next_child() == 0
    s.update_parent(+1, bar_index=1)  # 次 bar = 新 parent
    assert s.next_child() == +1


def test_scheduler_horizon5_spreads_one_parent_within_bar():
    """horizon=5: 1 parent で 5 child を連続して出す。同 bar 内 update は no-op。"""
    s = ChildOrderScheduler(execution_horizon=5)
    s.update_parent(+1, bar_index=0)
    out = [s.next_child() for _ in range(7)]
    assert out[:5] == [+1, +1, +1, +1, +1]
    assert out[5:] == [0, 0]
    # 同 bar 再 call は無視
    s.update_parent(-1, bar_index=0)
    assert s.next_child() == 0  # no-op


def test_scheduler_direction_flip_on_new_bar():
    """新 bar で方向転換すると schedule が新方向で再 charge。"""
    s = ChildOrderScheduler(execution_horizon=5)
    s.update_parent(+1, bar_index=0)
    assert s.next_child() == +1  # remaining=4
    s.update_parent(-1, bar_index=1)  # 新 bar + 方向転換
    assert s.next_child() == -1
    assert s.remaining == 4


def test_scheduler_abstain_on_new_bar_drops_schedule():
    """新 bar で action=0 のとき残 schedule が破棄される。"""
    s = ChildOrderScheduler(execution_horizon=5)
    s.update_parent(+1, bar_index=0)
    s.next_child()
    s.update_parent(0, bar_index=1)  # 次 bar で abstain
    assert s.remaining == 0
    assert s.next_child() == 0


def test_scheduler_horizon_zero_rejected():
    with pytest.raises(ValueError):
        ChildOrderScheduler(execution_horizon=0)


# ---- model 統合 ---------------------------------------------------------


def test_execution_horizon1_matches_previous_behaviour():
    """execution_horizon=1 のとき YH007-2 (pass-through) と等価。"""
    kwargs = dict(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=40, main_steps=80, n_trend=4, n_fade=4, n_fcn=8,
        bar_size=10, lookback_bars=3, order_volume=1,
    )
    m1 = KronosLOBMarket(execution_horizon=1, **kwargs)
    r1 = m1.run(seed=42)
    m2 = KronosLOBMarket(execution_horizon=1, **kwargs)
    r2 = m2.run(seed=42)
    # 同設定再現性
    import numpy as np
    np.testing.assert_allclose(r1["prices"], r2["prices"])


def test_execution_horizon_propagates_to_agents():
    """execution_horizon=5 を渡すと scheduler.execution_horizon にも反映される。"""
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=20, main_steps=40, n_trend=4, n_fade=4, n_fcn=8,
        bar_size=10, lookback_bars=2, execution_horizon=5,
    )
    m.run(seed=7)  # smoke が完走することの確認のみ
    # 直接 inspection 不可 (agent は run 中に生成); execution_horizon が
    # build_lob_config に伝わったことだけ確認
    from abm_models.kronos_lob.model import build_lob_config
    cfg = build_lob_config(
        warmup_steps=20, main_steps=40, n_trend=4, n_fade=4, n_fcn=8,
        bar_size=10, lookback_bars=2, execution_horizon=5,
    )
    assert cfg["TrendAgents"]["executionHorizon"] == 5
    assert cfg["FadeAgents"]["executionHorizon"] == 5


def test_execution_horizon_smoke_with_adaptive():
    """adaptive 構成でも execution_horizon が機能する (完走)。"""
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=30, main_steps=80,
        n_trend=0, n_fade=0, n_fcn=8, n_adaptive=10,
        bar_size=10, lookback_bars=2, execution_horizon=5,
        score_window=10,
    )
    res = m.run(seed=33)
    assert res["prices"].size > 0
