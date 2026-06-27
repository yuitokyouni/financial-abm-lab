"""synthetic — Cont-outside injectors as instrument-independence probes.

The 8 ABMs in REGISTRY plus the 6-feature fingerprint are all rooted in the
Cont (2001) stylized-facts literature. That's a closed loop: of *course* the
instrument separates the specimens — they were both built from the same
vocabulary.

These three synthetic processes are deliberately chosen to span phenomena the
loop does NOT name explicitly:

  * `garch11`         — exogenous conditional-variance feedback. Vol clustering
                        appears via a parametric mechanism the ABMs do not use,
                        so we can see whether fingerprint's `acf_absret_mean`
                        identifies the clustering family or only an ABM dialect.
  * `levy_walk`       — α-stable returns. Power-law tails as an *axiomatic*
                        property, not an emergent one. Pure fat-tail probe;
                        any Hill cap behaviour should be visible here first.
  * `regime_switch`   — Hidden-Markov 2-state volatility. Adds a *regime-count*
                        and non-stationarity dimension the Cont 6 do not encode.
                        If fingerprint cannot tell this from i.i.d.-Gaussian,
                        the instrument is blind to regime structure.

Each generator returns log-returns suitable for `fingerprint(series)`.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np


SYNTHETIC_BOUNDS: dict[str, dict[str, tuple]] = {
    "garch11": {
        # NOTE: bounds chosen so α+β ≤ 0.99 over the *worst-case* LHS corner —
        # one run had α=0.15+β=0.94=1.09 in v4 first attempt and the resulting
        # explosive series destroyed the standardised-distance geometry. The
        # specimen has to be stationary for the instrument reading to make sense.
        "T": (2000, 3000),
        "omega": (1e-7, 1e-5),
        "alpha": (0.03, 0.10),
        "beta": (0.80, 0.89),
    },
    "levy_walk": {
        "T": (2000, 3000),
        "alpha_stable": (1.3, 1.9),   # α<2 fat tails; α→2 Gaussian
        "scale": (0.005, 0.02),
    },
    "regime_switch": {
        "T": (2000, 3000),
        "p_lo_hi": (0.005, 0.05),   # transition prob low→high
        "p_hi_lo": (0.05, 0.30),    # transition prob high→low (faster mean rev)
        "vol_lo": (0.003, 0.008),
        "vol_hi": (0.020, 0.060),
    },
}

_INT_PARAMS_SYNTH = {"T"}


def sample_params_lhs(name: str, n: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    """Same LHS routine as adapters.sample_params_lhs but over SYNTHETIC_BOUNDS."""
    if name not in SYNTHETIC_BOUNDS:
        raise KeyError(f"no synthetic bounds for {name}")
    bounds = SYNTHETIC_BOUNDS[name]
    keys = list(bounds.keys())
    d = len(keys)
    cut = np.linspace(0, 1, n + 1)
    u = rng.uniform(size=(n, d))
    pts = cut[:n, None] + u * (1.0 / n)
    for j in range(d):
        rng.shuffle(pts[:, j])
    out: list[dict[str, Any]] = []
    for i in range(n):
        kw: dict[str, Any] = {}
        for j, name_ in enumerate(keys):
            lo, hi = bounds[name_]
            v = float(lo + pts[i, j] * (hi - lo))
            if name_ in _INT_PARAMS_SYNTH:
                v = int(round(v))
            kw[name_] = v
        out.append(kw)
    return out


def garch11(T: int, omega: float, alpha: float, beta: float, *, seed: int) -> np.ndarray:
    """GARCH(1,1) returns. r_t = σ_t z_t; σ²_t = ω + α r²_{t-1} + β σ²_{t-1}."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(T)
    sigma2 = np.empty(T)
    r = np.empty(T)
    # Stationary unconditional variance (only meaningful if α+β<1).
    if alpha + beta < 1.0:
        sigma2[0] = omega / (1.0 - alpha - beta)
    else:
        sigma2[0] = omega
    r[0] = np.sqrt(sigma2[0]) * z[0]
    for t in range(1, T):
        sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        r[t] = np.sqrt(sigma2[t]) * z[t]
    return r


def levy_walk(T: int, alpha_stable: float, scale: float, *, seed: int) -> np.ndarray:
    """α-stable returns via the Chambers-Mallows-Stuck algorithm (symmetric, β=0).

    Avoids `scipy.stats.levy_stable.rvs` which can be slow / hit numerical issues
    near α=2. CMS is the standard generator and α∈(0,2] is supported directly.
    """
    rng = np.random.default_rng(seed)
    a = float(alpha_stable)
    # symmetric β=0 → simplified CMS
    U = rng.uniform(-np.pi / 2, np.pi / 2, size=T)
    W = rng.exponential(scale=1.0, size=T)
    if abs(a - 1.0) < 1e-6:
        X = np.tan(U)
    else:
        X = (np.sin(a * U) / np.power(np.cos(U), 1.0 / a)) * \
            np.power(np.cos(U - a * U) / W, (1.0 - a) / a)
    return scale * X


def regime_switch(T: int, p_lo_hi: float, p_hi_lo: float,
                  vol_lo: float, vol_hi: float, *, seed: int) -> np.ndarray:
    """Hidden Markov 2-state vol regime; conditional returns Gaussian within a state."""
    rng = np.random.default_rng(seed)
    state = np.zeros(T, dtype=np.int8)  # 0 = low, 1 = high
    s = 0
    for t in range(T):
        state[t] = s
        if s == 0 and rng.random() < p_lo_hi:
            s = 1
        elif s == 1 and rng.random() < p_hi_lo:
            s = 0
    z = rng.standard_normal(T)
    vols = np.where(state == 0, vol_lo, vol_hi)
    return vols * z


GENERATORS: dict[str, Callable[..., np.ndarray]] = {
    "garch11": garch11,
    "levy_walk": levy_walk,
    "regime_switch": regime_switch,
}


def build_and_run(name: str, params: dict[str, Any], *, seed: int) -> np.ndarray:
    """Dispatch to the named generator. Returns the log-return-like series."""
    if name not in GENERATORS:
        raise KeyError(f"unknown synthetic {name}; available={list(GENERATORS)}")
    fn = GENERATORS[name]
    # The generator signatures use keyword-only seed; everything else flat-dict.
    return fn(seed=seed, **params)
