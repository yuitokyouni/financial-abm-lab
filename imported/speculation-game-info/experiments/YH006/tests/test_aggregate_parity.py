"""aggregate_sim.py (YH006 local fork) の parity / determinism test.

verify する invariant:
  1. uniform モードが YH005 simulate と同 seed で bit-一致 (fork 忠実性)
  2. Pareto モードが同 seed で reproducible (determinism)
  3. uniform と Pareto が同 seed でも結果が異なる (分岐が効いている sanity)

pytest 実行:
  cd experiments/YH006
  python -m pytest tests/test_aggregate_parity.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

try:
    import pytest
except ModuleNotFoundError:  # pytest 不在でも __main__ fallback で 9 ケース実行可能にする
    class _ParametrizeStub:
        @staticmethod
        def parametrize(*_args, **_kwargs):
            def _decorator(fn):
                return fn
            return _decorator

    class _PytestStub:
        mark = _ParametrizeStub()

    pytest = _PytestStub()  # type: ignore[assignment]

HERE = Path(__file__).resolve().parent
YH006 = HERE.parent
YH005 = YH006.parent / "YH005"
sys.path.insert(0, str(YH006))
sys.path.insert(0, str(YH005))

from aggregate_sim import simulate_aggregate  # noqa: E402
from simulate import simulate as yh005_simulate  # noqa: E402


# N=100, T=1000 はユーザー指定。M=5 / S=2 は YH006 2×2 の本番 params。
PARAMS_BASE = dict(N=100, M=5, S=2, T=1000, B=9, C=3.0, p0=100.0)

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


def _assert_full_parity(ref: dict, vec: dict, ctx: str) -> None:
    # YH005 にある全 key が YH006 uniform モードと bit-一致することを verify
    for k in PARITY_KEYS:
        assert np.array_equal(ref[k], vec[k]), (
            f"{ctx}: key {k!r} mismatch; "
            f"ref[:5]={ref[k][:5] if hasattr(ref[k], '__len__') else ref[k]}, "
            f"vec[:5]={vec[k][:5] if hasattr(vec[k], '__len__') else vec[k]}"
        )
    assert ref["num_substitutions"] == vec["num_substitutions"], (
        f"{ctx}: num_substitutions mismatch "
        f"ref={ref['num_substitutions']} vec={vec['num_substitutions']}"
    )
    assert ref["total_wealth"] == vec["total_wealth"], (
        f"{ctx}: total_wealth mismatch "
        f"ref={ref['total_wealth']} vec={vec['total_wealth']}"
    )
    for k in ROUND_TRIP_KEYS:
        ra = ref["round_trips"][k]
        va = vec["round_trips"][k]
        assert np.array_equal(ra, va), (
            f"{ctx}: round_trips[{k!r}] mismatch; "
            f"ref_len={len(ra)} vec_len={len(va)}; "
            f"ref[:5]={ra[:5]} vec[:5]={va[:5]}"
        )
    for k in ORDER_SIZE_KEYS:
        assert np.array_equal(ref[k], vec[k]), (
            f"{ctx}: key {k!r} mismatch; "
            f"ref.sum()={ref[k].sum()} vec.sum()={vec[k].sum()}"
        )
    # YH005 側にある key は全て YH006 側にも存在する (シンクしている前提)
    missing = set(ref.keys()) - set(vec.keys())
    assert not missing, f"{ctx}: YH006 is missing YH005 keys: {missing}"


@pytest.mark.parametrize("seed", [1, 42, 777, 12345])
def test_uniform_mode_bit_parity_with_yh005(seed: int) -> None:
    """aggregate_sim(wealth_mode='uniform') == YH005 simulate() at same seed."""
    ref = yh005_simulate(seed=seed, **PARAMS_BASE)
    vec = simulate_aggregate(seed=seed, wealth_mode="uniform", **PARAMS_BASE)
    _assert_full_parity(ref, vec, f"uniform parity seed={seed}")


@pytest.mark.parametrize("seed", [1, 777])
def test_pareto_mode_reproducible(seed: int) -> None:
    """Same seed + Pareto mode → identical output (determinism)."""
    kw = dict(seed=seed, wealth_mode="pareto", pareto_alpha=1.5, pareto_xmin=9, **PARAMS_BASE)
    a = simulate_aggregate(**kw)
    b = simulate_aggregate(**kw)
    for k in PARITY_KEYS:
        assert np.array_equal(a[k], b[k]), (
            f"pareto determinism broken at key {k!r} seed={seed}"
        )
    assert a["num_substitutions"] == b["num_substitutions"]
    assert a["total_wealth"] == b["total_wealth"]
    for k in ROUND_TRIP_KEYS:
        assert np.array_equal(a["round_trips"][k], b["round_trips"][k]), (
            f"pareto determinism broken at round_trips[{k!r}] seed={seed}"
        )


@pytest.mark.parametrize("seed", [1, 42, 777])
def test_uniform_pareto_differ(seed: int) -> None:
    """Same seed でも uniform と Pareto は分岐が効いているので結果が異なる."""
    u = simulate_aggregate(seed=seed, wealth_mode="uniform", **PARAMS_BASE)
    p = simulate_aggregate(
        seed=seed, wealth_mode="pareto", pareto_alpha=1.5, pareto_xmin=9, **PARAMS_BASE
    )
    # 初期 wealth 分布が違えば final_wealth も必ず違う (bankruptcy 以外で分岐が効く)
    assert not np.array_equal(u["final_wealth"], p["final_wealth"]), (
        f"seed={seed}: uniform と Pareto で final_wealth が同じ — Pareto 分岐が無効?"
    )
    # 価格系列も違うはず (初期 wealth が order size q = w//B を決めるため)
    assert not np.array_equal(u["prices"], p["prices"]), (
        f"seed={seed}: uniform と Pareto で prices が同じ — 需要が分岐に影響していない?"
    )


if __name__ == "__main__":
    # 直接実行でも parametrize をループで回す (pytest 不在時の fallback)
    for s in [1, 42, 777, 12345]:
        test_uniform_mode_bit_parity_with_yh005(s)
    print("[parity] uniform mode × 4 seeds bit-parity with YH005 — OK")
    for s in [1, 777]:
        test_pareto_mode_reproducible(s)
    print("[parity] Pareto mode × 2 seeds reproducible — OK")
    for s in [1, 42, 777]:
        test_uniform_pareto_differ(s)
    print("[parity] uniform vs Pareto differ × 3 seeds — OK")
    print("all 9 checks passed")
