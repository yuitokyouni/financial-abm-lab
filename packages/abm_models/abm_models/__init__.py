"""abm_models — 金融ABMモデルの正準実装 (一度だけ書く)。

各モデルは `ABMModel` protocol を実装し、experiments 層から import される。
新しいモデルを足すときは market/SF/provenance を再実装せず、ここに1モデル追加して
protocol に準拠させるだけでよい (spec 001 O2)。

2系統:
  - speculation-game-info 由来 (論文忠実・findings parity): SG/CB/LM/MG/GCMG
  - PRISM intervention framework 由来 (FW系): CI/ZI/FW (calibrate/intervene を保持しつつ
    run(seed) で ABMModel にも準拠)
"""

from __future__ import annotations

from .base import ABMModel, prices_of, returns_of
from .chiarella_iori import ChiarellaIori
from .cont_bouchaud import ContBouchaud
from .franke_westerhoff import FrankeWesterhoff
from .gcmg import GrandCanonicalMG
from .lux_marchesi import LuxMarchesi
from .minority_game import MinorityGame
from .sg import SpeculationGame
from .zero_intelligence import ZeroIntelligence

__all__ = [
    "ABMModel",
    "prices_of",
    "returns_of",
    "SpeculationGame",
    "ContBouchaud",
    "LuxMarchesi",
    "MinorityGame",
    "GrandCanonicalMG",
    "ChiarellaIori",
    "ZeroIntelligence",
    "FrankeWesterhoff",
    "REGISTRY",
]

#: モデル名 → クラスのレジストリ
REGISTRY: dict[str, type] = {
    "speculation_game": SpeculationGame,
    "cont_bouchaud": ContBouchaud,
    "lux_marchesi": LuxMarchesi,
    "minority_game": MinorityGame,
    "gcmg": GrandCanonicalMG,
    "chiarella_iori": ChiarellaIori,
    "zero_intelligence": ZeroIntelligence,
    "franke_westerhoff": FrankeWesterhoff,
}
