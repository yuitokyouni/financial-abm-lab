"""Challet-Zhang (1997) Minority Game — 正準実装 (YH003 から昇格)。

少数派に付くゲーム。σ²/N が α=2^M/N に対し U 字を描く。価格系列は持たず
出席数 (attendance) が主出力。結果 dict: {"attendance", "winner", "actions", "real_gain", ...}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import simulate

__all__ = ["MinorityGame", "simulate"]


@dataclass(slots=True)
class MinorityGame:
    N: int = 101
    M: int = 6
    S: int = 2
    T: int = 10000
    record_attendance: bool = True
    name: str = field(default="minority_game", init=False)

    def run(self, *, seed: int) -> dict[str, Any]:
        return simulate(N=self.N, M=self.M, S=self.S, T=self.T,
                        seed=seed, record_attendance=self.record_attendance)
