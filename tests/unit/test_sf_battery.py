"""sf_battery: SF1-5 測定の sanity(spec §4)。"""

from __future__ import annotations

import numpy as np
from toy.sf_battery import (
    CALIBRATION_SF,
    measure_sf_battery,
    sf1_return_acf,
    sf3_excess_kurtosis,
    sf4_garch_persistence,
)


def _gaussian(n: int = 4000, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, 0.01, size=n)


def test_battery_keys() -> None:
    sf = measure_sf_battery(_gaussian())
    assert {"SF1", "SF2", "SF3", "SF4", "SF5"} <= set(sf)
    assert all(np.isfinite(v) for v in sf.values())
    assert CALIBRATION_SF == ("SF1", "SF2", "SF3", "SF4")


def test_iid_gaussian_has_low_return_acf() -> None:
    # IID は return autocorrelation がほぼ無い → SF1 小、excess kurtosis ≈ 0。
    g = _gaussian(8000, seed=1)
    assert sf1_return_acf(g) < 0.1
    assert abs(sf3_excess_kurtosis(g)) < 0.3


def test_constant_returns_degenerate_safe() -> None:
    z = np.zeros(500, dtype=np.float64)
    sf = measure_sf_battery(z)
    assert all(np.isfinite(v) for v in sf.values())
    assert sf["SF1"] == 0.0


def test_garch_persistence_in_unit_interval_ish() -> None:
    # 強いボラ集中を持つ合成系列で α+β が高め(< 1.1)に出る。
    rng = np.random.default_rng(2)
    n = 4000
    r = np.zeros(n)
    vol = 0.01
    for t in range(1, n):
        vol = float(np.sqrt(0.000001 + 0.1 * r[t - 1] ** 2 + 0.88 * vol**2))
        r[t] = rng.normal(0, vol)
    s = sf4_garch_persistence(r)
    assert 0.0 <= s < 1.1
