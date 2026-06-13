"""Jefferies et al. (2001) Grand-Canonical Minority Game — 正準実装 (YH004 から昇格)。

参加/不参加の自由度を持つ MG 拡張。r_min により MG 極限〜GCMG を連続に跨ぐ。
GCMG では fat-tail (excess kurtosis ≫ 0) が出る。結果 dict: {"active", "attendance", "winner", "actions"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import simulate

__all__ = ["GrandCanonicalMG", "simulate"]


@dataclass(slots=True)
class GrandCanonicalMG:
    N: int = 101
    M: int = 2
    S: int = 2
    T_win: int = 50
    T_total: int = 21000
    r_min_static: float | None = 0.0
    lam: float | None = None
    name: str = field(default="gcmg", init=False)

    def run(self, *, seed: int) -> dict[str, Any]:
        return simulate(
            N=self.N, M=self.M, S=self.S, T_win=self.T_win, T_total=self.T_total,
            r_min_static=self.r_min_static, lam=self.lam, seed=seed,
        )
