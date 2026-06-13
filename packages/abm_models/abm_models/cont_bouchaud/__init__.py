"""Cont-Bouchaud (1997) Percolation — 正準実装 (YH001 から昇格)。

クラスタ (= herd) のサイズ分布が冪則になり、return が fat-tail を持つ。
結果 dict: {"returns", "cluster_sizes"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import simulate

__all__ = ["ContBouchaud", "simulate"]


@dataclass(slots=True)
class ContBouchaud:
    N: int = 10000
    c: float = 0.9
    a: float = 0.01
    lam: float = 1.0
    T: int = 50000
    report_every: int = 5000
    name: str = field(default="cont_bouchaud", init=False)

    def run(self, *, seed: int) -> dict[str, Any]:
        return simulate(N=self.N, c=self.c, a=self.a, lam=self.lam, T=self.T,
                        seed=seed, report_every=self.report_every)
