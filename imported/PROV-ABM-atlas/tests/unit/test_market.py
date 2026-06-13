"""market: 価格更新の式・ED 集約・run の再現性(spec §3.1)。"""

from __future__ import annotations

import math

import numpy as np
from provabm.capture import CaptureLevel, CaptureSink
from toy.agents import make_population
from toy.market import Market, MarketParams, price_update, run_simulation


def _setup(seed: int, model: str, params: MarketParams):  # type: ignore[no-untyped-def]
    param_ss, *agent_ss = np.random.SeedSequence(seed).spawn(1 + params.n_agents)
    agents = make_population(model, params.n_agents, np.random.default_rng(param_ss))
    decision_rngs = [np.random.default_rng(s) for s in agent_ss]
    return agents, decision_rngs


_DEV = MarketParams(
    n_agents=20, lam=0.01, p_star=100.0, obs_window=10, burn_in=5, measure=15, init_price=100.0
)


def test_price_update_formula() -> None:
    # ED=0 → 価格不変。
    assert price_update(100.0, 0.0, 0.01, 500) == 100.0
    # ED=N → 100·exp(λ)。
    assert math.isclose(price_update(100.0, 500.0, 0.01, 500), 100.0 * math.exp(0.01))
    # 売り超過は価格を下げる。
    assert price_update(100.0, -250.0, 0.01, 500) < 100.0


def test_market_step_aggregates_ed_and_logreturn() -> None:
    m = Market(_DEV)
    actions = np.array([1, 1, -1, 0, 0], dtype=np.int64)  # ED = 1
    p0 = m.price
    ed = m.step(actions)
    assert ed == 1.0
    assert math.isclose(m.return_hist[-1], math.log(m.price / p0))
    assert m.volume_hist[-1] == 3.0  # |1|+|1|+|-1|


def test_run_simulation_shape_and_action_bounds() -> None:
    agents, rngs = _setup(0, "T", _DEV)
    result = run_simulation(_DEV, agents, rngs, CaptureSink(CaptureLevel.L0))
    assert len(result.steps) == _DEV.measure
    assert result.price.shape == (_DEV.measure,)
    # ED ∈ [-N, N]。
    assert np.all(np.abs(result.excess_demand) <= _DEV.n_agents)


def test_run_simulation_reproducible_same_seed() -> None:
    a1, r1 = _setup(42, "H", _DEV)
    a2, r2 = _setup(42, "H", _DEV)
    res1 = run_simulation(_DEV, a1, r1, CaptureSink(CaptureLevel.L0))
    res2 = run_simulation(_DEV, a2, r2, CaptureSink(CaptureLevel.L0))
    assert np.array_equal(res1.price, res2.price)
    assert np.array_equal(res1.agg_action, res2.agg_action)


def test_different_seed_diverges() -> None:
    a1, r1 = _setup(1, "H", _DEV)
    a2, r2 = _setup(2, "H", _DEV)
    res1 = run_simulation(_DEV, a1, r1, CaptureSink(CaptureLevel.L0))
    res2 = run_simulation(_DEV, a2, r2, CaptureSink(CaptureLevel.L0))
    # Model H は確率的選択を含むので異 seed で系列が割れる。
    assert not np.array_equal(res1.agg_action, res2.agg_action)


def test_l2_capture_records_ctx_calls() -> None:
    agents, rngs = _setup(0, "T", _DEV)
    capture = CaptureSink(CaptureLevel.L2)
    run_simulation(_DEV, agents, rngs, capture)
    # 全 agent × 全 step で最低 observe + submit_order が走る。
    total_steps = _DEV.burn_in + _DEV.measure
    assert len(capture) >= _DEV.n_agents * total_steps * 2
