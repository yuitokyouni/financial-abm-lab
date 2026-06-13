"""toy.agents — 機構モデル。

`base.Agent` を介して全 agent は `ctx.*` 経由でのみ観測・乱数・発注を行う(honest 性確保)。
`trend.TrendAgent` = Model T、`herd.HerdAgent` = Model H(spec §3.2)。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from toy.agents.base import Agent
from toy.agents.herd import build_herd_population
from toy.agents.trend import build_trend_population

_PopulationBuilder = Callable[[int, np.random.Generator], Sequence[Agent]]

# config の agents.model 値 → 集団 builder。
_BUILDERS: dict[str, _PopulationBuilder] = {
    "T": build_trend_population,
    "H": build_herd_population,
}


def make_population(model: str, n: int, rng: np.random.Generator) -> list[Agent]:
    """機構ラベル('T' / 'H')からヘテロ集団を生成する。"""
    try:
        builder = _BUILDERS[model]
    except KeyError as exc:
        raise ValueError(
            f"unknown agent model {model!r}; expected one of {sorted(_BUILDERS)}"
        ) from exc
    return list(builder(n, rng))


__all__ = ["Agent", "build_herd_population", "build_trend_population", "make_population"]
