"""Simulation-based inference for the AI-trader share p2.

One inference engine, three *summary vectors*, so the comparison isolates what
each summary knows about p2 rather than confounding it with estimator choice:

  garch_theorem  -- (omega, alpha, beta) from GARCH(1,1) QMLE, inverted through
                    Theorem 4.1 as p2 = sqrt(alpha)/(rho k gam). The textbook
                    route the paper's theorem invites. Not fitted through the
                    engine below -- it is a closed-form inversion, reported for
                    contrast.
  garch_aux      -- the same (omega, alpha, beta), but used only as an
                    *auxiliary statistic*: the binding function p2 -> QMLE
                    output is learned by simulation instead of assumed. This is
                    indirect inference; it is immune to the theorem's
                    approximation error while still leaning on a GARCH fit.
  sieve_sf       -- sieve's prespecified stylized-fact battery plus the
                    absolute-value shape features. No GARCH anywhere.

Engine: rejection ABC with local-linear regression adjustment (Beaumont,
Zhang & Balding 2002) on rank-normalised summaries. Rank normalisation is not
cosmetic here -- the model's kurtosis and Hill features have seed
distributions heavy enough that a Euclidean distance on raw values is decided
by a single draw.
"""

from __future__ import annotations

import numpy as np


def rank_normalise(bank: np.ndarray) -> tuple[np.ndarray, callable]:
    """Map each feature to its bank rank in (0,1), then to a normal score.

    Returns the transformed bank and a transformer for new observations that
    uses the *bank's* empirical CDF, so an observation outside the bank's
    support saturates instead of exploding.
    """
    sorted_cols = [np.sort(bank[np.isfinite(bank[:, j]), j])
                   for j in range(bank.shape[1])]

    def transform(x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(x)
        out = np.empty_like(x, dtype=float)
        for j, col in enumerate(sorted_cols):
            n = len(col)
            pos = np.searchsorted(col, x[:, j])
            q = (pos + 0.5) / (n + 1.0)
            q = np.clip(q, 1.0 / (n + 1.0), 1.0 - 1.0 / (n + 1.0))
            out[:, j] = _probit(q)
            out[~np.isfinite(x[:, j]), j] = 0.0   # missing -> bank centre
        return out

    return transform(bank), transform


def _probit(q: np.ndarray) -> np.ndarray:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    q = np.asarray(q, dtype=float)
    out = np.empty_like(q)
    lo, hi = q < 0.02425, q > 1 - 0.02425
    mid = ~(lo | hi)
    r = np.sqrt(-2 * np.log(np.where(lo, q, 0.5)))
    out[lo] = ((((((c[0]*r+c[1])*r+c[2])*r+c[3])*r+c[4])*r+c[5])
               / ((((d[0]*r+d[1])*r+d[2])*r+d[3])*r+1))[lo]
    r = np.sqrt(-2 * np.log(np.where(hi, 1 - q, 0.5)))
    out[hi] = (-(((((c[0]*r+c[1])*r+c[2])*r+c[3])*r+c[4])*r+c[5])
               / ((((d[0]*r+d[1])*r+d[2])*r+d[3])*r+1))[hi]
    r = np.where(mid, q, 0.5) - 0.5
    s = r * r
    out[mid] = ((((((a[0]*s+a[1])*s+a[2])*s+a[3])*s+a[4])*s+a[5])*r
                / (((((b[0]*s+b[1])*s+b[2])*s+b[3])*s+b[4])*s+1))[mid]
    return out


class ABCPosterior:
    """Fit once on a simulation bank, then query with observed summaries."""

    def __init__(self, summaries: np.ndarray, theta: np.ndarray,
                 accept_frac: float = 0.02):
        keep = np.isfinite(summaries).all(axis=1) & np.isfinite(theta)
        self.raw = summaries[keep]
        self.theta = theta[keep]
        self.z, self._tf = rank_normalise(self.raw)
        self.sd = self.z.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        self.zs = self.z / self.sd
        # The local-linear adjustment fits n_features + 1 coefficients inside
        # the accepted set. With too few neighbours it interpolates them, the
        # residual spread collapses and the posterior undercovers badly (0.49
        # against a nominal 0.90 in the first run of this study). Keep at least
        # 12 neighbours per fitted coefficient.
        floor = 12 * (self.z.shape[1] + 1)
        self.n_keep = min(len(self.theta) - 1,
                          max(floor, int(accept_frac * len(self.theta))))
        if self.n_keep < floor:
            raise ValueError(
                f"bank of {len(self.theta)} is too small for "
                f"{self.z.shape[1]} features: need >= {floor} accepted draws")

    def support_distance(self, x: np.ndarray) -> np.ndarray:
        """Distance to the bank's nearest simulation, in normalised units.

        This is the model-adequacy gate: an observation whose nearest neighbour
        in the whole bank is far away is outside anything the model can
        produce, and the posterior below is then extrapolation dressed up as
        inference. Reported, never silently ignored.
        """
        zq = self._tf(np.atleast_2d(x)) / self.sd
        d = np.linalg.norm(self.zs[None, :, :] - zq[:, None, :], axis=2)
        return d.min(axis=1) / np.sqrt(self.zs.shape[1])

    def posterior(self, x: np.ndarray) -> dict:
        """Local-linear-adjusted ABC posterior sample for one observation."""
        zq = (self._tf(np.atleast_2d(x)) / self.sd)[0]
        d = np.linalg.norm(self.zs - zq, axis=1)
        idx = np.argpartition(d, self.n_keep)[:self.n_keep]
        dk, tk, zk = d[idx], self.theta[idx], self.zs[idx]
        h = dk.max() if dk.max() > 0 else 1.0
        w = np.maximum(0.0, 1.0 - (dk / h) ** 2)          # Epanechnikov
        w = w / w.sum() if w.sum() > 0 else np.full_like(w, 1 / len(w))
        # local linear adjustment: theta_adj = theta - (z - z_obs) . beta
        X = np.column_stack([np.ones(len(idx)), zk - zq])
        W = np.diag(w)
        try:
            # ridge on the slopes only (never the intercept): the accepted
            # set is by construction a narrow, collinear cloud
            pen = np.eye(X.shape[1]) * 1e-3 * float(np.trace(X.T @ W @ X))
            pen[0, 0] = 0.0
            coef = np.linalg.solve(X.T @ W @ X + pen, X.T @ W @ tk)
            adj = tk - (zk - zq) @ coef[1:]
        except np.linalg.LinAlgError:
            adj = tk
        q = _weighted_quantiles(adj, w, [0.05, 0.25, 0.5, 0.75, 0.95])
        return {"mean": float(np.sum(w * adj)), "median": float(q[2]),
                "q05": float(q[0]), "q25": float(q[1]), "q75": float(q[3]),
                "q95": float(q[4]), "sample": adj, "weights": w}


def _weighted_quantiles(v: np.ndarray, w: np.ndarray, qs) -> np.ndarray:
    o = np.argsort(v)
    v, w = v[o], w[o]
    cw = np.cumsum(w) - 0.5 * w
    cw /= w.sum()
    return np.interp(qs, cw, v)


def theorem_inversion(alpha_hat: float, rho: float, k: float, gam: float) -> float:
    """p2 = sqrt(alpha)/(rho k gam) -- Theorem 4.1 read backwards."""
    if alpha_hat <= 0 or rho * k * gam <= 0:
        return float("nan")
    return float(np.sqrt(alpha_hat) / (rho * k * gam))
