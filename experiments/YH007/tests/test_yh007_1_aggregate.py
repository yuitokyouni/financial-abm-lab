"""YH007-1 受け入れ基準: 同一 Kronos 予測から順張り/逆張りの 2 行動が
決定論的に分岐する (seed 固定で再現)。

実 Kronos は重く、テスト目的では `constant_signal_provider` (mock) で十分。
spec 002 §8 (YH007-1) の受け入れ条件をこのテストで充足する。
"""
from __future__ import annotations

import numpy as np

from abm_models.kronos_aggregate import (
    FadeAgent,
    KronosAggregateMarket,
    KronosSignal,
    TrendAgent,
    constant_signal_provider,
)


def test_trend_and_fade_split_on_same_signal():
    """同じ signal を渡したとき, Trend と Fade の action は逆符号 (または共に 0)。"""
    cases = [
        # (last_close, pred_close_mean) -> Trend, Fade の期待 action
        (100.0, 101.0, +1, -1),  # 上ドリフト
        (100.0, 99.0, -1, +1),  # 下ドリフト
        (100.0, 100.0, 0, 0),    # ドリフト無し → 両者 abstain
    ]
    for last, pred, trend_expected, fade_expected in cases:
        sig = KronosSignal(last_close=last, pred_close_mean=pred, pred_close_std=1.0)
        assert TrendAgent(0).decide(sig) == trend_expected, f"trend {last}->{pred}"
        assert FadeAgent(1).decide(sig) == fade_expected, f"fade {last}->{pred}"


def test_market_run_smoke_with_constant_signal():
    """Mock signal で smoke が完走し prices/returns が出る。"""
    market = KronosAggregateMarket(
        signal_provider=constant_signal_provider(pred_close_mean=101.0, pred_close_std=1.0),
        n_trend=10, n_fade=10, n_warmup=16, n_steps=20, initial_price=100.0,
    )
    res = market.run(seed=7)
    assert res["prices"].shape == (21,), res["prices"].shape  # initial + n_steps
    assert res["returns"].shape == (20,), res["returns"].shape
    assert res["actions"].shape == (20, 20), res["actions"].shape
    assert res["history"].shape[0] == 16 + 20


def test_market_run_decision_split_deterministic():
    """seed 固定で trend と fade の action 系列が決定論的に逆符号になる。

    constant_signal_provider(pred=101 > last) なので
    Trend は常に +1, Fade は常に -1。aggregate excess = (n_trend - n_fade)。
    """
    market = KronosAggregateMarket(
        signal_provider=constant_signal_provider(pred_close_mean=101.0),
        n_trend=7, n_fade=3, n_warmup=16, n_steps=10, initial_price=100.0,
    )
    res = market.run(seed=42)
    actions = res["actions"]  # (T, N)
    # 先頭 n_trend=7 は Trend, 残り n_fade=3 は Fade (model.py のレイアウト)
    assert np.all(actions[:, :7] == +1), "Trend は drift>0 で常に +1"
    assert np.all(actions[:, 7:] == -1), "Fade は drift>0 で常に -1"
    # excess = 7 - 3 = +4, log return = kappa * 4 / 10 = 0.001 * 0.4 = +0.0004
    assert np.all(res["returns"] > 0), "正の excess → 全 step で正リターン"


def test_market_run_reproducible_across_seeds():
    """同じ seed で 2 回回しても完全一致 (deterministic)。"""
    kwargs = dict(
        signal_provider=constant_signal_provider(pred_close_mean=101.0),
        n_trend=5, n_fade=5, n_warmup=8, n_steps=15, initial_price=100.0,
    )
    m1 = KronosAggregateMarket(**kwargs)
    m2 = KronosAggregateMarket(**kwargs)
    r1 = m1.run(seed=123)
    r2 = m2.run(seed=123)
    np.testing.assert_array_equal(r1["actions"], r2["actions"])
    np.testing.assert_allclose(r1["prices"], r2["prices"])


def test_market_returns_signal_history():
    """signal の drift / confidence が log されている (drift は対称構成で時不変)。"""
    market = KronosAggregateMarket(
        signal_provider=constant_signal_provider(pred_close_mean=101.0, pred_close_std=2.0),
        n_trend=4, n_fade=4, n_warmup=8, n_steps=5, initial_price=100.0,
    )
    res = market.run(seed=1)
    assert res["drift"].shape == (5,)
    assert res["confidence"].shape == (5,)
    # 対称構成 (4 trend vs 4 fade, drift > 0) → excess=0 → returns=0 → close 不変
    # → drift と confidence は 5 step を通じて一定値 (warmup 終端の close が起点)
    assert np.allclose(res["returns"], 0.0), res["returns"]
    assert np.allclose(np.diff(res["drift"]), 0.0), res["drift"]
    assert np.allclose(np.diff(res["confidence"]), 0.0), res["confidence"]
    # 値そのものは pred - last_after_warmup と |drift|/std
    expected_drift = 101.0 - res["prices"][0]
    np.testing.assert_allclose(res["drift"], expected_drift)
    np.testing.assert_allclose(res["confidence"], abs(expected_drift) / 2.0)
