"""Franke-Westerhoff sentiment model — PRISM adapter から昇格。

herding/sentiment による fundamentalist-chartist 切替。PRISM framework メソッドは保持し、
ABMModel protocol 用の run(seed) を追加。結果 dict: {"returns"}。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import FWAdapter, FWParams

__all__ = ["FrankeWesterhoff", "FWAdapter", "FWParams"]


@dataclass(slots=True)
class FrankeWesterhoff:
    n_steps: int = 1000
    params: FWParams | None = None
    name: str = field(default="franke_westerhoff", init=False)

    def _adapter(self) -> FWAdapter:
        p = self.params or FWParams()
        p.n_steps = self.n_steps
        return FWAdapter(params=p)

    def run(self, *, seed: int) -> dict[str, Any]:
        smd = self._adapter().simulate(seed=seed, n_paths=1)
        return {"returns": smd.returns}
