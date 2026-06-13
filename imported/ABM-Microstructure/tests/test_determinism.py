"""SC-004: 同一 seed → 同一出力（決定論・再現性）。"""
from dataclasses import replace

from microstructure import SimConfig, run


def _cfg(**kw):
    base = dict(n_periods=50000, seed=7, dt=1e-2, alpha=0.3, lambda_jump=8.0,
                jump_size=1.0, half_spread=0.1, noise_rate=1.0)
    base.update(kw)
    return SimConfig(**base)


def test_same_seed_same_output():
    a = run(_cfg())
    b = run(_cfg())
    assert a.metrics == b.metrics


def test_different_seed_differs():
    a = run(_cfg(seed=1))
    b = run(_cfg(seed=2))
    assert a.metrics.extraction != b.metrics.extraction


def test_batch_deterministic():
    a = run(_cfg(mechanism="batch", batch_interval=10))
    b = run(_cfg(mechanism="batch", batch_interval=10))
    assert a.metrics == b.metrics
