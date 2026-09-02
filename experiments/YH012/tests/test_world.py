from __future__ import annotations

import copy

import numpy as np

from experiments.YH012.experiment import WorldExperiment
from experiments.YH012.metrics import orders_of_magnitude_compatible


def _base_config(**overrides) -> dict:
    cfg = {
        "seed": 42,
        "end_time": 25_000,
        "rule": "price_time",
        "mean_wakeup": 600,
        "f0": 10_000,
        "f_sigma": 0.25,
        "band": 30,
        "qty_min": 1,
        "qty_max": 5,
        "noise_offset_max": 15,
        "chartist_lookback": 3,
        "lobcore_root": "/workspace",
        "agents": {
            "n_fundamentalist": 30,
            "n_chartist": 25,
            "n_noise": 45,
        },
        "noise_take_prob": 0.15,
        "chartist_take_prob": 0.25,
    }
    for k, v in overrides.items():
        if k == "agents" and isinstance(v, dict):
            cfg["agents"] = {**cfg["agents"], **v}
        else:
            cfg[k] = v
    return cfg


def test_world_exit_criteria_single_seed():
    run = WorldExperiment(_base_config()).run()
    s = run.stats
    assert s.spread_positive_frac >= 0.90, s
    assert s.n_fills > 0, s
    assert s.mid_f_corr > 0.0, s
    assert run.result.meta.lobcore_version
    assert len(run.result.meta.lobcore_version) >= 7


def test_world_reproducible():
    cfg = _base_config(seed=99, end_time=15_000)
    a = WorldExperiment(copy.deepcopy(cfg)).run()
    b = WorldExperiment(copy.deepcopy(cfg)).run()
    assert a.result.state_hash == b.result.state_hash
    assert np.array_equal(a.result.log, b.result.log)
    assert a.result.meta.lobcore_version == b.result.meta.lobcore_version


def test_ten_seeds_similar_order():
    spreads: list[float] = []
    vols: list[float] = []
    corrs: list[float] = []
    for seed in range(10):
        run = WorldExperiment(_base_config(seed=seed, end_time=18_000, mean_wakeup=700)).run()
        assert run.stats.n_fills > 0, (seed, run.stats)
        assert run.stats.spread_positive_frac >= 0.90, (seed, run.stats)
        spreads.append(run.stats.mean_spread)
        vols.append(max(run.stats.volatility, 1e-12))
        corrs.append(run.stats.mid_f_corr)
    assert orders_of_magnitude_compatible(spreads), spreads
    assert orders_of_magnitude_compatible(vols), vols
    # 短時間ではシードにより相関がぶれる。平均と多数決でアンカーを確認。
    assert float(np.mean(corrs)) > 0.0, corrs
    assert sum(c > 0.0 for c in corrs) >= 7, corrs
