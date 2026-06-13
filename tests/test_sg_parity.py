"""SG backbone parity test (spec 001 T0 / AC2).

正準 SG (packages/abm_models) + 統一 SF (packages/stylized_facts) が、
speculation-game-info/YH005 の記録済み findings を統計的等価 (相対誤差 ≤ 5%) で
再現することを検証する。これが Stage B 移行の go-no-go ゲート。

また reference ↔ vectorized の bit-parity を確認し、core への移植が挙動を
変えていないことを保証する (AC1)。
"""

from __future__ import annotations

import numpy as np
import pytest

from abm_models.sg import BASELINE_PARAMS, SpeculationGame, run_reference, simulate
from stylized_facts import log_returns_from_prices, stylized_facts_summary

# YH005 outputs/baseline_metrics.json (N=1000,M=5,S=2,T=20000,B=9,C=3.0,seed=777)
RECORDED = {
    "std": 0.0032560438166104556,
    "ret_acf_1": 0.09171512436302687,
    "vol_acf_1": 0.2004195274849944,
    "vol_acf_200": 0.0159276459246795,
    "kurt_1": 3.630631815076492,
    "kurt_640": -0.40342223646773023,
    "hill_alpha": 4.526690654652822,
}
REL_TOL = 0.05  # spec 001 AC2: 統計的等価 = 相対誤差 ≤ 5%


def _rel_err(new: float, old: float) -> float:
    return abs(new - old) / abs(old)


@pytest.mark.slow
def test_sg_findings_parity_within_5pct():
    """正準 SG (vectorized) baseline の findings が記録値の相対 5% 以内。"""
    model = SpeculationGame(**BASELINE_PARAMS, backend="vectorized")
    res = model.run(seed=777)
    returns = log_returns_from_prices(res["prices"])
    summary = stylized_facts_summary(
        returns, acf_lags=(1, 14, 50, 200, 500), kurt_windows=(1, 16, 64, 256, 640)
    )

    got = {
        "std": summary["std"],
        "ret_acf_1": summary["ret_acf"][1],
        "vol_acf_1": summary["vol_acf"][1],
        "vol_acf_200": summary["vol_acf"][200],
        "kurt_1": summary["kurt"][1],
        "kurt_640": summary["kurt"][640],
        "hill_alpha": summary["hill_alpha"],
    }
    failures = {
        k: (got[k], RECORDED[k], _rel_err(got[k], RECORDED[k]))
        for k in RECORDED
        if _rel_err(got[k], RECORDED[k]) > REL_TOL
    }
    assert not failures, f"parity broken (rel>5%): {failures}\nall got={got}"


def test_sg_reference_vectorized_bit_parity():
    """小規模で reference と vectorized が bit-identical (移植ガード)。"""
    params = dict(N=50, M=2, S=2, T=300, B=9, C=3.0, p0=100.0)
    ref = run_reference(seed=42, **params)
    vec = simulate(seed=42, **params)
    np.testing.assert_array_equal(ref["prices"], vec["prices"])
    np.testing.assert_array_equal(ref["cognitive_prices"], vec["cognitive_prices"])
    assert ref["num_substitutions"] == vec["num_substitutions"]
    assert ref["total_wealth"] == vec["total_wealth"]
