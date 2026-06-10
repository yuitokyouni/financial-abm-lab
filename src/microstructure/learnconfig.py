"""LearnConfig — 実験B の不変 run パラメータ（specs/002 data-model / contracts §1）。

市場 primitives は 001 SimConfig と同名・同義（dt スケーリング、α、noise_rate、fee）。
学習・収束・IR gate の既定値は research D-B2/D-B6/D-B7 で固定した数値。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace as _dc_replace
from typing import Literal

from .anchors import gm_break_even

# 表形式が成立する状態数の上限（超えたら設計を見直す、黙って回さない）
_MAX_STATES = 200_000


@dataclass(frozen=True)
class LearnConfig:
    # 市場（001 SimConfig と同語彙）
    dt: float = 1e-2
    lambda_jump: float = 5.0
    jump_size: float = 1.0
    alpha: float = 0.3
    noise_rate: float = 1.0
    fee: float = 0.0
    sigma: float = 0.0          # B baseline は pure-jump（A 側 ① 完了まで diffusion 不可）
    initial_price: float = 100.0
    # 機構
    mechanism: Literal["continuous", "batch"] = "continuous"
    batch_interval: int = 1
    staleness: Literal["committed", "revisable"] = "committed"
    # 集団
    n_mm: int = 2
    memory: int = 1
    # action grid（half-spread、D-B2: [grid_lo_mult·h*_cont, grid_hi_mult·J]）
    n_actions: int = 15
    grid_lo_mult: float = 0.5
    grid_hi_mult: float = 2.0
    # 学習（D-B6）
    algo: Literal["qlearning", "sarsa", "zi", "fixed"] = "qlearning"
    lr: float = 0.15
    gamma: float = 0.95
    eps_beta: float = 4.6e-6
    q_init: float = 0.0
    # 収束・測定（D-B6）
    stable_window: int = 100_000
    t_max: int = 2_000_000
    measure_periods: int = 10_000
    # IR gate（D-B7）
    ir_pre: int = 100
    ir_horizon: int = 200
    ir_punish_lag: int = 10
    ir_restore_tail: int = 50
    markup_floor: float = 0.05
    # robustness
    noise_reserve: float = math.inf   # R: noise の留保 half-spread（inf = inelastic baseline, D-B11）
    tie_rule: Literal["split", "rotate"] = "split"
    # 実行
    seed: int = 0

    def __post_init__(self) -> None:
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be in [0,1]")
        if self.dt <= 0:
            raise ValueError("dt must be > 0")
        if not (0.0 <= self.lambda_jump * self.dt <= 1.0):
            raise ValueError("lambda_jump*dt must be in [0,1] (refine dt)")
        if not (0.0 <= self.noise_rate * self.dt <= 1.0):
            raise ValueError("noise_rate*dt must be in [0,1] (refine dt)")
        if self.sigma != 0.0:
            raise ValueError("B baseline is pure-jump: sigma must be 0 until A-side ① closes "
                             "(finding 0001)")
        if self.batch_interval < 1:
            raise ValueError("batch_interval >= 1")
        if self.mechanism == "continuous" and self.batch_interval != 1:
            raise ValueError("continuous requires batch_interval == 1")
        if self.n_mm < 1:
            raise ValueError("n_mm >= 1 (1 is sanity-only)")
        if self.memory < 0:
            raise ValueError("memory >= 0")
        if self.n_actions < 2:
            raise ValueError("n_actions >= 2")
        if self.n_states > _MAX_STATES:
            raise ValueError(f"state space {self.n_states} exceeds tabular limit {_MAX_STATES} "
                             "(reduce n_actions/n_mm/memory)")
        if self.noise_reserve <= 0:
            raise ValueError("noise_reserve > 0 (use math.inf for inelastic)")
        grid = self.action_grid
        if not all(a < b for a, b in zip(grid, grid[1:])):
            raise ValueError("action_grid must be strictly increasing "
                             "(check grid_lo_mult·h* < grid_hi_mult·J)")

    @property
    def h_star_cont(self) -> float:
        """連続 GM break-even（grid の下端基準・markup 文脈の解析参照点）。"""
        return gm_break_even(self.lambda_jump, self.jump_size, self.alpha, self.noise_rate)

    @property
    def action_grid(self) -> tuple[float, ...]:
        lo = self.grid_lo_mult * self.h_star_cont
        hi = self.grid_hi_mult * self.jump_size
        step = (hi - lo) / (self.n_actions - 1)
        return tuple(lo + step * i for i in range(self.n_actions))

    @property
    def n_states(self) -> int:
        """混基数 encode の状態数 = n_actions^(n_mm·memory)（memory=0 → 1 状態）。"""
        return self.n_actions ** (self.n_mm * self.memory)

    @property
    def period_steps(self) -> int:
        """学習 1 期の市場 step 数（continuous=1、batch=N。D-B3）。"""
        return self.batch_interval if self.mechanism == "batch" else 1

    def replace(self, **kw) -> "LearnConfig":
        return _dc_replace(self, **kw)
