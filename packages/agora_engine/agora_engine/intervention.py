"""Intervention — 宣言的介入 (YH010_HANDOFF §7-3)。

時点・対象・種別・パラメータを持ち、テープ (サイドカー JSON) に必ず記録される。
種別は両プロジェクトの既知集合を定数として持つが、拡張は自由 (検証は警告レベル)。
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

KNOWN_TYPES = {
    # YH010 (価格空間)
    "forced_deviation",        # ID-1 強制逸脱
    "prompt_perturbation",     # ID-3a プロンプト摂動
    "composition_change",      # ID-3b 構成異質化
    # YH010-g (ガバナンス空間)
    "advisor_correlation",     # IV-1 助言者数・ポリシー重複度の操作
    "mandate_coarseness",      # IV-2 マンデート不完備度の操作
}


@dataclass
class Intervention:
    t: int                     # 適用時点 (期 / シーズン index)
    type: str                  # 種別 (KNOWN_TYPES 参照)
    target: str                # 対象 (agent_id / manager / market 等)
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in KNOWN_TYPES:
            warnings.warn(f"unknown intervention type: {self.type!r} (known: {sorted(KNOWN_TYPES)})",
                          stacklevel=2)

    def to_dict(self) -> dict:
        return {"t": self.t, "type": self.type, "target": self.target, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, d: dict) -> "Intervention":
        return cls(t=int(d["t"]), type=str(d["type"]), target=str(d.get("target", "")),
                   params=dict(d.get("params", {})))
