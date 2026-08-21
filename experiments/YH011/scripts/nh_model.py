"""Nakagawa-Hirano-Minami-Mizuta (arXiv:2409.12516) aggregate market model.

Reference: "A Multi-agent Market Model Can Explain the Impact of AI Traders
in Financial Markets -- A New Microfoundations of GARCH model",
Nakagawa, Hirano, Minami & Mizuta (2024).

Structure (paper's Section 3-4, re-derived here so the *exact* recursion is
simulated rather than its GARCH approximation):

    D_t     = p1 (g(x_{t-1}) - lam sigma_{t-1})
            + p2 (h(x_{t-1}) - gam |u_{t-1}|)          order-imbalance signal
    A^b_t   = (S/2)(1 + D_t) + (kS/2)(1 + D_t) eps_t
    A^s_t   = (S/2)(1 - D_t) - (kS/2)(1 + D_t) eps_t
    r_t     = rho (A^b_t - A^s_t)/(A^b_t + A^s_t)
            = rho D_t + rho k (1 + D_t) eps_t
    =>  f_t = rho D_t                                  conditional mean
        sigma_t = rho k |1 + D_t|                      conditional sd
        u_t = r_t - f_t = sigma_t eps_t

Theorem 4.1 squares sigma_t and *drops the cross terms*, giving GARCH(1,1)

    sigma_t^2 ~= omega + alpha u_{t-1}^2 + beta sigma_{t-1}^2
    omega = rho^2 k^2 (1 + p1^2 g^2 + p2^2 h^2)
    alpha = rho^2 k^2 p2^2 gam^2          <- carries the AI-trader share p2
    beta  = rho^2 k^2 p1^2 lam^2          <- carries the fundamental share p1

`simulate` runs the exact recursion; `garch_params` returns the Theorem-4.1
coefficients for the same parameter point, so the two can be compared.

The absolute value in sigma_t is ours, not the paper's: the paper's sigma_t is
rho k (1 + D_t), which is negative whenever D_t < -1, and D_t < -1 happens at
the paper's own parameters (see `clip_rate` in the returned diagnostics).
Squaring -- which is all Theorem 4.1 ever does with sigma_t -- is insensitive
to the sign, so |.| is the reading that keeps the theorem intact.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

# Paper's Section 5 parameter point (Table 1 reproduction).
PAPER = dict(rho=4.0, k=0.4, p1=0.2, p2=0.4, lam=1.2, gam=1.2, h_coef=0.1)


@dataclass(frozen=True)
class Params:
    """One parameter point of the aggregate model."""
    rho: float = 4.0     # order-imbalance -> return coefficient
    k: float = 0.4       # inverse liquidity (larger k = thinner book)
    p1: float = 0.2      # fundamental-trader share
    p2: float = 0.4      # AI-trader share            <- the estimand
    lam: float = 1.2     # fundamental-trader risk aversion
    gam: float = 1.2     # AI-trader risk aversion
    h_coef: float = 0.1  # AI predictor h(x) = h_coef * x

    def garch_params(self) -> dict[str, float]:
        """Theorem 4.1 coefficients (omega uses E[g^2], E[h^2] under x~N(0,1))."""
        rk2 = (self.rho * self.k) ** 2
        eg2 = float(np.mean(g_fundamental(np.random.default_rng(0).normal(size=200_000)) ** 2))
        eh2 = self.h_coef ** 2  # E[(h_coef x)^2] with Var(x)=1
        return {
            "omega": rk2 * (1.0 + self.p1 ** 2 * eg2 + self.p2 ** 2 * eh2),
            "alpha": rk2 * self.p2 ** 2 * self.gam ** 2,
            "beta": rk2 * self.p1 ** 2 * self.lam ** 2,
        }


def stability(params: Params) -> dict[str, float | bool]:
    """Where the model stops being a market and starts being an explosion.

    Two boundaries, which turn out to coincide almost exactly:

    * covariance stationarity of the Theorem 4.1 GARCH, alpha + beta < 1,
      i.e. (rho k)^2 (p2^2 gam^2 + p1^2 lam^2) < 1;
    * strict stationarity of the *exact* recursion, whose large-sigma slope is
      rho k (p1 lam + p2 gam |eps|), so the top Lyapunov exponent is
      E[log(rho k (p1 lam + p2 gam |eps|))] < 0.

    At the paper's own parameters both put the ceiling at p2 ~= 0.48, and the
    paper simulates p2 = 0.40 -- 83% of the way to it. Any sweep over p2 has
    to stop below this line; past it the "market" diverges and every summary
    statistic is reading the explosion, not the trader mix.
    """
    rk = params.rho * params.k
    beta = (rk * params.p1 * params.lam) ** 2
    p2_max_cov = (np.sqrt(max(0.0, 1.0 - beta)) / (rk * params.gam)
                  if rk * params.gam > 0 else float("inf"))
    e = np.abs(np.random.default_rng(0).normal(size=400_000))
    lyap = float(np.mean(np.log(rk * (params.p1 * params.lam
                                      + params.p2 * params.gam * e))))
    return {"alpha_plus_beta": beta + (rk * params.p2 * params.gam) ** 2,
            "p2_max_covariance_stationary": float(p2_max_cov),
            "lyapunov_exponent": lyap,
            "stationary": bool(lyap < 0.0)}


def g_fundamental(x: np.ndarray) -> np.ndarray:
    """g(x) = log(1 + max(-0.99, x)) -- the paper's fundamental utility shape.

    The max(-0.99, .) floor makes g bounded below by log(0.01) = -4.605, and
    x ~ N(0,1) hits x < -1 about 15.9% of the time, so this floor -- not the
    AI traders -- is where most of the simulation's left-tail mass comes from.
    """
    return np.log1p(np.maximum(-0.99, x))


def simulate(params: Params, n_steps: int, seed: int, burn_in: int = 500,
             n_paths: int = 1, keep_latent: bool = False
             ) -> dict[str, np.ndarray | float]:
    """Simulate the exact recursion, batched over `n_paths` independent paths.

    Paths share the time loop but not the randomness; each is an independent
    run in sieve's sense (they are never concatenated). Arrays come back
    shaped (n_paths, n_steps), or (n_steps,) when ``n_paths == 1``.
    """
    rng = np.random.default_rng(seed)
    total = n_steps + burn_in
    m = n_paths

    x = rng.normal(size=(total, m))     # fundamental variable, iid N(0,1)
    eps = rng.normal(size=(total, m))   # order-flow noise, iid N(0,1)
    g = g_fundamental(x)
    h = params.h_coef * x

    r = np.empty((total, m))
    sigma = np.empty((total, m))
    f = np.empty((total, m))

    rk = params.rho * params.k
    sigma_prev = np.full(m, rk)   # sigma_0: the no-signal level rho*k
    u_prev = np.zeros(m)
    n_neg = 0

    zero = np.zeros(m)
    for t in range(total):
        gt = g[t - 1] if t > 0 else zero
        ht = h[t - 1] if t > 0 else zero
        d = (params.p1 * (gt - params.lam * sigma_prev)
             + params.p2 * (ht - params.gam * np.abs(u_prev)))
        raw = 1.0 + d
        n_neg += int(np.count_nonzero(raw < 0.0))
        f[t] = params.rho * d
        sigma[t] = rk * np.abs(raw)
        u = sigma[t] * eps[t]
        r[t] = f[t] + u
        sigma_prev, u_prev = sigma[t], u

    sl = slice(burn_in, total)

    def shape(a):
        a = a[sl].T                      # -> (m, n_steps)
        return a[0] if m == 1 else a

    out = {"return": shape(r), "clip_rate": n_neg / (total * m)}
    if keep_latent:
        out |= {"sigma": shape(sigma), "mean": shape(f), "x": shape(x)}
    return out


def summary_stats(r: np.ndarray) -> dict[str, float]:
    """The four statistics the paper reports in its Table 1."""
    rc = r - r.mean()
    sd = rc.std(ddof=0)
    r2 = rc ** 2
    r2c = r2 - r2.mean()
    denom = float((r2c ** 2).sum())
    return {
        "sd": float(sd),
        "skewness": float(np.mean(rc ** 3) / sd ** 3),
        "kurtosis": float(np.mean(rc ** 4) / sd ** 4),
        "acf1_sq": float((r2c[:-1] * r2c[1:]).sum() / denom) if denom > 0 else float("nan"),
    }


if __name__ == "__main__":
    import json
    p = Params(**PAPER)
    print("Theorem 4.1 coefficients:", json.dumps(p.garch_params(), indent=2))
    # Paper: single T=1000 path. Repeat over seeds to see the sampling spread.
    rows = [summary_stats(rr) for rr in simulate(p, 1000, 0, n_paths=200)["return"]]
    print(f"{'stat':10s} {'median':>9s} {'p05':>9s} {'p95':>9s}   paper")
    paper = {"sd": None, "skewness": -1.880, "kurtosis": 9.230, "acf1_sq": 0.367}
    for key in ("sd", "skewness", "kurtosis", "acf1_sq"):
        v = np.array([row[key] for row in rows])
        pv = paper[key]
        print(f"{key:10s} {np.median(v):9.3f} {np.percentile(v,5):9.3f} "
              f"{np.percentile(v,95):9.3f}   {'-' if pv is None else f'{pv:.3f}'}")
    print(f"\nclip rate (1+D_t < 0): {simulate(p, 1000, 0, n_paths=200)['clip_rate']:.3f}")


def simulate_population(draws: dict[str, np.ndarray], n_steps: int, seed: int,
                        burn_in: int = 500) -> np.ndarray:
    """Simulate one path per parameter draw, vectorised across draws.

    ``draws`` maps each :class:`Params` field to an array of length m. Every
    operation in the recursion is elementwise in the path dimension, so a
    population of m *different* parameter points costs one time loop instead
    of m of them -- which is what makes a simulation bank of thousands of
    draws cheap enough to build an ABC posterior on.

    Returns an (m, n_steps) array of returns.
    """
    m = len(next(iter(draws.values())))
    rho, k = draws["rho"], draws["k"]
    p1, p2 = draws["p1"], draws["p2"]
    lam, gam, h_coef = draws["lam"], draws["gam"], draws["h_coef"]

    rng = np.random.default_rng(seed)
    total = n_steps + burn_in
    r = np.empty((total, m))
    rk = rho * k
    sigma_prev = rk.copy()
    u_prev = np.zeros(m)
    x_prev = np.zeros(m)

    for t in range(total):
        gt = g_fundamental(x_prev)
        ht = h_coef * x_prev
        d = p1 * (gt - lam * sigma_prev) + p2 * (ht - gam * np.abs(u_prev))
        sigma = rk * np.abs(1.0 + d)
        u = sigma * rng.normal(size=m)
        r[t] = rho * d + u
        sigma_prev, u_prev = sigma, u
        x_prev = rng.normal(size=m)

    return r[burn_in:].T
