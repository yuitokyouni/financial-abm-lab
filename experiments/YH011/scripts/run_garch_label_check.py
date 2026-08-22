"""YH011 step 3c -- does the "GARCH" label on Theorem 4.1 describe the process?

Theorem 4.1 does not claim markets are GARCH. It claims *this ABM is*, with
alpha = rho^2 k^2 p2^2 gam^2 and beta = rho^2 k^2 p1^2 lam^2. That claim is
what the whole inverse problem rests on, so it is worth testing directly
rather than through an estimator.

Test: pick ABM parameters whose nominal Theorem-4.1 coefficients are exactly
(alpha, beta), simulate, and compare the |r| autocorrelation against a real
GARCH(1,1) run at the same (alpha, beta). If the label is descriptive the two
should look alike. They do not.

Also runs plain GARCH(1,1) against BTC, which matters for interpreting the
whole result: GARCH is not the thing that fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from btc_data import load, windows
from nh_model import simulate_population
from run_memory_check import LAGS, acf_abs

RESULTS = Path(__file__).resolve().parents[1] / "results"


def garch11(alpha, beta, T, m, seed, nu=None):
    rng = np.random.default_rng(seed)
    om = 1.0 - alpha - beta
    s2 = np.full(m, 1.0)
    out = np.empty((T, m))
    for t in range(T + 500):
        e = (rng.normal(size=m) if nu is None
             else rng.standard_t(nu, size=m) / np.sqrt(nu / (nu - 2)))
        u = np.sqrt(s2) * e
        if t >= 500:
            out[t - 500] = u
        s2 = om + alpha * u ** 2 + beta * s2
    return out.T


def abm_at_nominal(alpha, beta, T, m, seed, rk=1.6, p1=0.30, p2=0.40):
    """ABM parameters whose Theorem-4.1 coefficients equal (alpha, beta)."""
    d = {"rho": np.full(m, 4.0), "k": np.full(m, rk / 4.0),
         "p1": np.full(m, p1), "p2": np.full(m, p2),
         "lam": np.full(m, np.sqrt(beta) / rk / p1),
         "gam": np.full(m, np.sqrt(alpha) / rk / p2),
         "h_coef": np.full(m, 0.1)}
    return simulate_population(d, T, seed=seed)


def main() -> None:
    T, m = 4000, 400
    out = {"lags": LAGS, "pairs": []}
    print("|r| autocorrelation at identical NOMINAL Theorem-4.1 coefficients\n")
    for alpha, beta in [(0.10, 0.89), (0.05, 0.90), (0.20, 0.70)]:
        g = np.nanmedian([acf_abs(x) for x in garch11(alpha, beta, T, m, 3)], axis=0)
        a = np.nanmedian([acf_abs(x) for x in abm_at_nominal(alpha, beta, T, m, 3)],
                         axis=0)
        out["pairs"].append({"alpha": alpha, "beta": beta,
                             "garch": g.tolist(), "abm": a.tolist()})
        print(f"nominal alpha={alpha}, beta={beta}  (alpha+beta={alpha+beta:.2f})")
        print(f"  {'lag':>5s} " + " ".join(f"{L:>8d}" for L in LAGS))
        print(f"  {'GARCH':>5s} " + " ".join(f"{v:8.4f}" for v in g))
        print(f"  {'ABM':>5s} " + " ".join(f"{v:8.4f}" for v in a))
        print()

    ts, r = load()
    btc = np.nanmean([acf_abs(w["returns"]) for w in windows(ts, r, 2000)], axis=0)
    best = []
    for nu in (None, 4):
        for phi in (0.90, 0.95, 0.97, 0.99, 0.999):
            for alpha in (0.02, 0.05, 0.10, 0.20):
                if alpha >= phi:
                    continue
                g = np.nanmean([acf_abs(x) for x in
                                garch11(alpha, phi - alpha, 2000, 60, 1, nu)], axis=0)
                d = abs(g[0] - btc[0]) + abs(g[LAGS.index(20)] - btc[LAGS.index(20)])
                best.append((d, alpha, phi, nu, g.tolist()))
    best.sort(key=lambda z: z[0])
    d, alpha, phi, nu, g = best[0]
    out["btc"] = {"acf": btc.tolist(), "best_garch": {
        "alpha": alpha, "alpha_plus_beta": phi,
        "innovations": "normal" if nu is None else f"t({nu})", "acf": g}}
    print("plain GARCH(1,1) vs BTC (best of the grid, by lag-1 + lag-20 error)")
    print(f"  {'lag':>5s} " + " ".join(f"{L:>8d}" for L in LAGS))
    print(f"  {'BTC':>5s} " + " ".join(f"{v:8.4f}" for v in btc))
    print(f"  {'GARCH':>5s} " + " ".join(f"{v:8.4f}" for v in g)
          + f"   (alpha={alpha}, alpha+beta={phi}, "
            f"{'normal' if nu is None else f't({nu})'})")

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "garch_label_check.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {RESULTS/'garch_label_check.json'}")


if __name__ == "__main__":
    main()
