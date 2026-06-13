"""Chiarella-Iori order-book model — PRISM adapter から昇格。

fundamentalist/chartist/noise を order-book 上で混合。PRISM framework メソッドは保持し、
ABMModel protocol 用の run(seed) を追加。結果 dict: {"returns"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import CIAdapter, CIParams

__all__ = ["ChiarellaIori", "CIAdapter", "CIParams"]


@dataclass(slots=True)
class ChiarellaIori:
    n_steps: int = 1000
    params: CIParams | None = None
    name: str = field(default="chiarella_iori", init=False)

    def _adapter(self) -> CIAdapter:
        p = self.params or CIParams()
        p.n_steps = self.n_steps
        return CIAdapter(params=p)

    def run(self, *, seed: int) -> dict[str, Any]:
        smd = self._adapter().simulate(seed=seed, n_paths=1)
        return {"returns": smd.returns}
