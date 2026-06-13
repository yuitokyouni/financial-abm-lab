"""test_kernel_faithful — 高速経路(kernel)の決定性と参照への SF 忠実性を pin。

kernel.run_fast は参照 run_simulation と **bit 一致ではない**(noise の RNG threading 差)。
保証するのは (i) seed 固定で決定的、(ii) SF1-4 分布が参照と統計的に等価。
CI は NUMBA_DISABLE_JIT=1(素 Python 経路)なので市場は小さく保つ。
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from provabm.capture import CaptureLevel, CaptureSink
from toy.agents.trend import build_trend_population
from toy.calibration import CALIB_MARKET, T_STAR_ALPHA
from toy.kernel import run_fast
from toy.market import run_simulation
from toy.sf_battery import CALIBRATION_SF, measure_sf_battery

# CI(JIT off)で軽い小市場。
SMALL = replace(CALIB_MARKET, n_agents=30, burn_in=100, measure=200)


def test_run_fast_is_deterministic() -> None:
    """同一 seed → bit 同一の高速経路出力(再現性の地金)。"""
    a = run_fast(SMALL, "T", T_STAR_ALPHA, seed=11)
    b = run_fast(SMALL, "T", T_STAR_ALPHA, seed=11)
    assert np.array_equal(a, b)
    c = run_fast(SMALL, "T", T_STAR_ALPHA, seed=12)
    assert not np.array_equal(a, c)  # seed が違えば軌道も違う


def _ref_returns(model: str, mix: tuple[float, float, float], seed: int) -> np.ndarray:
    ss = np.random.SeedSequence(seed).spawn(1 + SMALL.n_agents)
    prng = np.random.default_rng(ss[0])
    agents = build_trend_population(SMALL.n_agents, prng, mix)
    drngs = [np.random.default_rng(s) for s in ss[1:]]
    return run_simulation(SMALL, agents, drngs, CaptureSink(CaptureLevel.L0)).returns


def _sf_dist(returns_list: list[np.ndarray]) -> np.ndarray:
    rows = []
    for r in returns_list:
        sf = measure_sf_battery(r, include_post=False)
        rows.append([sf[k] for k in CALIBRATION_SF])
    return np.asarray(rows, dtype=np.float64)


def test_fast_matches_reference_sf_distribution() -> None:
    """fast と reference の SF1-4 分布が統計的に等価(各次元、差 < 1 pooled std)。

    壊れた kernel は SF を桁で外す(例: SF4 clustering が 0 になる)ため、緩い許容でも検出する。
    """
    m = 12
    fast = _sf_dist([run_fast(SMALL, "T", T_STAR_ALPHA, seed=5000 + i) for i in range(m)])
    ref = _sf_dist([_ref_returns("T", T_STAR_ALPHA, 5000 + i) for i in range(m)])
    for d, name in enumerate(CALIBRATION_SF):
        diff = abs(float(fast[:, d].mean()) - float(ref[:, d].mean()))
        pooled = float(fast[:, d].std()) + float(ref[:, d].std()) + 1e-6
        assert diff <= pooled, f"{name}: fast/ref 乖離 {diff:.3f} > pooled std {pooled:.3f}"
