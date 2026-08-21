"""Exploratory extension: NH with heterogeneous AI horizons (NH-HAR).

NOT the paper's model. This is YH011's answer to the question the adequacy
test raises -- "what would the model need in order to reach BTC at all?" --
and it is kept separate from `nh_model.py` so nothing here is ever mistaken
for a reproduction of arXiv:2409.12516.

The gap the adequacy test finds is volatility *memory*: the paper's recursion
carries one lag, so its |r| autocorrelation decays geometrically, while BTC's
decays far more slowly. The minimal change that fixes this without touching
the economics is to stop assuming every AI trader looks back exactly one step.
Replace the single risk term gamma|u_{t-1}| with a mixture over horizons,

    ubar_t = sum_j w_j v_{j,t},     v_{j,t} = (1-phi_j)|u_t| + phi_j v_{j,t-1}

and likewise for sigma. A mixture of exponentials with spread decay rates
aggregates to near-hyperbolic decay (Granger 1980), which is exactly the
observed shape. Economically it says the AI population is heterogeneous in
lookback -- some trade off the last bar, some off the last quarter -- which is
a weaker assumption than the homogeneity the original makes, not a stronger
one.

p2 keeps its meaning: it is still the AI share, still multiplying both the
forecast channel h and the risk channel gamma*ubar. The horizon weights are
fixed a priori, not fitted, so the extension does not buy its fit with extra
free parameters.
"""

from __future__ import annotations

import numpy as np

from nh_model import g_fundamental

# Decay rates spanning ~1, 3, 14 and 66 steps of lookback. Fixed, not fitted.
PHI = np.array([0.0, 0.70, 0.93, 0.985])
W = np.full(len(PHI), 1.0 / len(PHI))


def lyapunov_har(rk, p1lam, p2gam, n=1024):
    """Same stationarity screen as nh_model, using the mixture's unit gain.

    The EMA mixture has total gain 1 by construction (weights sum to one, each
    EMA is a proper average), so the large-sigma slope is the same expression
    as the one-lag model -- the memory is redistributed across lags, not added.
    """
    q = (np.arange(n) + 0.5) / n
    from inference import _probit
    e = np.abs(_probit((q + 1.0) / 2.0))
    out = np.empty(len(rk))
    for i in range(0, len(rk), 4096):
        s = slice(i, i + 4096)
        out[s] = np.log(np.maximum(1e-300, rk[s, None] *
                        (p1lam[s, None] + p2gam[s, None] * e[None, :]))).mean(1)
    return out


def simulate_population_har(draws: dict[str, np.ndarray], n_steps: int,
                            seed: int, burn_in: int = 1000) -> np.ndarray:
    """One path per parameter draw, vectorised, with heterogeneous horizons."""
    m = len(next(iter(draws.values())))
    rho, k = draws["rho"], draws["k"]
    p1, p2 = draws["p1"], draws["p2"]
    lam, gam, h_coef = draws["lam"], draws["gam"], draws["h_coef"]

    rng = np.random.default_rng(seed)
    total = n_steps + burn_in
    r = np.empty((total, m))
    rk = rho * k

    v_u = np.zeros((len(PHI), m))          # EMAs of |u|
    v_s = np.full((len(PHI), m), 1.0) * rk  # EMAs of sigma
    x_prev = np.zeros(m)

    for t in range(total):
        ubar = W @ v_u
        sbar = W @ v_s
        d = (p1 * (g_fundamental(x_prev) - lam * sbar)
             + p2 * (h_coef * x_prev - gam * ubar))
        sigma = rk * np.abs(1.0 + d)
        u = sigma * rng.normal(size=m)
        r[t] = rho * d + u
        v_u = (1.0 - PHI)[:, None] * np.abs(u)[None, :] + PHI[:, None] * v_u
        v_s = (1.0 - PHI)[:, None] * sigma[None, :] + PHI[:, None] * v_s
        x_prev = rng.normal(size=m)

    return r[burn_in:].T
