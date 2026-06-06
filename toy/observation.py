"""observation — 観測ベクトル o_{i,t} の構築 + B2 masking scheme(spec §3.3, §7.3)。

観測は **生の時系列のみ**(MA/momentum 等の加工特徴は含めない)。Model T は価格 log-return から
内部で trend を、Model H は集約行動から内部で社会信号を抽出する。これが「B2 ≠ A」の核心
(観測チャネルを degrade しても機構そのものは ablate しない)。

B2 介入 4 scheme(time aggregation / low-pass / observation noise / time delay)は **Week4 実装**。
本 v0 では Enum + signature stub のみ(`apply_masking` は NotImplementedError)。
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

import numpy as np
import numpy.typing as npt

# 観測ベクトルのキー(spec §3.3 の 3 要素)。
PRICE_RETURNS = "price_returns"
VOLUME = "volume"
AGG_ACTION = "agg_action"


def _last_padded(hist: Sequence[float], window: int) -> npt.NDArray[np.float64]:
    """履歴末尾 `window` 点を返す。不足分は左側を 0 詰め(burn-in 初期の短履歴対策)。"""
    tail = np.asarray(hist[-window:], dtype=np.float64) if len(hist) else np.empty(0, np.float64)
    if tail.size < window:
        return np.concatenate([np.zeros(window - tail.size, dtype=np.float64), tail])
    return tail


def build_observation(
    return_hist: Sequence[float],
    volume_hist: Sequence[float],
    agg_action_hist: Sequence[float],
    window: int,
) -> dict[str, npt.NDArray[np.float64]]:
    """o_{i,t}: 価格 log-return / 出来高 / 集約行動 の生履歴(各長さ `window`)。"""
    return {
        PRICE_RETURNS: _last_padded(return_hist, window),
        VOLUME: _last_padded(volume_hist, window),
        AGG_ACTION: _last_padded(agg_action_hist, window),
    }


class InterventionScheme(StrEnum):
    """B2 attenuation スキーム(spec §7.3)。本体実装は Week4。"""

    TIME_AGGREGATION = "a"  # 時系列を Δt 刻みで平均化
    LOW_PASS = "b"  # Butterworth low-pass
    OBS_NOISE = "c"  # Gaussian observation noise
    TIME_DELAY = "d"  # 観測 lag


def apply_masking(
    scheme: InterventionScheme,
    series: npt.NDArray[np.float64],
    theta: float,
    *,
    rng: np.random.Generator | None = None,
) -> npt.NDArray[np.float64]:
    """観測系列に強度 θ ∈ [0,1] の degradation を適用する(scaffold)。"""
    raise NotImplementedError(
        f"apply_masking({scheme.value}): awaiting Week4 介入実装 — B2 masking scheme (spec §7.3)"
    )
