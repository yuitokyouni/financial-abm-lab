"""Lux-Marchesi (2000) Volatility Clustering — 正準実装 (YH002 から昇格)。

chartist/fundamentalist 間の遷移が臨界点近傍で volatility clustering と fat-tail を生む。
結果 dict: {"prices", "returns", "z", "x", "params", "zbar"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import Params, simulate

__all__ = ["LuxMarchesi", "Params", "simulate"]


@dataclass(slots=True)
class LuxMarchesi:
    n_integer_steps: int = 20000
    steps_per_unit: int = 100
    n_c_init: int = 50
    params: Params | None = None
    name: str = field(default="lux_marchesi", init=False)

    def run(self, *, seed: int) -> dict[str, Any]:
        return simulate(
            params=self.params,
            n_integer_steps=self.n_integer_steps,
            steps_per_unit=self.steps_per_unit,
            seed=seed,
            n_c_init=self.n_c_init,
            verbose=False,
        )
