"""test_channel_band — 脱共役による識別の核を pin(再設計 P1)。

連続市場では価格チャネルと注文流チャネルが同一信号(return=λ·flow)なので、
price-reader(A)と orderflow-reader(B)は **bit 同一**の軌道を生む = 観測で区別不能。
batch auction はこの両チャネルを脱共役するので A と B は分岐する。
この「連続=同一 / batch=分岐」が再設計 P1 の load-bearing な性質。
"""

from __future__ import annotations

import numpy as np
from toy.channel_band import BandParams, simulate

# テストは軽く(短い market)。
SMALL = BandParams(n_agents=80, steps=400, burn_in=100)


def test_continuous_A_equals_B_bitwise() -> None:
    """連続市場(batch=1): A(価格)と B(注文流)は同一信号を読む → bit 同一 = 区別不能。"""
    a = simulate("A", 1, seed=7, params=SMALL)
    b = simulate("B", 1, seed=7, params=SMALL)
    assert a.size == b.size and a.size > 0
    assert np.array_equal(a, b)  # 観測上 identical


def test_batch_decouples_A_and_B() -> None:
    """batch auction(batch=10): 価格と注文流が脱共役 → A と B は分岐する。"""
    a = simulate("A", 10, seed=7, params=SMALL)
    b = simulate("B", 10, seed=7, params=SMALL)
    assert a.size == b.size and a.size > 0
    assert not np.array_equal(a, b)  # 政策介入が両機構を識別可能にする


def test_determinism() -> None:
    """同一 seed → bit 同一(再現性)。"""
    assert np.array_equal(
        simulate("A", 10, seed=3, params=SMALL), simulate("A", 10, seed=3, params=SMALL)
    )
    assert not np.array_equal(
        simulate("A", 10, seed=3, params=SMALL), simulate("A", 10, seed=4, params=SMALL)
    )


def test_continuous_adaptive_equals_A() -> None:
    """連続: 両チャネル同一 → 学習(adaptive)は固定 A と一致(学習が見えない)。batch で分岐。"""
    assert np.array_equal(
        simulate("A", 1, seed=7, params=SMALL), simulate("adaptive", 1, seed=7, params=SMALL)
    )
    assert not np.array_equal(
        simulate("A", 10, seed=7, params=SMALL), simulate("adaptive", 10, seed=7, params=SMALL)
    )


def test_with_flow_returns_pair() -> None:
    """with_flow=True で (batch_returns, order-flow 系列) を返す(案3 microstructure)。"""
    rets, flow = simulate("A", 5, seed=7, params=SMALL, with_flow=True)
    assert rets.ndim == 1 and flow.ndim == 1 and flow.size > rets.size
