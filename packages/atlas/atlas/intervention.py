"""B2 intervention schemes — the four observation-channel attenuations the P1 run
needs (spec 002 §13 task 4).

These act on an *observation series* (what an agent reads), not on mechanism
coefficients: B2 ≠ A (ablation). Degrading an observation channel must never
touch the generating mechanism. Ported from the PROV-ABM-atlas toy
(``toy/observation.py``), which is the reference implementation of the P1 B2
surface (experimental_design_v0.3 §7.3).

θ = 0 is the identity for every scheme (property-tested). θ = 1 is "fully
degraded but the mechanism still moves" — schemes are *not* allowed to collapse
to ablation (experimental_design_v0.3 §7.4).
"""

from __future__ import annotations

import math
from enum import StrEnum

import numpy as np
import numpy.typing as npt


class InterventionScheme(StrEnum):
    """The four B2 attenuation schemes (experimental_design_v0.3 §7.3).

    One-to-one with the four literature archetypes (B2 survey §2).
    """

    TIME_AGGREGATION = "a"  # average the series in Δt blocks
    LOW_PASS = "b"  # Butterworth low-pass filter
    OBS_NOISE = "c"  # additive Gaussian observation noise
    TIME_DELAY = "d"  # observation lag


#: All P1 schemes, in canonical order.
SCHEMES: tuple[InterventionScheme, ...] = (
    InterventionScheme.TIME_AGGREGATION,
    InterventionScheme.LOW_PASS,
    InterventionScheme.OBS_NOISE,
    InterventionScheme.TIME_DELAY,
)


def apply_scheme(
    scheme: InterventionScheme,
    series: npt.NDArray[np.float64],
    theta: float,
    *,
    rng: np.random.Generator | None = None,
) -> npt.NDArray[np.float64]:
    """Apply attenuation of strength θ ∈ [0, 1] to an observation series.

    θ = 0 returns an exact copy (identity). Scheme ``c`` (observation noise) is
    exogenous and requires an ``rng`` distinct from the agent's own randomness
    (CRN seed-desync avoidance, B2 survey §3).
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

        if length <= 12:
            return s.copy()
        fc = max((1.0 - t) * 0.5, 0.01)
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

    raise ValueError(f"unknown scheme {scheme!r}")  # pragma: no cover
