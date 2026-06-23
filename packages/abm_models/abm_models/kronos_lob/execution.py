"""YH007-4: 執行層 (機構 2 = order flow の long-memory) — parent → child TWAP 分割。

spec 002 §3 3層分離 / §4.5 軸1 / §9.4 (refs_execution_algorithms.md):
戦略層が出す parent order (方向, サイズ) を執行層が child schedule に分けて LOB に流す。
ここでは最も単純な TWAP-like 分割: parent 1 つ → N step に渡り volume を均等に出す。

Bouchaud 仮説 (機構 2): 大口 parent の分割執行 → 符号付きフロー自己相関 → vol clustering。
ablation: execution_horizon ∈ {1, 5, 10, ...} を振って vol_acf がどう動くかを観察。

実装上の意味論:
  - update_parent(action) は毎 step に呼ばれる「戦略の最新方向」。同方向の継続なら schedule を
    "再 charge" (= execution_horizon を維持)、方向転換なら schedule を上書き、action=0 なら破棄。
  - next_child() は 1 child の方向を返す。返値 0 はその step に新規 order を出さない。
  - execution_horizon=1 のとき、scheduler は「毎 step の action をそのまま 1 child として返す」
    完全な pass-through (= YH007-2/3 と等価)。これで execution layer の有無で挙動を切り分けられる。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChildOrderScheduler:
    """Parent order を TWAP-like に分割執行する scheduler。

    semantics: **parent は新 bar (= signal 更新タイミング) でのみ発生**。同 bar 内で
    `update_parent(action, bar_index)` を再度呼んでも何もしない (bar 単位で 1 parent)。
    parent 1 つにつき最大 `execution_horizon` 個の child を **次以降の step** で出していく。
    execution_horizon=1 のとき bar 切替時に 1 child だけ出して、bar 内残りは abstain。
    >1 で複数 step に child を分散 (TWAP-like)。

    Parameters
    ----------
    execution_horizon : int
        1 parent あたりの child 数の上限 (≥ 1)。bar_size と組み合わせて
        bar 内のどれだけの step で child を出すかを決める。
    """

    execution_horizon: int = 1
    _remaining: int = field(default=0, init=False)
    _direction: int = field(default=0, init=False)
    _last_parent_bar: int = field(default=-1, init=False)

    def __post_init__(self) -> None:
        if self.execution_horizon < 1:
            raise ValueError(f"execution_horizon must be >= 1, got {self.execution_horizon}")

    def update_parent(self, action: int, bar_index: int) -> None:
        """新 bar のタイミングで parent を投入。同 bar 内の再呼び出しは無視。

        - action=0: schedule を破棄 (abstain)
        - 方向転換 or 同方向の新 parent: schedule を再 charge
        """
        if bar_index == self._last_parent_bar:
            return  # 同 bar 内では parent を新規発生させない
        self._last_parent_bar = bar_index
        if action == 0:
            self._remaining = 0
            self._direction = 0
            return
        self._direction = action
        self._remaining = self.execution_horizon

    def next_child(self) -> int:
        """次 child の方向 (1=buy, -1=sell, 0=skip)。1 child 分の枠を消費する。"""
        if self._remaining <= 0:
            return 0
        self._remaining -= 1
        return self._direction

    def reset(self) -> None:
        self._remaining = 0
        self._direction = 0
        self._last_parent_bar = -1

    @property
    def remaining(self) -> int:
        return self._remaining

    @property
    def direction(self) -> int:
        return self._direction
