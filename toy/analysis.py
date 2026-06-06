"""analysis — response curve と susceptibility 特徴抽出(spec §8)。

**scaffold のみ。** Week5 実装。susceptibility curve(出力指標 Y を θ の関数として)から
4 特徴(初期勾配 / 飽和水準 / 半減点 / 曲線下面積)を抽出する(spec §8.3)。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def susceptibility_features(
    theta: npt.NDArray[np.float64], y: npt.NDArray[np.float64]
) -> dict[str, float]:
    """θ-Y susceptibility curve から f1-f4 を抽出する(Week5 実装)。"""
    raise NotImplementedError("awaiting Week5: susceptibility feature 抽出(spec §8.3)")
