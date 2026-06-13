"""YH003: Challet & Zhang (1997) Minority Game の再現実装.

N 人のエージェントが二択 (A=+1, B=-1) を繰り返し、少数派が勝つ。
各エージェントは S 個の戦略テーブル (過去 M 期の勝ち履歴 → 予測) を持ち、
仮想スコア (virtual capital) に基づき最良戦略を選択する帰納的学習を行う。

Reference: Challet, D., & Zhang, Y.-C. (1997). "Emergence of cooperation and
organization in an evolutionary game", Physica A, 246, 407-418.

設計メモ:
    - 行動/予測は ±1 エンコード (A=+1, B=-1)。符号演算で戦略更新が綺麗になる。
    - 履歴は直近 M 期の勝ち側を整数 μ ∈ [0, 2^M - 1] で保持する。新しい bit を
      右端に push して mask を取る。strategies[..., mu] 一発で予測が引ける。
    - 戦略テーブル shape は (N, S, 2^M), 値は ±1 (int8)。
    - スコアは (N, S) の int 配列。
    - 同点破り: argmax 対象に [0, 0.5) の一様乱数を足してから argmax を取る。
      スコアが整数のため、0.5 未満の摂動ではスコア差のある組の順位は変わらず、
      同点の組のみランダムに崩れる。
    - Agent / Market クラスは 1 ラン分の読みやすい参照実装 (step 関数に展開)。
      バッチ用 simulate() は N 軸を numpy でベクトル化して 10–100 倍速い。
      両者は同じ RNG 消費順序なので同じ seed で結果が一致する。
"""

from __future__ import annotations

import numpy as np


# --------------------------------------------------------------------------
# クラス版 (参照実装、仕様書通り)
# --------------------------------------------------------------------------


class Agent:
    """1 エージェント分の戦略テーブルとスコア.

    YH004 (GCMG) / YH005 (Speculation Game) への拡張時は本クラスを
    BaseMGAgent として継承する。decide が (action, s_idx) を返す
    契約、update_virtual が (mu, signal) を受ける契約は不変。
    """

    def __init__(self, M: int, S: int, rng: np.random.Generator):
        self.M = M
        self.S = S
        self.strategies = rng.choice([-1, 1], size=(S, 1 << M)).astype(np.int8)
        self.scores = np.zeros(S, dtype=np.int64)
        self.real_gain = 0

    def decide(self, mu: int, rng: np.random.Generator) -> tuple[int, int]:
        """現履歴 mu に対し最良戦略の予測と戦略 index を返す."""
        best = np.flatnonzero(self.scores == self.scores.max())
        s_idx = int(rng.choice(best))
        return int(self.strategies[s_idx, mu]), s_idx

    def update_virtual(self, mu: int, winning_side: int) -> None:
        """勝ち側を予測していた全戦略のスコアを +1 (原論文流儀 a)."""
        self.scores += (self.strategies[:, mu] == winning_side).astype(np.int64)


class Market:
    """少数派判定と履歴 μ の管理."""

    def __init__(self, M: int, rng: np.random.Generator):
        self.M = M
        self.mask = (1 << M) - 1
        self.history = int(rng.integers(0, 1 << M))
        self.attendance_log: list[int] = []
        self.winner_log: list[int] = []

    def get_mu(self) -> int:
        return self.history

    def tick(self, actions: np.ndarray) -> int:
        """actions (±1 配列) を受けて少数派を勝ちとする. 履歴を更新して返す."""
        excess = int(actions.sum())  # = (A 側) - (B 側)
        # 少数派側の符号. excess の符号と逆. excess==0 は N 奇数なら起きない。
        if excess == 0:
            # 偶数 N の事故回避: コインフリップ
            winning_side = 1 if self.history & 1 else -1
        else:
            winning_side = -1 if excess > 0 else 1
        bit = 1 if winning_side == 1 else 0
        self.history = ((self.history << 1) | bit) & self.mask
        N = actions.size
        A_count = (N + excess) // 2
        self.attendance_log.append(A_count)
        self.winner_log.append(winning_side)
        return winning_side


def run_reference(
    N: int, M: int, S: int, T: int, seed: int
) -> tuple[Market, list[Agent]]:
    """仕様書通りのクラス版 1 ラン. 小規模検証用."""
    rng = np.random.default_rng(seed)
    agents = [Agent(M, S, rng) for _ in range(N)]
    market = Market(M, rng)
    actions = np.empty(N, dtype=np.int8)
    for _ in range(T):
        mu = market.get_mu()
        for i, a in enumerate(agents):
            act, _ = a.decide(mu, rng)
            actions[i] = act
        winning = market.tick(actions)
        for i, a in enumerate(agents):
            a.update_virtual(mu, winning)
            if actions[i] == winning:
                a.real_gain += 1
    return market, agents


# --------------------------------------------------------------------------
# ベクトル化版 (本実験の主戦力. スキャン系はこちらを使う)
# --------------------------------------------------------------------------


def simulate(
    N: int,
    M: int,
    S: int,
    T: int,
    seed: int = 42,
    track_scores_at: tuple[int, ...] = (),
    record_attendance: bool = True,
) -> dict:
    """N 軸を numpy でベクトル化した Minority Game シミュレータ.

    Parameters
    ----------
    N : int
        プレイヤー数 (奇数推奨)。
    M : int
        記憶長。戦略テーブルの入力空間サイズは 2**M。
    S : int
        各エージェントの戦略数。
    T : int
        総ステップ数 (burn-in + measure を含む)。
    seed : int
    track_scores_at : tuple[int, ...]
        スコア分布のスナップショットを取る時刻 (0-indexed) のリスト。
    record_attendance : bool
        True なら毎ステップ A 側人数と勝ち側を記録する。

    Returns
    -------
    dict with keys:
        attendance : (T,) int, 各ステップの A 側人数
        winner     : (T,) int, 各ステップの勝ち側 (±1)
        actions    : (T, N) int8, 毎ステップ各エージェントの選択
        real_gain  : (N,) int, 全期間の実利得 (少数派を当てた回数)
        chosen_idx : (T, N) int16, 各ステップ各エージェントが選んだ戦略 index
        scores_snapshots : dict[int, ndarray (N, S)], track_scores_at の時刻分
        final_strategies : (N, S, 2**M) int8
    """
    rng = np.random.default_rng(seed)
    mask = (1 << M) - 1
    # (N, S, 2^M) int8, ±1
    strategies = rng.choice([-1, 1], size=(N, S, 1 << M)).astype(np.int8)
    scores = np.zeros((N, S), dtype=np.int64)
    real_gain = np.zeros(N, dtype=np.int64)
    history = int(rng.integers(0, 1 << M))

    attendance = np.empty(T, dtype=np.int64) if record_attendance else None
    winner = np.empty(T, dtype=np.int8) if record_attendance else None
    actions_log = np.empty((T, N), dtype=np.int8)
    chosen_log = np.empty((T, N), dtype=np.int16)
    scores_snapshots: dict[int, np.ndarray] = {}

    snap_set = set(int(t) for t in track_scores_at)

    for t in range(T):
        if t in snap_set:
            scores_snapshots[t] = scores.copy()
        # 戦略選択 (同点乱数破り)
        perturb = rng.uniform(0.0, 0.5, size=(N, S))
        chosen = np.argmax(scores + perturb, axis=1)  # (N,) in [0, S)
        # 各エージェントの予測 = strategies[i, chosen[i], history]
        preds = strategies[np.arange(N), chosen, history]  # (N,) ±1
        excess = int(preds.sum())
        if excess == 0:
            winning_side = 1 if history & 1 else -1
        else:
            winning_side = -1 if excess > 0 else 1
        # 記録
        if record_attendance:
            attendance[t] = (N + excess) // 2
            winner[t] = winning_side
        actions_log[t] = preds
        chosen_log[t] = chosen
        # 仮想スコア更新 (全戦略同時)
        preds_all = strategies[:, :, history]  # (N, S) ±1
        scores += (preds_all == winning_side).astype(np.int64)
        # 実利得
        real_gain += (preds == winning_side).astype(np.int64)
        # 履歴更新
        bit = 1 if winning_side == 1 else 0
        history = ((history << 1) | bit) & mask

    # 末尾スナップショットも欲しい場合のため、T-1 が含まれているか確認
    if (T - 1) in snap_set and (T - 1) not in scores_snapshots:
        scores_snapshots[T - 1] = scores.copy()

    return {
        "attendance": attendance,
        "winner": winner,
        "actions": actions_log,
        "chosen_idx": chosen_log,
        "real_gain": real_gain,
        "scores_snapshots": scores_snapshots,
        "final_strategies": strategies,
        "final_scores": scores,
    }


def sigma2_over_N(
    N: int, M: int, S: int, T_burn: int, T_measure: int, seed: int
) -> float:
    """単一ランの σ²/N. burn-in を切り落として measure 期の分散/N を返す."""
    res = simulate(N, M, S, T_burn + T_measure, seed=seed, record_attendance=True)
    att = res["attendance"][T_burn:]
    # excess = 2*A - N
    excess = 2.0 * att.astype(np.float64) - N
    return float(excess.var() / N)
