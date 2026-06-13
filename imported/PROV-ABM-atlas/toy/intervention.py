"""intervention — B2 観察情報チャネル介入の 4 scheme(spec §7)。

**scaffold のみ。** Week4 実装。masking 本体は `toy.observation.apply_masking` 側に置く予定で、
本モジュールは介入軸(trend/social masking)× scheme × θ の sweep 駆動を担う。
"""

from __future__ import annotations

from dataclasses import dataclass

from toy.observation import InterventionScheme


@dataclass(frozen=True, slots=True)
class InterventionSpec:
    """1 介入条件: 軸 × scheme × 強度 θ(spec §7.2-7.3)。"""

    axis: str  # "trend_masking" | "social_masking"
    scheme: InterventionScheme
    theta: float


def run_intervention(spec: InterventionSpec, *, seed: int) -> None:
    """介入下で 1 run を実行する(Week4 実装)。"""
    raise NotImplementedError("awaiting Week4: 介入 4 scheme × 2 軸(spec §7)")
