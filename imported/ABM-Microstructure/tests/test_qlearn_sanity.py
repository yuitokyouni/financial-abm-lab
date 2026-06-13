"""T011: 学習の縮退 sanity（spec US1 Acceptance 3/4・SC-008）。

定数の設計根拠: 到着が疎だと reward が高分散になり、定常 lr の Q は argmax が
隣接 arm 間で flap する。検出力を上げるため sanity では noise_rate を高く（pn=0.3）、
action 数を小さく（K=7）取り、複数 seed 平均と方向 assertion で判定する。

memory=0 の核心 assertion は**構造的**なもの: state が不変なので逸脱に反応する経路が
存在せず、IR gate は punished=False を決定論で返す（「懲罰を条件づけられない →
collusion 不能」の理論整合）。実現水準の Nash 集合チェックは、ε 減衰を学習率に対して
十分遅くして co-adaptation（undercut 戦）を完走させた params で行う——減衰が速すぎると
tail で undercut の Q が更新されず勝者総取りの tie が grid 上限に固着する
（「探索不足の高止まり」。markup だけでは collusion と区別できない、という gate の
存在理由の実例。初版テストはまさにこれで落ちた）。
"""
import numpy as np
import pytest

from microstructure import benchmarks
from microstructure.learnconfig import LearnConfig
from microstructure.qlearn import train
from microstructure.verdict import certify, impulse_response, measure

SANITY = dict(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=30.0,
              n_actions=7, stable_window=25_000, measure_periods=4_000)


def _mean_realized(cfg_base, seeds):
    vals = []
    for s in seeds:
        cfg = cfg_base.replace(seed=s)
        vals.append(measure(cfg, train(cfg)).realized_spread)
    return float(np.mean(vals))


def test_n1_monopoly_direction():
    """n=1: 競争者がいなければ spread は上限方向（grid 上半分）へ行く（US1-AS3）。

    inelastic noise では monopoly = grid 上限（D-B11 ceiling）。reward 分散による
    最上位 arm 間の flap を許容し「上半分」を assert する。
    """
    cfg = LearnConfig(n_mm=1, memory=0, t_max=200_000, lr=0.05, eps_beta=3e-5,
                      **SANITY)
    mean = _mean_realized(cfg, (0, 1))
    assert mean >= cfg.action_grid[3]                      # 上半分
    assert mean > benchmarks.myopic_nash_spread(cfg.replace(n_mm=2))  # 競争水準より上


def test_memory0_cannot_be_certified():
    """memory=0 の構造的不可能性: 逸脱を観測する state が無い → 懲罰経路ゼロ →
    IR gate は punished=False を決定論で返し、markup が何であれ認定されない（US1-AS4 の核）。"""
    cfg = LearnConfig(n_mm=2, memory=0, t_max=60_000, lr=0.05, eps_beta=3e-5,
                      **SANITY)
    cells, irs = [], []
    for s in (0, 1):
        c = cfg.replace(seed=s)
        tr = train(c)
        cells.append(measure(c, tr))
        irs.append(impulse_response(c, tr))
    assert all(not ir.punished for ir in irs)              # 構造的に懲罰不能
    assert not certify(cells, irs).certified


def test_memory0_realized_in_nash_set():
    """memory=0 + γ=0（純 myopic）→ undercut 戦が完走し、実現 spread は
    myopic-Nash 集合の近傍に落ちる（US1-AS4 の実現水準）。

    γ=0 が理論的に正しい設定: memory=0 の対象は myopic BR の不動点（one-shot
    stage-game Nash）そのもの。γ>0 だと bootstrap 項 γV が arm 間の報酬差を
    矮小化し、reward 分散由来の Q ノイズと同サイズになって argmax が拡散する
    （γ=.95 では grid 上限への高止まりを観測——gate の存在理由の実例）。
    lr=0.02 は reward 分散に対する平均化（sd_Q ≈ sd_r·√(lr/2) < arm 間ギャップ）。
    離散 Bertrand の対称 Nash は一般に区間なので Nash 集合 ±½tick で判定。
    検証済み: 6 seed 全てが Nash 集合 {arm1, arm2} に収束（2026-06-10）。
    """
    cfg = LearnConfig(n_mm=2, memory=0, t_max=500_000, lr=0.02, gamma=0.0,
                      eps_beta=1.2e-5, **SANITY)
    cands = benchmarks.myopic_nash_candidates(cfg)
    spacing = cfg.action_grid[1] - cfg.action_grid[0]
    mean = _mean_realized(cfg, (0, 1))
    assert min(cands) - 0.5 * spacing <= mean <= max(cands) + 0.5 * spacing
    assert mean < cfg.action_grid[-1] - spacing            # ceiling には行かない


def test_train_deterministic():
    """同一 LearnConfig → Q 表まで bit 一致（FR-012 / D-B12）。"""
    cfg = LearnConfig(n_mm=2, memory=1, t_max=15_000, seed=42, lr=0.05,
                      eps_beta=3e-5, **SANITY)
    tr1, tr2 = train(cfg), train(cfg)
    for p1, p2 in zip(tr1.policies, tr2.policies):
        assert np.array_equal(p1.q, p2.q)
    assert (tr1.converged, tr1.periods_run) == (tr2.converged, tr2.periods_run)
    m1, m2 = measure(cfg, tr1), measure(cfg, tr2)
    assert m1.markup == m2.markup
