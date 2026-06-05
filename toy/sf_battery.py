"""sf_battery — Stylized Facts SF1-SF6 測定(spec §4)。

**scaffold のみ。** 留保 2(SF battery のスコープ:何を calibration target にし、何を
post-equivalence の独立検証量にするか)が Yuito confirm 待ちのため、本体は実装しない。
確定後に v0.2 を切ってから measure を実装する(CLAUDE.md「未解決」)。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

# spec §4 の SF ID(measure 実装は留保 2 確定後)。
SF_IDS: tuple[str, ...] = ("SF1", "SF2", "SF3", "SF4", "SF5", "SF6")


def measure_sf_battery(returns: npt.NDArray[np.float64]) -> dict[str, float]:
    """return 系列から SF1-SF6 の特徴量を測る(留保 2 確定後に実装)。"""
    raise NotImplementedError("awaiting v0.2: 留保 2 decision(SF battery scope)")
