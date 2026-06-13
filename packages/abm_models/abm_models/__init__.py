"""abm_models — 金融ABMモデルの正準実装 (一度だけ書く)。

各モデルは `ABMModel` protocol を実装し、experiments 層から import される。
新しいモデルを足すときは market/SF/provenance を再実装せず、ここに1モデル追加して
protocol に準拠させるだけでよい (spec 001 O2)。
"""

from __future__ import annotations

from .base import ABMModel, prices_of
from .sg import SpeculationGame

__all__ = ["ABMModel", "prices_of", "SpeculationGame", "REGISTRY"]

#: モデル名 → クラスのレジストリ (順次追加: cont_bouchaud, lux_marchesi, mg, gcmg, ...)
REGISTRY: dict[str, type] = {
    "speculation_game": SpeculationGame,
}
