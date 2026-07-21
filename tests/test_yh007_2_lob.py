"""YH007-2: PAMS CDA LOB + MMFCN + Kronos shared-signal × 2-reading の疎通テスト。

mock signal で end-to-end が回り、価格列・bar 履歴・action log が取れることを示す。
SF baseline は smoke 内で参考値として算出 (受け入れ基準は緩め)。
"""
from __future__ import annotations

import numpy as np
import pytest

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket, build_ohlcv_from_market


@pytest.mark.parametrize("seed", [7, 42])
def test_lob_smoke_with_mock_signal(seed: int):
    """mock signal で smoke が完走し、prices / actions が取れる。"""
    market = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.6, pred_close_std=1.0),
        warmup_steps=80, main_steps=200,
        n_trend=10, n_fade=10, n_fcn=10,
        bar_size=10, lookback_bars=8, order_volume=1,
        initial_market_price=300.0,
    )
    res = market.run(seed=seed)

    # bar 履歴が出ている (warmup + main = 280 step → 28 bar)
    assert len(res["history"]) >= 20, len(res["history"])
    assert res["prices"].ndim == 1 and res["prices"].size >= 20
    assert res["returns"].size == res["prices"].size - 1

    # signal log: lookback 経過後に signal が記録される
    sig_log = res["signal_log"]
    non_none = [s for _, s in sig_log if s is not None]
    assert len(non_none) > 0, "lookback 経過後に signal が出るはず"

    # agent action log: trend と fade それぞれで record がある (main session 開始後)
    n_trend_acts = sum(len(al) for al in res["trend_actions"])
    n_fade_acts = sum(len(al) for al in res["fade_actions"])
    assert n_trend_acts > 0, "trend agent が submit_orders_by_market で記録するはず"
    assert n_fade_acts > 0


def test_trend_fade_actions_opposite_under_constant_drift():
    """constant_signal_provider(pred > price) なら trend は +1, fade は -1 が dominant。"""
    market = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=305.0, pred_close_std=1.0),
        warmup_steps=80, main_steps=300,
        n_trend=8, n_fade=8, n_fcn=10,
        bar_size=10, lookback_bars=8, order_volume=1,
        initial_market_price=300.0,
    )
    res = market.run(seed=123)

    # 全 trend agent の action 平均、全 fade agent の action 平均
    trend_actions = np.concatenate(
        [np.asarray([a for _, a in log], dtype=int) for log in res["trend_actions"] if log]
    ) if any(res["trend_actions"]) else np.array([], dtype=int)
    fade_actions = np.concatenate(
        [np.asarray([a for _, a in log], dtype=int) for log in res["fade_actions"] if log]
    ) if any(res["fade_actions"]) else np.array([], dtype=int)
    assert trend_actions.size > 0 and fade_actions.size > 0
    # constant_signal_provider は pred=305 > last (≈ 300) で drift>0
    # → trend は +1 dominant, fade は -1 dominant
    assert trend_actions.mean() > 0.5
    assert fade_actions.mean() < -0.5


def test_bar_aggregator_returns_well_formed_ohlcv():
    """bar_aggregator が PAMS market から OHLCV を作る。"""
    # 軽い run で market を取る
    market_model = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.0),
        warmup_steps=20, main_steps=80,
        n_trend=4, n_fade=4, n_fcn=8,
        bar_size=5, lookback_bars=4, order_volume=1,
    )
    res = market_model.run(seed=1)
    h = res["history"]
    assert set(h.columns) >= {"timestamps", "open", "high", "low", "close", "volume", "amount"}
    # high >= max(open, close), low <= min(open, close)
    assert (h["high"] >= h[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (h["low"] <= h[["open", "close"]].min(axis=1) + 1e-9).all()
