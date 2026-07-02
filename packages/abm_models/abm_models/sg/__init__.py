"""Speculation Game (Katahira-Chen 2019) — 正準実装。

speculation-game-info/YH005 の論文忠実実装を core に昇格したもの。
`run_reference` (per-agent 参照) と `simulate` (ベクトル化, bit-parity) の2系統を持ち、
両者は §7 の RNG 消費順を共有する。

注意: PRISM / PROV-ABM-atlas の `adapters/sg.py` は名称が "SG" だが、実体は
fundamentalist/chartist/noise + softmax switching の別モデル (Franke-Westerhoff 系)
であり、本 Speculation Game とは別物。正準 SG は本実装を指す (ADR 0001 参照)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .reference import run_reference
from .vectorized import simulate

__all__ = ["SpeculationGame", "run_reference", "simulate", "BASELINE_PARAMS"]

#: YH005 §8.4 ベースライン (parity 基準)
BASELINE_PARAMS: dict[str, Any] = dict(N=1000, M=5, S=2, T=20000, B=9, C=3.0, p0=100.0)


@dataclass(slots=True)
class SpeculationGame:
    """Speculation Game モデル (ABMModel protocol 実装)。

    パラメータを保持し、`run(seed=...)` で 1 本のパスを返す。backend で参照実装と
    ベクトル化実装を切り替える (既定: vectorized)。
    """

    N: int = 1000
    M: int = 5
    S: int = 2
    T: int = 20000
    B: int = 9
    C: float = 3.0
    p0: float = 100.0
    history_mode: str = "endogenous"        # 'endogenous' | 'exogenous' (Null A)
    decision_mode: str = "strategy"          # 'strategy'   | 'random'   (Null B)
    random_open_prob: float = 0.5
    order_size_buckets: tuple[int, int] = (50, 100)
    backend: str = "vectorized"              # 'vectorized' | 'reference'

    name: str = field(default="speculation_game", init=False)

    def _params(self) -> dict[str, Any]:
        return dict(
            N=self.N, M=self.M, S=self.S, T=self.T, B=self.B, C=self.C, p0=self.p0,
            history_mode=self.history_mode, decision_mode=self.decision_mode,
            random_open_prob=self.random_open_prob,
            order_size_buckets=self.order_size_buckets,
        )

    def run(self, *, seed: int) -> dict[str, Any]:
        # minor #5: 未知の backend 文字列を無検証で reference に silent fallback すると、
        # 例えば "vectorised" の typo で意図せず低速な参照実装が走っても気づけない。
        # 明示的に検証する。
        if self.backend == "vectorized":
            fn = simulate
        elif self.backend == "reference":
            fn = run_reference
        else:
            raise ValueError(
                f"unknown backend {self.backend!r}; expected 'vectorized' or 'reference'"
            )
        return fn(seed=seed, **self._params())
