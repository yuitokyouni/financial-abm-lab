"""解析ベンチマーク — markup 分母（機構別 myopic-Nash）と floor 参照点（research D-B4/D-B5）。

**このモジュールは env/qlearn/verdict を import しない**（anchors と stdlib のみ）。
markup の分母が学習コードのバグを共有しないことを構造で担保する（001 anchors 規律の B 版）。

stage game（1 学習期 = 1 clearing サイクル）:
  各 MM が half-spread h_i ∈ grid を提示。勝者 = min h（tie は等分割）。勝者が全 flow を取る:
    π(h) = N·p_n·accept(h)·(h + f) − α·E[(|S_N| − h)+]      （committed）
    π(h) = N·p_n·accept(h)·(h + f)                           （revisable: sniping 項 ≡ 0）
  N = 学習期内 step 数（continuous=1）、p_n = noise_rate·dt、accept(h) = 1 − h/R（R=∞ で 1）。
  E[(|S_N|−h)+] は anchors の binomial 厳密和（001 検証済みの netting 機構を共有）。

順序の注意（D-B5 訂正）: 勝者総取りの spread 競争では理論順序は
  myopic-Nash ≤ 学習実現（収束時）/ ZI
であり、「ZI ≤ Nash」は一般に成立しない（ZI = E[min h] は grid 支持域の中央寄り、
Nash は break-even 近傍）。ZI は「知能ゼロの中間参照点」として報告する。
"""
from __future__ import annotations

import math

from .anchors import _iter_net_displacement
from .learnconfig import LearnConfig


def _noise_accept(h: float, reserve: float) -> float:
    """noise の約定受諾率（D-B11: 留保 half-spread r~U(0,R)、h ≤ r で約定。R=∞ → 1）。"""
    if math.isinf(reserve):
        return 1.0
    return max(0.0, 1.0 - h / reserve)


def winner_payoff(h: float, cfg: LearnConfig) -> float:
    """勝者が単独で全 flow を取るときの期待期 PnL（tie 分割前）。"""
    n_steps = cfg.period_steps
    p_n = cfg.noise_rate * cfg.dt
    noise_rev = n_steps * p_n * _noise_accept(h, cfg.noise_reserve) * (h + cfg.fee)
    if cfg.staleness == "revisable":
        return noise_rev
    q = cfg.lambda_jump * cfg.dt
    snipe = cfg.alpha * sum(p * (s - h)
                            for p, s in _iter_net_displacement(n_steps, q, cfg.jump_size)
                            if s > h)
    return noise_rev - snipe


def stage_payoff(a_idx: int, others_idx: tuple[int, ...], cfg: LearnConfig) -> float:
    """MM i（action index a_idx）の期待 stage 利得。比較は index で厳密（grid 単調増）。"""
    if not others_idx:
        return winner_payoff(cfg.action_grid[a_idx], cfg)
    others_min = min(others_idx)
    if a_idx > others_min:
        return 0.0
    k = 1 + (sum(1 for j in others_idx if j == a_idx) if a_idx == others_min else 0)
    return winner_payoff(cfg.action_grid[a_idx], cfg) / k


def myopic_nash_candidates(cfg: LearnConfig) -> list[float]:
    """対称純戦略 Nash の実現 half-spread 全候補（grid 上の全列挙、D-B4）。

    対称 profile（全員 a）が Nash ⟺ 単独逸脱で利得が増えない:
      下方 b<a: 全取り π(b) ≤ π(a)/n、上方 b>a: 0 ≤ π(a)/n。
    n=1 は逸脱先でも常に勝者なので argmax（= monopoly）に一致する。
    """
    grid = cfg.action_grid
    pays = [winner_payoff(h, cfg) for h in grid]
    if cfg.n_mm == 1:
        best = max(pays)
        return [grid[i] for i, p in enumerate(pays) if p >= best - 1e-15]
    out = []
    for a in range(len(grid)):
        eq = pays[a] / cfg.n_mm
        best_undercut = max(pays[:a], default=-math.inf)
        if eq >= best_undercut - 1e-15 and eq >= -1e-15:
            out.append(grid[a])
    return out


def myopic_nash_spread(cfg: LearnConfig) -> float:
    """markup 分母 = 最も競争的な（最小の）対称 Nash half-spread（D-B4。機構別）。"""
    cands = myopic_nash_candidates(cfg)
    if not cands:
        raise RuntimeError("no symmetric pure Nash on grid (unexpected: lowest "
                           "non-negative-profit point should qualify)")
    return min(cands)


def monopoly_grid(cfg: LearnConfig) -> float:
    """n=1 の最適 half-spread（sanity 専用。inelastic では grid 上限 = 文書化済み ceiling, D-B11）。"""
    grid = cfg.action_grid
    return max(grid, key=lambda h: winner_payoff(h, cfg))


def zi_floor(cfg: LearnConfig) -> float:
    """知能ゼロ参照点 = E[min(h_1..h_n)]、各 h は grid 上一様 i.i.d.（厳密和、D-B5）。

    P(min index ≥ a) = ((K−a)/K)^n。順序は経験的に Nash より上に出るのが普通
    （モジュール docstring の D-B5 訂正参照）。
    """
    grid = cfg.action_grid
    K = len(grid)
    n = cfg.n_mm
    total = 0.0
    for a in range(K):
        p_ge_a = ((K - a) / K) ** n
        p_ge_a1 = ((K - a - 1) / K) ** n if a + 1 < K else 0.0
        total += grid[a] * (p_ge_a - p_ge_a1)
    return total
