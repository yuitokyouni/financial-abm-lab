"""SC-002/003: 連続 vs batch の抽出量、σ(=vol proxy)・N スケーリング。"""
from dataclasses import replace

from microstructure import SimConfig, run


def _base(**kw):
    base = dict(n_periods=300000, seed=2, dt=1e-2, alpha=0.4, lambda_jump=10.0,
                jump_size=1.0, half_spread=0.1, noise_rate=1.0)
    base.update(kw)
    return SimConfig(**base)


def test_batch_reduces_extraction():
    cont = run(_base()).extraction_rate
    b5 = run(_base(mechanism="batch", batch_interval=5)).extraction_rate
    assert b5 < cont


def test_extraction_monotone_decreasing_in_N():
    rates = [run(_base(mechanism="batch", batch_interval=N)).extraction_rate
             for N in (1, 5, 20)]
    assert rates[0] >= rates[1] >= rates[2]


def test_extraction_increases_in_volatility():
    """vol proxy = lambda_jump（realized var ∝ lambda*J^2）。高 vol ほど抽出大。"""
    lo = run(_base(lambda_jump=5.0)).extraction_rate
    hi = run(_base(lambda_jump=15.0)).extraction_rate
    assert hi > lo


def test_batch_n1_approx_continuous():
    """N=1 batch ≈ 連続（sanity）。rng 順は違うので相対 15% 内。"""
    cont = run(_base()).extraction_rate
    b1 = run(_base(mechanism="batch", batch_interval=1)).extraction_rate
    assert abs(b1 - cont) <= 0.15 * cont
