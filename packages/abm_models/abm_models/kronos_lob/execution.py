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
    """Parent order を TWAP-like に分割執行する単純 scheduler。

    Parameters
    ----------
    execution_horizon : int
        新 parent が来てから child を出し続ける step 数 (≥ 1)。
        1 で即時 1 発 (= 従来 YH007-2/3 と等価)。
    """

    execution_horizon: int = 1
    _remaining: int = field(default=0, init=False)
    _direction: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.execution_horizon < 1:
            raise ValueError(f"execution_horizon must be >= 1, got {self.execution_horizon}")

    def update_parent(self, action: int) -> None:
        """戦略層の最新方向で schedule を更新。

        - action=0: 残 schedule を破棄 (abstain で執行も止める)
        - 方向転換: 新方向で schedule を再 schedule
        - 同方向: schedule を維持 (残 horizon を `execution_horizon` まで再 charge)
        """
        if action == 0:
            self._remaining = 0
            self._direction = 0
            return
        if action != self._direction:
            self._direction = action
            self._remaining = self.execution_horizon
        else:
            self._remaining = max(self._remaining, self.execution_horizon)

    def next_child(self) -> int:
        """次 child の方向 (1=buy, -1=sell, 0=skip)。1 child 分の枠を消費する。"""
        if self._remaining <= 0:
            return 0
        self._remaining -= 1
        return self._direction

    def reset(self) -> None:
        self._remaining = 0
        self._direction = 0

    @property
    def remaining(self) -> int:
        return self._remaining

    @property
    def direction(self) -> int:
        return self._direction
