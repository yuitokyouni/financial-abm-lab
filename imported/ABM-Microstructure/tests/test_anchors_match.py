"""SC-001/005: sim を解析アンカーに照合。

判定（D6）: tight な統計 consistency（複数 seed の SE）＋ 形/スケーリング再現。
flat な「緩い方 5%」は使わない。小さい abs floor のみ補助に置く。
"""
from dataclasses import replace

import numpy as np
import pytest

from microstructure import SimConfig, measure_competitive_spread, run
from microstructure import anchors

# coverage: alpha・lambda(=vol proxy)・J の関連レンジ＋stress（高 lambda・大 J）
GM_PARAMS = [
    dict(alpha=0.2, lambda_jump=5.0, jump_size=1.0),
    dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0),
    dict(alpha=0.5, lambda_jump=5.0, jump_size=1.0),
    dict(alpha=0.2, lambda_jump=10.0, jump_size=1.0),
    dict(alpha=0.3, lambda_jump=8.0, jump_size=2.0),
    dict(alpha=0.5, lambda_jump=10.0, jump_size=1.0),
    dict(alpha=0.1, lambda_jump=5.0, jump_size=1.0),
    dict(alpha=0.4, lambda_jump=15.0, jump_size=1.5),  # stress
]


@pytest.mark.parametrize("p", GM_PARAMS)
def test_gm_break_even_matches(p):
    base = SimConfig(n_periods=120000, seed=0, dt=1e-2, noise_rate=1.0,
                     mechanism="continuous", **p)
    anchor = anchors.gm_break_even(p["lambda_jump"], p["jump_size"],
                                   p["alpha"], base.noise_rate)
    hbe = np.array([measure_competitive_spread(replace(base, seed=s))
                    for s in range(5)])
    mean, se = hbe.mean(), hbe.std(ddof=1) / np.sqrt(len(hbe))
    tol = max(base.se_mult * se, 0.03 * anchor)  # tight SE 主、わずかな floor
    assert abs(mean - anchor) <= tol, f"sim {mean:.4f} vs anchor {anchor:.4f} (tol {tol:.4f})"


def test_gm_dt_stability():
    """dt→0 でアンカーは不変（dt が cancel する連続時間極限）。粗/細 dt で h* が安定。"""
    p = dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0)
    anchor = anchors.gm_break_even(p["lambda_jump"], p["jump_size"], p["alpha"], 1.0)
    coarse = measure_competitive_spread(
        SimConfig(n_periods=120000, seed=0, dt=1e-2, noise_rate=1.0, **p))
    fine = measure_competitive_spread(
        SimConfig(n_periods=240000, seed=0, dt=5e-3, noise_rate=1.0, **p))
    assert abs(coarse - anchor) < 0.1 * anchor
    assert abs(fine - anchor) < 0.1 * anchor


# ---- impact 層（SC-005, D5b v2）: identity-blind flow 回帰 λ̂ vs kyle_lambda ----
# 旧版（informed_impact == J == anchor）は sim の Bayesian 更新と circular で検出力ゼロ
# だったため置換（finding 0001 ③ の閉鎖）。

KYLE_PARAMS = [
    dict(alpha=0.1, lambda_jump=5.0, jump_size=1.0, noise_rate=1.0),
    dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0, noise_rate=1.0),
    dict(alpha=0.5, lambda_jump=10.0, jump_size=1.0, noise_rate=1.0),
    dict(alpha=0.3, lambda_jump=8.0, jump_size=2.0, noise_rate=2.0),
    dict(alpha=0.4, lambda_jump=15.0, jump_size=1.5, noise_rate=0.5),  # stress
]


@pytest.mark.parametrize("p", GM_PARAMS)
def test_kyle_gm_identity(p):
    """GM の定理: N=1 で λ(1) = h*。spread 層（PnL break-even scan）と impact 層
    （flow 回帰）が別経路で同一閉形式に収束する三角検証の anchor 側。"""
    hstar = anchors.gm_break_even(p["lambda_jump"], p["jump_size"], p["alpha"], 1.0)
    lam = anchors.kyle_lambda(p["lambda_jump"], p["jump_size"], p["alpha"], 1.0,
                              dt=1e-2, half_spread=hstar, batch_interval=1)
    assert lam == pytest.approx(hstar, rel=1e-12)


@pytest.mark.parametrize("p", KYLE_PARAMS)
def test_kyle_lambda_matches_continuous(p):
    """sim λ̂（識別盲回帰）が flow 組成アンカーに tight SE で一致（関数形=α・noise_rate・J 依存）。"""
    base = SimConfig(n_periods=120000, seed=0, dt=1e-2, mechanism="continuous",
                     half_spread=0.3 * p["jump_size"], **p)
    anchor = anchors.kyle_lambda(p["lambda_jump"], p["jump_size"], p["alpha"],
                                 p["noise_rate"], base.dt, base.half_spread, 1)
    vals = np.array([run(replace(base, seed=s)).metrics.price_impact for s in range(5)])
    mean, se = vals.mean(), vals.std(ddof=1) / np.sqrt(len(vals))
    tol = max(base.se_mult * se, 0.03 * anchor)
    assert abs(mean - anchor) <= tol, f"sim {mean:.4f} vs anchor {anchor:.4f} (tol {tol:.4f})"


@pytest.mark.parametrize("N", [5, 20])
def test_kyle_lambda_matches_batch(N):
    """batch λ(N): netting（binomial net 変位）× noise 希釈（N·dt 線形蓄積）を anchor と照合。"""
    p = dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0, noise_rate=1.0)
    base = SimConfig(n_periods=200000, seed=0, dt=1e-2, mechanism="batch",
                     batch_interval=N, half_spread=0.5, **p)
    anchor = anchors.kyle_lambda(p["lambda_jump"], p["jump_size"], p["alpha"],
                                 p["noise_rate"], base.dt, base.half_spread, N)
    vals = np.array([run(replace(base, seed=s)).metrics.price_impact for s in range(5)])
    mean, se = vals.mean(), vals.std(ddof=1) / np.sqrt(len(vals))
    tol = max(base.se_mult * se, 0.03 * anchor)
    assert abs(mean - anchor) <= tol, f"N={N}: sim {mean:.4f} vs anchor {anchor:.4f} (tol {tol:.4f})"


def test_kyle_lambda_noise_dilution_form():
    """関数形: λ は noise_rate で単調減（identity-blind flow の informed 含有率の希釈）。"""
    p = dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0)
    grid = [anchors.kyle_lambda(p["lambda_jump"], p["jump_size"], p["alpha"],
                                nr, 1e-2, 0.3, 1) for nr in (0.5, 1.0, 2.0, 4.0)]
    assert all(a > b for a, b in zip(grid, grid[1:]))
    sims = []
    for nr in (0.5, 4.0):
        base = SimConfig(n_periods=120000, seed=0, dt=1e-2, noise_rate=nr,
                         half_spread=0.3, **p)
        sims.append(np.mean([run(replace(base, seed=s)).metrics.price_impact
                             for s in range(3)]))
    assert sims[0] > sims[1]


def test_kyle_lambda_dt_convergence():
    """D6: anchor は N=1 で dt が厳密に cancel、batch は T_batch 固定の dt 細分で収束。
    sim は dt 細分でも anchor に一致し続ける（離散化誤差を flat tolerance に吸わせない）。"""
    p = dict(alpha=0.3, lambda_jump=5.0, jump_size=1.0, noise_rate=1.0)
    a1 = anchors.kyle_lambda(5.0, 1.0, 0.3, 1.0, 1e-2, 0.3, 1)
    a2 = anchors.kyle_lambda(5.0, 1.0, 0.3, 1.0, 1e-3, 0.3, 1)
    assert a1 == pytest.approx(a2, rel=1e-12)
    b1 = anchors.kyle_lambda(5.0, 1.0, 0.3, 1.0, 1e-2, 0.5, 20)
    b2 = anchors.kyle_lambda(5.0, 1.0, 0.3, 1.0, 5e-3, 0.5, 40)
    assert b1 == pytest.approx(b2, rel=5e-3)  # 実測 rel 差 ~0.2%（単調収束）
    for dt, n in ((1e-2, 120000), (5e-3, 240000)):
        base = SimConfig(n_periods=n, seed=0, dt=dt, half_spread=0.3, **p)
        anchor = anchors.kyle_lambda(p["lambda_jump"], p["jump_size"], p["alpha"],
                                     p["noise_rate"], dt, base.half_spread, 1)
        vals = np.array([run(replace(base, seed=s)).metrics.price_impact
                         for s in range(3)])
        mean, se = vals.mean(), vals.std(ddof=1) / np.sqrt(len(vals))
        assert abs(mean - anchor) <= max(base.se_mult * se, 0.03 * anchor)


def test_extraction_nonnegative_and_accounting():
    cfg = SimConfig(n_periods=80000, seed=1, dt=1e-2, alpha=0.3, lambda_jump=8.0,
                    jump_size=1.0, half_spread=0.1, noise_rate=1.0)
    m = run(cfg).metrics
    assert m.extraction >= 0
    assert m.mm_trading_pnl == pytest.approx(m.noise_pnl - m.extraction)
