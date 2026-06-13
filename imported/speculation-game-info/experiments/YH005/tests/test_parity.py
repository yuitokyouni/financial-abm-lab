"""YH005: Reference ↔ Vectorized bit-parity tests + invariants.

§8.1 の受け入れ基準に従い、以下を検証:
  - 5 seeds × (N=30, M=3, S=2, T=300, B=9, C=3.0) で全出力キーが np.array_equal
  - S=1 の parity (3 seeds)
  - Null A (history_mode='exogenous') の parity
  - Null B (decision_mode='random')  の parity
  - 毎ステップ buy+sell+active+passive+idle == N の不変条件
  - cognitive_prices == cumsum(h_series) の不変条件
  - 同一 seed での決定性
  - seed 感度 (seed を変えると prices が変わる)

pytest 実行:
  cd experiments/YH005
  python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import run_reference
from simulate import simulate


PARAMS_DEFAULT = dict(N=30, M=3, S=2, T=300, B=9, C=3.0)
PARITY_KEYS = (
    "prices",
    "h_series",
    "cognitive_prices",
    "final_wealth",
    "num_buy",
    "num_sell",
    "num_active_hold",
    "num_passive_hold",
)
ROUND_TRIP_KEYS = (
    "agent_idx",
    "open_t",
    "close_t",
    "entry_action",
    "entry_quantity",
    "delta_G",
)
ORDER_SIZE_KEYS = (
    "num_orders_by_size",
    "num_orders_by_size_buy",
    "num_orders_by_size_sell",
)


def _assert_parity(ref: dict, vec: dict, ctx: str):
    for k in PARITY_KEYS:
        assert np.array_equal(ref[k], vec[k]), (
            f"{ctx}: key '{k}' mismatch; "
            f"ref[{k}][:5]={ref[k][:5] if hasattr(ref[k], '__len__') else ref[k]}, "
            f"vec[{k}][:5]={vec[k][:5] if hasattr(vec[k], '__len__') else vec[k]}"
        )
    assert ref["num_substitutions"] == vec["num_substitutions"], (
        f"{ctx}: num_substitutions mismatch "
        f"ref={ref['num_substitutions']} vec={vec['num_substitutions']}"
    )
    assert ref["total_wealth"] == vec["total_wealth"], (
        f"{ctx}: total_wealth mismatch "
        f"ref={ref['total_wealth']} vec={vec['total_wealth']}"
    )
    # round_trips (Phase 1 拡張)
    for k in ROUND_TRIP_KEYS:
        ref_arr = ref["round_trips"][k]
        vec_arr = vec["round_trips"][k]
        assert np.array_equal(ref_arr, vec_arr), (
            f"{ctx}: round_trips['{k}'] mismatch; "
            f"ref_len={len(ref_arr)}, vec_len={len(vec_arr)}, "
            f"ref[:5]={ref_arr[:5]}, vec[:5]={vec_arr[:5]}"
        )
    # num_orders_by_size (Phase 1 拡張)
    for k in ORDER_SIZE_KEYS:
        assert np.array_equal(ref[k], vec[k]), (
            f"{ctx}: key '{k}' mismatch; "
            f"ref.sum()={ref[k].sum()}, vec.sum()={vec[k].sum()}"
        )


@pytest.mark.parametrize("seed", [1, 2, 7, 42, 100])
def test_parity_default(seed: int):
    ref = run_reference(seed=seed, **PARAMS_DEFAULT)
    vec = simulate(seed=seed, **PARAMS_DEFAULT)
    _assert_parity(ref, vec, f"default seed={seed}")


@pytest.mark.parametrize("seed", [1, 2, 7])
def test_parity_S1(seed: int):
    params = dict(PARAMS_DEFAULT)
    params["S"] = 1
    ref = run_reference(seed=seed, **params)
    vec = simulate(seed=seed, **params)
    _assert_parity(ref, vec, f"S=1 seed={seed}")


def test_parity_null_a():
    ref = run_reference(seed=1, history_mode="exogenous", **PARAMS_DEFAULT)
    vec = simulate(seed=1, history_mode="exogenous", **PARAMS_DEFAULT)
    _assert_parity(ref, vec, "Null A")


def test_parity_null_b():
    ref = run_reference(seed=1, decision_mode="random", **PARAMS_DEFAULT)
    vec = simulate(seed=1, decision_mode="random", **PARAMS_DEFAULT)
    _assert_parity(ref, vec, "Null B")


def test_action_invariant():
    """buy + sell + active_hold + passive_hold + idle == N, idle >= 0"""
    res = simulate(seed=42, **PARAMS_DEFAULT)
    N = PARAMS_DEFAULT["N"]
    total_non_idle = (
        res["num_buy"] + res["num_sell"] + res["num_active_hold"] + res["num_passive_hold"]
    )
    assert (total_non_idle <= N).all(), "sum of 4 action kinds exceeds N"
    idle = N - total_non_idle
    assert (idle >= 0).all(), "idle count went negative"


def test_cognitive_cumsum():
    """cognitive_prices[t] == cumsum(h_series)[t]"""
    res = simulate(seed=42, **PARAMS_DEFAULT)
    expected = np.cumsum(res["h_series"].astype(np.int64))
    assert np.array_equal(res["cognitive_prices"], expected)


def test_determinism():
    """Same seed → identical output."""
    r1 = simulate(seed=42, **PARAMS_DEFAULT)
    r2 = simulate(seed=42, **PARAMS_DEFAULT)
    for k in PARITY_KEYS:
        assert np.array_equal(r1[k], r2[k]), f"non-determinism in {k}"


def test_seed_sensitivity():
    """Different seed → different prices."""
    r1 = simulate(seed=42, **PARAMS_DEFAULT)
    r2 = simulate(seed=43, **PARAMS_DEFAULT)
    assert not np.array_equal(r1["prices"], r2["prices"])


# ---------------------------------------------------------------------------
# Phase 1 拡張: round_trips と num_orders_by_size の invariant (§1.6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 42])
def test_roundtrip_invariants(seed: int):
    res = simulate(seed=seed, **PARAMS_DEFAULT)
    rt = res["round_trips"]
    if rt["close_t"].size == 0:
        return
    # 1) close_t > open_t
    assert (rt["close_t"] > rt["open_t"]).all(), "close_t must be strictly > open_t"
    # 2) close_t は非減少 (同一 step に複数 close は許される、agent_idx 順 append)
    assert (np.diff(rt["close_t"]) >= 0).all(), "close_t must be non-decreasing"
    # 3) entry_action ∈ {-1, +1}
    assert np.isin(rt["entry_action"], np.array([-1, 1], dtype=np.int8)).all()
    # 4) entry_quantity >= 1
    assert (rt["entry_quantity"] >= 1).all(), "entry_quantity must be >= 1"


@pytest.mark.parametrize("seed", [1, 42])
def test_order_size_bucket_invariants(seed: int):
    res = simulate(seed=seed, **PARAMS_DEFAULT)
    size_buy = res["num_orders_by_size_buy"]
    size_sell = res["num_orders_by_size_sell"]
    size_total = res["num_orders_by_size"]
    num_buy = res["num_buy"]
    num_sell = res["num_sell"]
    # 5) size.sum(axis=1) == num_buy + num_sell (全 step、effective != 0 の件数)
    assert np.array_equal(size_total.sum(axis=1), num_buy + num_sell)
    # 6) size_buy.sum(axis=1) == num_buy
    assert np.array_equal(size_buy.sum(axis=1), num_buy)
    # 7) size_sell.sum(axis=1) == num_sell
    assert np.array_equal(size_sell.sum(axis=1), num_sell)
    # 8) 要素単位で size == size_buy + size_sell
    assert np.array_equal(size_total, size_buy + size_sell)
