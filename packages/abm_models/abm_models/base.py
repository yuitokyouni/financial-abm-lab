"""共通 ABM モデル protocol。

金融ABMの全モデル (SG / Cont-Bouchaud / Lux-Marchesi / MG / GCMG / ...) は、
seed を受け取り価格系列を含む結果 dict を返す `run` を実装する。これにより
experiments 層は stylized_facts などの core を再実装せず import するだけで済む
(spec 001 O2)。

結果 dict の必須キー:
  - "prices": np.ndarray (float64, 長さ T) — 実価格系列

各モデルはこれに加えてモデル固有の系列 (cognitive_prices, round_trips, ...) を
任意で含めてよい。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class ABMModel(Protocol):
    """price 系列を生成する ABM の最小インターフェース。"""

    #: モデル識別子 (例: "speculation_game")
    name: str

    def run(self, *, seed: int) -> dict[str, Any]:
        """1 本のパスを生成し、結果 dict を返す ("prices" を必ず含む)。"""
        ...


def prices_of(result: dict[str, Any]) -> np.ndarray:
    """結果 dict から価格系列を取り出す (キー契約の単一窓口)。"""
    if "prices" not in result:
        raise KeyError("ABM result dict must contain 'prices'")
    return np.asarray(result["prices"], dtype=np.float64)
