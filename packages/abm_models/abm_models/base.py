"""共通 ABM モデル protocol。

金融ABMの全モデル (SG / Cont-Bouchaud / Lux-Marchesi / Minority Game / GCMG / ...)
は、seed を受け取り結果 dict を返す `run` を実装する。これにより experiments 層は
stylized_facts などの core を再実装せず import するだけで済む (spec 001 O2)。

結果 dict のキーはモデルにより異なる:
  - price 系モデル (SG, Lux-Marchesi): "prices" / "returns"
  - Cont-Bouchaud: "returns" (価格ではなくリターン直接)
  - Minority Game / GCMG: "attendance" (出席数。価格系列を持たない)

共通 protocol は「seed → dict」のみを要求し、系列の取り出しはヘルパで吸収する。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class ABMModel(Protocol):
    """seed から1パスを生成する ABM の最小インターフェース。"""

    #: モデル識別子 (例: "speculation_game")
    name: str

    def run(self, *, seed: int) -> dict[str, Any]:
        """1 本のパスを生成し、結果 dict を返す。"""
        ...


def prices_of(result: dict[str, Any]) -> np.ndarray:
    """価格系列を取り出す。無ければ KeyError。"""
    if "prices" not in result:
        raise KeyError("result has no 'prices' (price-less model?)")
    return np.asarray(result["prices"], dtype=np.float64)


def returns_of(result: dict[str, Any]) -> np.ndarray:
    """リターン系列を取り出す。'returns' が無ければ 'prices' から log-return を導出。"""
    if "returns" in result:
        return np.asarray(result["returns"], dtype=np.float64)
    if "prices" in result:
        p = np.asarray(result["prices"], dtype=np.float64)
        safe = np.where(p > 0, p, np.nan)
        return np.diff(np.log(safe))
    raise KeyError("result has neither 'returns' nor 'prices'")
