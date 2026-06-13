"""YH004: Grand Canonical Minority Game (Jefferies et al. 2001) の再現実装.

論文: Jefferies, P., Hart, M. L., Hui, P. M., & Johnson, N. F. (2001).
"From market games to real-world markets", Eur. Phys. J. B, 20, 493-501.
arXiv: cond-mat/0008387

YH003 の MG を次の 2 点で拡張する:
  1. Signed scoring + rolling window T (§2.2, p.4)
     - 戦略スコア: +1 正解 / -1 誤答, 直近 T 期のみ集計 ("sunken losses")
     - スコア範囲 rS ∈ [-T, T]
  2. 閾値 r_min による参加選択 (§2.2, p.4-5)
     - max(rS) > r_min のときのみ取引. そうでなければ action = 0 (abstain).
     - r_min は生の signed score 単位, 範囲 [-T, T] (論文 Figure 1 x 軸)
     - 静的 (r_min 固定) と動的 (r_min = max[0, λσ(r_i) - r_i]) の 2 モード

YH003 との極限同値: T ≥ T_total かつ r_min < -T なら、argmax ランキングは
MG と一致 (signed と unsigned は affine 関係で順位不変)。

設計メモ:
  - 戦略テーブル strategies: (N, S, 2^M) int8 ±1 (YH003 と同じ)
  - スコア scores: (N, S) int32, 範囲 [-T, T]
  - score_buf: (T_win, N, S) int8 in ±1. ring buffer で T 期保持
  - personal_buf: (T_win, N) int8 in {-1, 0, +1}. 動的 r_min / 個人成績用
  - 同点破り: argmax 前に [0, 0.5) 一様乱数加算 (YH003 と同じ)
"""

from __future__ import annotations

import numpy as np


# --------------------------------------------------------------------------
# クラス版 (参照実装. 共通基盤 BaseMGAgent を書いて GCMGAgent で拡張)
# --------------------------------------------------------------------------


class BaseMGAgent:
    """YH003-YH005 共通の土台. 5 要素 (M, S, strategies, scores, decide, update_virtual).

    YH003 Agent との差異: scores は signed (±1 per step) + rolling window T。
    """

    def __init__(self, M: int, S: int, T: int, rng: np.random.Generator):
        self.M = M
        self.S = S
        self.T = T  # sunken-losses window
        self.strategies = rng.choice([-1, 1], size=(S, 1 << M)).astype(np.int8)
        self.scores = np.zeros(S, dtype=np.int32)  # signed, range [-T, +T]
        self._score_buf = np.zeros((T, S), dtype=np.int8)
        self._buf_idx = 0

    def decide(self, mu: int, rng: np.random.Generator) -> tuple[int, int]:
        best = np.flatnonzero(self.scores == self.scores.max())
        s_idx = int(rng.choice(best))
        return int(self.strategies[s_idx, mu]), s_idx

    def update_virtual(self, mu: int, signal: int) -> None:
        """Signed score update. signal ∈ ±1. 正解 +1, 誤答 -1."""
        increment = (self.strategies[:, mu] * signal).astype(np.int8)
        self.scores -= self._score_buf[self._buf_idx]
        self._score_buf[self._buf_idx] = increment
        self.scores += increment
        self._buf_idx = (self._buf_idx + 1) % self.T


class GCMGAgent(BaseMGAgent):
    """Grand-Canonical MG エージェント (Jefferies et al. 2001).

    参加条件: max(rS) > r_min のとき参加。それ以外は action = 0 (abstain)。

    Parameters
    ----------
    r_min_static : float | None
        静的 r_min。raw signed score 単位 ∈ [-T, T]。None なら動的モード。
    lam : float | None
        動的モードでのリスク回避係数 λ。動的時のみ必須。
    """

    def __init__(
        self, M: int, S: int, T: int, rng: np.random.Generator,
        r_min_static: float | None = None, lam: float | None = None,
    ):
        super().__init__(M, S, T, rng)
        self.r_min_static = r_min_static
        self.lam = lam
        self._personal_buf = np.zeros(T, dtype=np.int8)
        self._pbuf_idx = 0

    @property
    def r_i(self) -> int:
        return int(self._personal_buf.sum())

    def current_r_min(self) -> float:
        if self.r_min_static is not None:
            return float(self.r_min_static)
        sigma = float(self._personal_buf.std())
        return max(0.0, -(self.r_i - self.lam * sigma))

    def decide(self, mu: int, rng: np.random.Generator) -> tuple[int, int]:
        best = np.flatnonzero(self.scores == self.scores.max())
        s_idx = int(rng.choice(best))
        if float(self.scores[s_idx]) > self.current_r_min():
            return int(self.strategies[s_idx, mu]), s_idx
        return 0, s_idx

    def update_personal(self, action: int, signal: int) -> None:
        """個人スコア更新. action*signal ∈ {-1, 0, +1}."""
        contrib = np.int8(action * signal)
        self._personal_buf[self._pbuf_idx] = contrib
        self._pbuf_idx = (self._pbuf_idx + 1) % self.T


class GCMGMarket:
    """少数派判定と履歴 μ の管理. 非参加 (action=0) に対応."""

    def __init__(self, M: int, rng: np.random.Generator):
        self.M = M
        self.mask = (1 << M) - 1
        self.history = int(rng.integers(0, 1 << M))
        self.rng = rng
        self.attendance_log: list[int] = []
        self.active_log: list[int] = []
        self.winner_log: list[int] = []

    def get_mu(self) -> int:
        return self.history

    def tick(self, actions: np.ndarray) -> int:
        excess = int(actions.sum())
        n_active = int((actions != 0).sum())
        if n_active == 0:
            winning_side = 1 if self.rng.random() > 0.5 else -1
        elif excess == 0:
            winning_side = 1 if self.history & 1 else -1
        else:
            winning_side = -1 if excess > 0 else 1
        bit = 1 if winning_side == 1 else 0
        self.history = ((self.history << 1) | bit) & self.mask
        N = actions.size
        A_count = int((actions == 1).sum())
        self.attendance_log.append(A_count)
        self.active_log.append(n_active)
        self.winner_log.append(winning_side)
        return winning_side


# --------------------------------------------------------------------------
# ベクトル化版 (本実験の主戦力)
# --------------------------------------------------------------------------


def simulate(
    N: int,
    M: int,
    S: int,
    T_win: int,
    T_total: int,
    r_min_static: float | None = None,
    lam: float | None = None,
    seed: int = 42,
) -> dict:
    """GCMG シミュレータ (N 軸ベクトル化).

    Parameters
    ----------
    N, M, S : int
        プレイヤー数 (奇数推奨), 記憶長, 戦略数。
    T_win : int
        "sunken losses" 窓幅。スコアはこの期間で rolling 集計。
    T_total : int
        総ステップ数。
    r_min_static : float | None
        静的 r_min。raw signed score ∈ [-T_win, T_win]。None なら動的。
    lam : float | None
        動的モードのリスク回避係数。動的時のみ使用。
    seed : int

    Returns
    -------
    dict:
        attendance : (T_total,) 買い方側 (action=+1) 人数
        active     : (T_total,) 非 abstain 人数
        winner     : (T_total,) 勝ち側 ±1
        excess     : (T_total,) actions.sum()
        real_gain  : (N,) 個人成績累計 (正解数)
        personal_final : (N,) 個人 r_i (rolling window 最終値)
    """
    assert r_min_static is not None or lam is not None, (
        "r_min_static か lam のいずれかを指定する必要があります"
    )
    rng = np.random.default_rng(seed)
    mask = (1 << M) - 1

    strategies = rng.choice([-1, 1], size=(N, S, 1 << M)).astype(np.int8)
    scores = np.zeros((N, S), dtype=np.int32)
    score_buf = np.zeros((T_win, N, S), dtype=np.int8)
    personal_buf = np.zeros((T_win, N), dtype=np.int8)
    buf_idx = 0

    history = int(rng.integers(0, 1 << M))
    real_gain = np.zeros(N, dtype=np.int64)

    attendance = np.zeros(T_total, dtype=np.int32)
    active_log = np.zeros(T_total, dtype=np.int32)
    winner_log = np.zeros(T_total, dtype=np.int8)
    excess_log = np.zeros(T_total, dtype=np.int32)

    for t in range(T_total):
        perturb = rng.uniform(0.0, 0.5, size=(N, S))
        chosen = np.argmax(scores + perturb, axis=1)
        best_scores = scores[np.arange(N), chosen].astype(np.float64)

        if r_min_static is not None:
            r_min_vec = np.full(N, float(r_min_static))
        else:
            r_i_vec = personal_buf.sum(axis=0).astype(np.float64)
            mean_r = r_i_vec / T_win
            var_r = ((personal_buf.astype(np.float64)) ** 2).sum(axis=0) / T_win - mean_r ** 2
            var_r = np.maximum(var_r, 0.0)
            sigma_r = np.sqrt(var_r)
            r_min_vec = np.maximum(0.0, -(r_i_vec - lam * sigma_r))

        preds = strategies[np.arange(N), chosen, history]
        active_mask = best_scores > r_min_vec
        actions = np.where(active_mask, preds, 0).astype(np.int8)

        excess = int(actions.sum())
        n_active = int(active_mask.sum())
        if n_active == 0:
            winning_side = 1 if rng.random() > 0.5 else -1
        elif excess == 0:
            winning_side = 1 if history & 1 else -1
        else:
            winning_side = -1 if excess > 0 else 1

        attendance[t] = int((actions == 1).sum())
        active_log[t] = n_active
        winner_log[t] = winning_side
        excess_log[t] = excess

        preds_all = strategies[:, :, history]
        increment = (preds_all.astype(np.int8) * winning_side).astype(np.int8)
        scores -= score_buf[buf_idx].astype(np.int32)
        score_buf[buf_idx] = increment
        scores += increment.astype(np.int32)

        personal_incr = (actions * winning_side).astype(np.int8)
        personal_buf[buf_idx] = personal_incr
        real_gain += (personal_incr == 1).astype(np.int64)

        buf_idx = (buf_idx + 1) % T_win
        bit = 1 if winning_side == 1 else 0
        history = ((history << 1) | bit) & mask

    return {
        "attendance": attendance,
        "active": active_log,
        "winner": winner_log,
        "excess": excess_log,
        "real_gain": real_gain,
        "personal_final": personal_buf.sum(axis=0),
    }


# --------------------------------------------------------------------------
# 論文 p.5 の二項近似: ⟨N_active⟩ ≈ N (1 - P[rS < r_min]^s)
# --------------------------------------------------------------------------


def binomial_theory(
    N: int, S: int, T_win: int, r_min_grid: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """独立 binomial walk 近似による ⟨N_active⟩ と σ[N_active].

    論文 p.5:
        rS ~ 2 Bin(T, 1/2) - T
        ⟨N_active⟩ ≈ N (1 - P[rS < r_min]^s)
        Var[N_active] ≈ N (1 - P^s) P^s

    dilute 相 (T ≫ 2^M) で近似が良いと論文自身が注意している。
    """
    from scipy.stats import binom
    # P[rS < r_min] = P[2X - T < r_min] = P[X < (r_min + T)/2]
    # X ∈ Z なので P[X < x] = binom.cdf(ceil(x)-1, T, 0.5).
    P = np.empty_like(r_min_grid, dtype=np.float64)
    for i, rm in enumerate(r_min_grid):
        k_thresh = np.ceil((rm + T_win) / 2.0) - 1
        if k_thresh < 0:
            P[i] = 0.0
        elif k_thresh >= T_win:
            P[i] = 1.0
        else:
            P[i] = float(binom.cdf(int(k_thresh), T_win, 0.5))
    P_s = P ** S
    mean_active = N * (1.0 - P_s)
    var_active = N * (1.0 - P_s) * P_s
    return mean_active, np.sqrt(var_active)
