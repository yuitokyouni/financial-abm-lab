"""calibration — SF-等価 calibration(spec §5)。

**scaffold のみ。** 留保 1(SF calibration の anchor:相互等価性で固定するか実データ近接か)が
Yuito confirm 待ちのため、grid search / BO の本体は実装しない。protocol/interface だけ置く。
確定後に v0.2 を切ってから Stage 1-3 を実装する(CLAUDE.md「未解決」「進行ルール」)。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CalibratedPair:
    """SF-等価点 (T*, H*)。Stage 3 の等価性検証を通った組(留保 1 確定後に実体化)。"""

    trend_params: dict[str, float]
    herd_params: dict[str, float]


def calibrate_sf_equivalent(*, seed: int) -> CalibratedPair:
    """両モデルが SF battery 上で区別不能になる (T*, H*) を探索(留保 1 確定後に実装)。"""
    raise NotImplementedError("awaiting v0.2: 留保 1 decision(SF calibration anchor)")
