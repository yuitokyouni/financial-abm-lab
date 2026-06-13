"""observation — 観測ベクトル o_{i,t} の構築 + B2 masking scheme(spec §3.3, §7)。

観測は **生の時系列のみ**。各チャネルが介入軸1本に対応(spec §7.2):
- ``price_returns``  価格 log-return 履歴   → Model T.chartist が読む / trend masking
- ``agg_action``    集約行動履歴            → Model H が読む / social masking
- ``fundamental``   誤価格系列 m_τ=log(p*/p_τ) → Model T.fundamentalist が読む / fundamental masking
- ``volume``        出来高履歴(v0 未使用、将来)

各成分は raw 観測から内部で信号を抽出する(B2 ≠ A)。観測チャネルを degrade しても機構係数は
触らない。B2 4 scheme(spec §7.3)は ``apply_masking`` に実装。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum

import numpy as np
import numpy.typing as npt

# 観測ベクトルのキー(spec §3.3)。
PRICE_RETURNS = "price_returns"
AGG_ACTION = "agg_action"
FUNDAMENTAL = "fundamental"
VOLUME = "volume"


def _last_padded(hist: Sequence[float], window: int) -> npt.NDArray[np.float64]:
    """履歴末尾 `window` 点。不足分は左を 0 詰め(burn-in 初期の短履歴対策)。"""
    tail = np.asarray(hist[-window:], dtype=np.float64) if len(hist) else np.empty(0, np.float64)
    if tail.size < window:
        return np.concatenate([np.zeros(window - tail.size, dtype=np.float64), tail])
    return tail


def _mispricing(price_hist: Sequence[float], p_star: float, window: int) -> npt.NDArray[np.float64]:
    """誤価格系列 m_τ = log(p* / p_τ)(p<p* で正=割安。fundamentalist が読む)。"""
    if not len(price_hist):
        return np.zeros(window, dtype=np.float64)
    tail = np.asarray(price_hist[-window:], dtype=np.float64)
    m = np.log(p_star / np.clip(tail, 1e-12, None))
    if m.size < window:
        return np.concatenate([np.zeros(window - m.size, dtype=np.float64), m])
    return m


def build_observation(
    return_hist: Sequence[float],
    agg_action_hist: Sequence[float],
    volume_hist: Sequence[float],
    price_hist: Sequence[float],
    p_star: float,
    window: int,
) -> dict[str, npt.NDArray[np.float64]]:
    """o_{i,t}: 価格 return / 集約行動 / 誤価格 / 出来高 の生履歴(各長さ `window`)。"""
    return {
        PRICE_RETURNS: _last_padded(return_hist, window),
        AGG_ACTION: _last_padded(agg_action_hist, window),
        FUNDAMENTAL: _mispricing(price_hist, p_star, window),
        VOLUME: _last_padded(volume_hist, window),
    }


class InterventionScheme(StrEnum):
    """B2 attenuation スキーム(spec §7.3)。文献の4類型と1対1(survey §2)。"""

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
    """観測系列(長さ L)に強度 θ ∈ [0,1] の degradation を適用(spec §7.3)。

    θ=0 で恒等、θ=1 で「完全 mask だが機構は微弱に動く」(§7.4: ablation と同型にしない)。
    scheme (c) は外生的介入ノイズのため `rng` を要する(agent の ctx.random とは別系統、
    same-seed CRN の seed desync 回避; survey §3)。
    """
    s = np.asarray(series, dtype=np.float64)
    length = s.size
    t = float(np.clip(theta, 0.0, 1.0))
    if length == 0 or t == 0.0:
        return s.copy()

    if scheme is InterventionScheme.TIME_AGGREGATION:
        dt = min(math.floor(t * length), length)
        if dt <= 1:
            return s.copy()
        out = s.copy()
        for start in range(0, length, dt):
            out[start : start + dt] = s[start : start + dt].mean()
        return out

    if scheme is InterventionScheme.LOW_PASS:
        from scipy.signal import butter, filtfilt

        fc = max((1.0 - t) * 0.5, 0.01)
        if length <= 12:
            return s.copy()
        b, a = butter(2, fc)
        return np.asarray(filtfilt(b, a, s), dtype=np.float64)

    if scheme is InterventionScheme.OBS_NOISE:
        if rng is None:
            raise ValueError("scheme (c) observation noise requires an rng")
        sigma = t * float(s.std())
        if sigma == 0.0:
            return s.copy()
        return s + rng.normal(0.0, sigma, size=length)

    if scheme is InterventionScheme.TIME_DELAY:
        lag = min(math.floor(t * length), length)
        if lag <= 0:
            return s.copy()
        out = np.empty_like(s)
        out[:lag] = s[0]
        out[lag:] = s[: length - lag]
        return out

    raise ValueError(f"unknown scheme {scheme!r}")
