"""auto-scaffold for idea #4 (SpeculationGameSelfOrganized).

combination_strategy:
          認知閾値Cを過去|Δp|の中央値または指数移動平均で毎ステップ更新し、自己組織化フィードバックループを形成する。元のSpec
  ulation Gameの戦略テーブルはそのまま使用し、C更新ロジックだけを追加する。

expected_behavior:
          外部パラメータCの初期設定に依存せず、価格変動の統計的性質に応じてCが自律的に調整され、fat‑tails・vol‑clus
  tering・長期記憶がロバストに再現される。

TODO(human): fill in the actual step logic. The scaffold below
instantiates the two base ABMs and returns the first one's result —
replace with the real combination.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from abm_models import REGISTRY


@dataclass(slots=True)
class SpeculationGameSelfOrganized:
    """Auto-scaffolded combo of `speculation_game` and `none`."""
    base_a_params: dict = field(default_factory=dict)
    base_b_params: dict = field(default_factory=dict)
    name: str = field(default="_idea_speculation_game_self_organized", init=False)

    def run(self, *, seed: int) -> dict[str, Any]:
        # TODO(human): combine the two base ABMs here.
        # The scaffold just runs base_a as a placeholder.
        BaseA = REGISTRY["speculation_game"]
        model_a = BaseA(**self.base_a_params)
        return model_a.run(seed=seed)
