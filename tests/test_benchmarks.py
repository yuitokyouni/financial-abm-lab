"""T005: benchmarks（markup 分母・floor 参照点）の検証。

Nash→GM h* の grid 細分収束が 001 anchor への接続。順序は D-B5 訂正後の形
（ZI は中間参照点。「ZI ≤ Nash」は定理ではない——default grid では Nash ≤ ZI）。
"""
import itertools

import numpy as np
import pytest

from microstructure import anchors, benchmarks
from microstructure.learnconfig import LearnConfig
from microstructure.qlearn import train
from microstructure.verdict import measure

BASE = dict(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=1.0)


def test_nash_converges_to_gm_break_even():
    """grid 細分で最小対称 Nash → h*（最初の非負利潤点に張り付く＝間隔以内、細分で単調縮小）。"""
    hstar = anchors.gm_break_even(BASE["lambda_jump"], BASE["jump_size"],
                                  BASE["alpha"], BASE["noise_rate"])
    gaps = []
    for K in (15, 61, 241):
        cfg = LearnConfig(n_actions=K, **BASE)
        nash = benchmarks.myopic_nash_spread(cfg)
        spacing = cfg.action_grid[1] - cfg.action_grid[0]
        assert nash >= hstar - 1e-12
        assert nash - hstar <= spacing + 1e-12
        gaps.append(nash - hstar)
    assert gaps[2] < gaps[0]


def test_nash_candidates_nonneg_profit():
    cfg = LearnConfig(**BASE)
    cands = benchmarks.myopic_nash_candidates(cfg)
    assert cands and min(cands) == benchmarks.myopic_nash_spread(cfg)
    assert all(benchmarks.winner_payoff(h, cfg) >= -1e-12 for h in cands)


@pytest.mark.parametrize("mech,N", [("continuous", 1), ("batch", 20)])
def test_nash_is_first_nonneg_point(mech, N):
    """定義整合: nash = その機構の最初の非負利潤 grid 点（π は h で単調増）。"""
    cfg = LearnConfig(mechanism=mech, batch_interval=N, **BASE)
    nash = benchmarks.myopic_nash_spread(cfg)
    grid = cfg.action_grid
    idx = grid.index(nash)
    assert benchmarks.winner_payoff(nash, cfg) >= -1e-12
    if idx > 0:
        assert benchmarks.winner_payoff(grid[idx - 1], cfg) < 0


def test_batch_denominator_mechanism_specific():
    """markup 分母は機構別（batch の break-even は netting で連続と低い、D-B4）。

    K=15 では両機構の break-even が同一 grid セルに量子化され一致しうる（それ自体は
    正しい挙動）ため、差が解像する K=61 で検証する。
    """
    n_cont = benchmarks.myopic_nash_spread(LearnConfig(n_actions=61, **BASE))
    n_bat = benchmarks.myopic_nash_spread(
        LearnConfig(n_actions=61, mechanism="batch", batch_interval=20, **BASE))
    assert n_bat < n_cont   # netting（finding 0001 の低 h 側）で batch の逆選択が軽い


def test_revisable_removes_sniping_term():
    com = LearnConfig(**BASE)
    rev = LearnConfig(staleness="revisable", **BASE)
    for h in com.action_grid:
        assert benchmarks.winner_payoff(h, rev) >= benchmarks.winner_payoff(h, com) - 1e-15
    # 低 h（sniping 域）では厳密に大きい
    low = com.action_grid[0]
    assert benchmarks.winner_payoff(low, rev) > benchmarks.winner_payoff(low, com)


def test_monopoly_grid_ceiling_and_interior():
    """inelastic では grid 上限（D-B11 の文書化済み ceiling）、有限 R では内点。"""
    cfg = LearnConfig(**BASE)
    assert benchmarks.monopoly_grid(cfg) == cfg.action_grid[-1]
    # R=J だと逆選択＋弾力需要で全 h について π≤0（monopolist でも市場非成立）に
    # なるため、内点 monopoly が立つ R=3.0 で検証する。
    cfg_r = LearnConfig(noise_reserve=3.0, **BASE)
    mono_r = benchmarks.monopoly_grid(cfg_r)
    assert mono_r < cfg_r.action_grid[-1]
    assert benchmarks.winner_payoff(mono_r, cfg_r) > 0


def test_nash_le_monopoly_and_n1_equivalence():
    for mech, N in (("continuous", 1), ("batch", 10)):
        cfg = LearnConfig(mechanism=mech, batch_interval=N, **BASE)
        assert benchmarks.myopic_nash_spread(cfg) <= benchmarks.monopoly_grid(cfg)
    cfg1 = LearnConfig(n_mm=1, **BASE)
    assert benchmarks.myopic_nash_spread(cfg1) == benchmarks.monopoly_grid(cfg1)


def test_zi_floor_exact_vs_bruteforce():
    for n in (2, 3):
        cfg = LearnConfig(n_mm=n, **BASE)
        grid = cfg.action_grid
        K = len(grid)
        brute = np.mean([grid[min(combo)]
                         for combo in itertools.product(range(K), repeat=n)])
        assert benchmarks.zi_floor(cfg) == pytest.approx(float(brute), rel=1e-12)


def test_zi_floor_matches_sim():
    """ZI 解析値 = ZIPolicy 実測（D-B5 の解析/sim 二重化）。"""
    cfg = LearnConfig(algo="zi", memory=0, measure_periods=20000, seed=7, **BASE)
    m = measure(cfg, train(cfg))
    assert abs(m.realized_spread - benchmarks.zi_floor(cfg)) < 0.03


def test_nash_le_zi_on_default_grid():
    """default grid の経験的性質（定理ではない、D-B5 訂正）: Nash は break-even 近傍、
    ZI=E[min h] は grid 中央寄り。grid 設定を変えると逆転しうるため invariant にはしない。"""
    for mech, N in (("continuous", 1), ("batch", 20)):
        cfg = LearnConfig(mechanism=mech, batch_interval=N, **BASE)
        assert benchmarks.myopic_nash_spread(cfg) <= benchmarks.zi_floor(cfg)
