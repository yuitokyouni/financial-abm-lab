"""Zero-Intelligence Constrained (Gode & Sunder 1993) — PRISM adapter から昇格。

null baseline モデル。PRISM の intervention framework (calibrate/intervene) はそのまま
保持しつつ、ABMModel protocol 用の run(seed) を追加。結果 dict: {"returns"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import ZIAdapter, ZIParams

__all__ = ["ZeroIntelligence", "ZIAdapter", "ZIParams"]


@dataclass(slots=True)
class ZeroIntelligence:
    n_agents: int = 100
    n_steps: int = 1000
    fundamental_value: float = 100.0
    noise_scale: float = 0.01
    tick_size: float = 0.01
    price_impact: float = 0.01
    name: str = field(default="zero_intelligence", init=False)

    def _adapter(self) -> ZIAdapter:
        return ZIAdapter(params=ZIParams(
            n_agents=self.n_agents, n_steps=self.n_steps,
            fundamental_value=self.fundamental_value, noise_scale=self.noise_scale,
            tick_size=self.tick_size, price_impact=self.price_impact,
        ))

    def run(self, *, seed: int) -> dict[str, Any]:
        smd = self._adapter().simulate(seed=seed, n_paths=1)
        return {"returns": smd.returns}
