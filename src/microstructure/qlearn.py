"""表形式学習 — Policy 群と train() ループ（research D-B1/D-B2/D-B6）。

Policy protocol（duck typing）:
  act(state, t) -> int / update(s, a, r, s_next, a_next) -> None /
  greedy(state) -> int / frozen() -> Policy
SARSA は a_next（次期に実際に選択された action）で更新するため、train() は
更新を 1 期遅延させる（t 期の遷移は t+1 期の action 選択後に flush。
最終期の遷移 1 件は未 flush——収束判定には無視できる）。

状態 encode: 直近 memory 期の action profile（n_mm × memory 桁）の混基数整数。
memory=0 → 常に状態 0（myopic 縮退）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .env import MarketEnv, derive_rngs
from .learnconfig import LearnConfig

_MEASURE_BURN_IN = 100  # frozen policy の決定論動学が limit cycle に入るまでの捨て期間


def encode(history: tuple[tuple[int, ...], ...], n_actions: int) -> int:
    """直近 memory 期の action profile 列 → 混基数整数（新しい期が下位桁）。"""
    s = 0
    for profile in history:
        for a in profile:
            s = s * n_actions + a
    return s


class _Tabular:
    def __init__(self, cfg: LearnConfig, seed: int) -> None:
        self.q = np.full((cfg.n_states, cfg.n_actions), cfg.q_init)
        self.stream = np.random.default_rng(seed)
        self.lr = cfg.lr
        self.gamma = cfg.gamma
        self.beta = cfg.eps_beta
        self.n_actions = cfg.n_actions

    def act(self, state: int, t: int) -> int:
        if self.stream.random() < math.exp(-self.beta * t):
            return int(self.stream.integers(self.n_actions))
        return int(np.argmax(self.q[state]))

    def greedy(self, state: int) -> int:
        return int(np.argmax(self.q[state]))

    def frozen(self) -> "FixedPolicy":
        return FixedPolicy(np.argmax(self.q, axis=1))


class QLearner(_Tabular):
    def update(self, s: int, a: int, r: float, s_next: int, a_next: int) -> None:
        target = r + self.gamma * float(np.max(self.q[s_next]))
        self.q[s, a] += self.lr * (target - self.q[s, a])


class SARSA(_Tabular):
    def update(self, s: int, a: int, r: float, s_next: int, a_next: int) -> None:
        target = r + self.gamma * float(self.q[s_next, a_next])
        self.q[s, a] += self.lr * (target - self.q[s, a])


class ZIPolicy:
    """知能ゼロ: 一様ランダム action（ZI 参照点の測定用）。frozen でもランダムのまま。"""

    def __init__(self, cfg: LearnConfig, seed: int) -> None:
        self.stream = np.random.default_rng(seed)
        self.n_actions = cfg.n_actions

    def act(self, state: int, t: int) -> int:
        return int(self.stream.integers(self.n_actions))

    def update(self, s, a, r, s_next, a_next) -> None:
        pass

    def greedy(self, state: int) -> int:
        return int(self.stream.integers(self.n_actions))

    def frozen(self) -> "ZIPolicy":
        return self


class FixedPolicy:
    """状態→action の固定表。gate 検証の合成 policy・frozen 共通の器。"""

    def __init__(self, table: np.ndarray) -> None:
        self.table = np.asarray(table, dtype=np.int64)

    def act(self, state: int, t: int) -> int:
        return int(self.table[state])

    def update(self, s, a, r, s_next, a_next) -> None:
        pass

    def greedy(self, state: int) -> int:
        return int(self.table[state])

    def frozen(self) -> "FixedPolicy":
        return self


def make_policies(cfg: LearnConfig, agent_seeds: list[int]) -> list:
    if cfg.algo == "qlearning":
        return [QLearner(cfg, s) for s in agent_seeds]
    if cfg.algo == "sarsa":
        return [SARSA(cfg, s) for s in agent_seeds]
    if cfg.algo == "zi":
        return [ZIPolicy(cfg, s) for s in agent_seeds]
    raise ValueError(f"algo={cfg.algo} は make_policies 対象外（fixed はテストで直接構築）")


@dataclass
class TrainResult:
    policies: list
    converged: bool
    periods_run: int
    policy_stable_at: int | None


def initial_history(cfg: LearnConfig) -> tuple[tuple[int, ...], ...]:
    """決定論の初期 state: 全員 mid-grid の profile × memory 期（D-B12 注記）。"""
    mid = cfg.n_actions // 2
    return ((mid,) * cfg.n_mm,) * cfg.memory


def run_greedy(env: MarketEnv, policies: list, cfg: LearnConfig, periods: int,
               history: tuple | None = None):
    """frozen/greedy policy で periods 期回す共通ループ（measure が使用）。

    returns (profiles, rewards_matrix, infos)
    """
    history = initial_history(cfg) if history is None else history
    profiles: list[tuple[int, ...]] = []
    rewards_all = np.zeros((periods, cfg.n_mm))
    infos: list[dict] = []
    state = encode(history, cfg.n_actions)
    for t in range(periods):
        actions = tuple(p.greedy(state) for p in policies)
        rewards, info = env.step(actions)
        profiles.append(actions)
        rewards_all[t] = rewards
        infos.append(info)
        if cfg.memory > 0:
            history = history[1:] + (actions,) if cfg.memory > 1 else (actions,)
            state = encode(history, cfg.n_actions)
    return profiles, rewards_all, infos


def train(cfg: LearnConfig) -> TrainResult:
    """n 体同時学習。収束 = 全 agent の greedy policy が stable_window 期連続不変（D-B6）。

    更新済み状態の greedy のみ変化しうるため、policy 安定は「直前期に更新した状態の
    argmax が変わらない」ことの streak で incremental に判定する（毎期 O(n_actions)）。
    """
    seeds = derive_rngs(cfg)
    env = MarketEnv(cfg, seeds["env"])
    policies = make_policies(cfg, seeds["agents"])
    if cfg.algo == "zi":
        return TrainResult(policies, True, 0, 0)

    tables = [np.argmax(p.q, axis=1) for p in policies]
    history = initial_history(cfg)
    state = encode(history, cfg.n_actions)
    prev: tuple[int, tuple[int, ...], np.ndarray] | None = None
    streak = 0
    stable_at: int | None = None
    converged = False
    periods = 0
    for t in range(cfg.t_max):
        actions = tuple(p.act(state, t) for p in policies)
        if prev is not None:
            s0, a0, r0 = prev
            changed = False
            for i, p in enumerate(policies):
                p.update(s0, a0[i], float(r0[i]), state, actions[i])
                g = int(np.argmax(p.q[s0]))
                if g != tables[i][s0]:
                    tables[i][s0] = g
                    changed = True
            streak = 0 if changed else streak + 1
            if streak >= cfg.stable_window:
                converged = True
                stable_at = t
                periods = t + 1
                break
        rewards, _ = env.step(actions)
        prev = (state, actions, rewards)
        if cfg.memory > 0:
            history = history[1:] + (actions,) if cfg.memory > 1 else (actions,)
            state = encode(history, cfg.n_actions)
        periods = t + 1
    return TrainResult(policies, converged, periods, stable_at)
