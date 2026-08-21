"""YH011 step 2 -- can p2 be recovered, and does dropping GARCH help?

Builds a simulation bank from the exact recursion, then scores four routes to
p2 on held-out simulations where the truth is known:

  theorem_qmle  p2 = sqrt(alpha_QMLE)/(rho k gam)   -- Theorem 4.1 inverted
  garch_ii      ABC on (alpha, beta, alpha+beta, log omega/var) -- indirect
                inference: same GARCH fit, but the binding function is learned
                by simulation rather than assumed
  sieve_sf      ABC on sieve's stylized-fact battery + |r| shape features
  sieve+garch   both feature blocks, to see whether GARCH adds anything

Two nuisance regimes:
  oracle  -- p1, k, lam, gam, h_coef known; only p2 unknown
  wide    -- all of them unknown, drawn from the prior alongside p2

Scored on bias, RMSE, 90% interval coverage and interval width. Coverage is
the number that decides whether any BTC figure may be quoted with error bars.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np

from inference import ABCPosterior, theorem_inversion
from nh_model import PAPER, Params, simulate_population
from summaries import FEATURE_NAMES, garch_aux, summary_vector

warnings.filterwarnings("ignore")
RESULTS = Path(__file__).resolve().parents[1] / "results"
FIELDS = list(Params.__dataclass_fields__)

# Wide prior. rho is fixed: the model is scale-equivariant under
# (rho, lam, gam) -> (c rho, lam/c, gam/c) and every summary used here is
# scale-invariant, so rho is the scale normalisation, not a free parameter.
WIDE = {"rho": (4.0, 4.0), "k": (0.15, 0.70), "p1": (0.05, 0.50),
        "p2": (0.00, 0.60), "lam": (0.40, 2.50), "gam": (0.40, 2.50),
        "h_coef": (0.00, 0.30)}


def _probit_abs(q):
    from inference import _probit
    return _probit((q + 1.0) / 2.0)          # quantiles of |N(0,1)|


def _lyapunov(rk, p1lam, p2gam):
    """E[log(rk (p1 lam + p2 gam |eps|))] by stratified quadrature.

    Evaluated on 1024 stratified quantiles of |N(0,1)| rather than a random
    sample: deterministic, accurate to ~1e-3, and -- unlike broadcasting a
    20k-point sample against 30k candidate draws -- it does not allocate 5 GB
    and thrash the box, which is exactly what the first version of this did.
    """
    q = (np.arange(1024) + 0.5) / 1024
    e = np.abs(_probit_abs(q))
    out = np.empty(len(rk))
    step = 4096
    for i in range(0, len(rk), step):
        s = slice(i, i + step)
        out[s] = np.log(np.maximum(
            1e-300,
            rk[s, None] * (p1lam[s, None] + p2gam[s, None] * e[None, :]))).mean(1)
    return out


def draw_prior(n: int, rng, regime: str) -> dict[str, np.ndarray]:
    """Draw from the prior, rejecting non-stationary parameter points."""
    out: dict[str, list] = {f: [] for f in FIELDS}
    got = 0
    while got < n:
        m = int((n - got) * 1.6) + 64
        if regime == "oracle":
            d = {f: np.full(m, PAPER[f]) for f in FIELDS}
            d["p2"] = rng.uniform(0.0, 0.60, m)
        else:
            d = {f: (np.full(m, WIDE[f][0]) if WIDE[f][0] == WIDE[f][1]
                     else rng.uniform(*WIDE[f], m)) for f in FIELDS}
        rk = d["rho"] * d["k"]
        beta = (rk * d["p1"] * d["lam"]) ** 2
        alpha = (rk * d["p2"] * d["gam"]) ** 2
        lyap = _lyapunov(rk, d["p1"] * d["lam"], d["p2"] * d["gam"])
        ok = (lyap < -0.01) & (alpha + beta < 0.98)
        take = min(int(ok.sum()), n - got)
        idx = np.flatnonzero(ok)[:take]
        for f in FIELDS:
            out[f].append(d[f][idx])
        got += take
    return {f: np.concatenate(v)[:n] for f, v in out.items()}


def build_bank(n: int, T: int, seed: int, regime: str, with_garch: bool):
    rng = np.random.default_rng(seed)
    draws = draw_prior(n, rng, regime)
    print(f"  simulating {n} draws x T={T} ({regime}) ...", flush=True)
    R = simulate_population(draws, T, seed=seed + 1)
    print("  summaries ...", flush=True)
    S = np.array([[summary_vector(r)[k] for k in FEATURE_NAMES] for r in R])
    G = None
    if with_garch:
        print("  GARCH QMLE fits ...", flush=True)
        G = np.empty((n, 4))
        for i, r in enumerate(R):
            try:
                g = garch_aux(r)
                v = float(np.var(r))
                G[i] = [g["alpha"], g["beta"], g["alpha"] + g["beta"],
                        np.log(max(g["omega"], 1e-12) / max(v, 1e-12))]
            except Exception:
                G[i] = np.nan
            if (i + 1) % 1000 == 0:
                print(f"    {i+1}/{n}", flush=True)
    return draws, S, G


def score(name, truth, est, lo, hi, extra=None) -> dict:
    ok = np.isfinite(est) & np.isfinite(truth)
    e, t = est[ok], truth[ok]
    cov = (np.isfinite(lo) & np.isfinite(hi) & (truth >= lo) & (truth <= hi))
    return {"estimator": name, "n_scored": int(ok.sum()),
            "bias": float(np.mean(e - t)), "rmse": float(np.sqrt(np.mean((e - t) ** 2))),
            "mae": float(np.mean(np.abs(e - t))),
            "corr": float(np.corrcoef(e, t)[0, 1]) if ok.sum() > 2 else float("nan"),
            "coverage_90": float(np.mean(cov[ok])) if ok.sum() else float("nan"),
            "mean_interval_width": float(np.nanmean((hi - lo)[ok])),
            **(extra or {})}


def run_regime(regime: str, n_bank: int, n_test: int, T: int, seed: int) -> list[dict]:
    print(f"\n### regime = {regime}, T = {T}")
    dtr, Str, Gtr = build_bank(n_bank, T, seed, regime, with_garch=True)
    dte, Ste, Gte = build_bank(n_test, T, seed + 5000, regime, with_garch=True)
    truth = dte["p2"]
    rows = []

    # --- Theorem 4.1 inverted, with rho,k,gam handed over as ORACLE truth.
    # Deliberately generous: in a real application those are unknown too.
    a = Gte[:, 0]
    est = np.array([theorem_inversion(ai, r_, k_, g_) for ai, r_, k_, g_
                    in zip(a, dte["rho"], dte["k"], dte["gam"])])
    rows.append(score("theorem_qmle", truth, est,
                      np.full_like(est, np.nan), np.full_like(est, np.nan),
                      {"note": "closed form; rho,k,gam given as oracle truth; "
                               "no interval"}))

    banks = {
        "garch_ii": (Gtr, Gte),
        "sieve_sf": (Str, Ste),
        "sieve+garch": (np.hstack([Str, Gtr]), np.hstack([Ste, Gte])),
    }
    for name, (Btr, Bte) in banks.items():
        abc = ABCPosterior(Btr, dtr["p2"], accept_frac=0.02)
        med = np.full(len(truth), np.nan)
        lo = np.full(len(truth), np.nan)
        hi = np.full(len(truth), np.nan)
        for i, x in enumerate(Bte):
            if not np.isfinite(x).all():
                continue
            p = abc.posterior(x)
            med[i], lo[i], hi[i] = p["median"], p["q05"], p["q95"]
        sd = abc.support_distance(Bte[np.isfinite(Bte).all(axis=1)])
        rows.append(score(name, truth, med, lo, hi,
                          {"median_support_distance": float(np.median(sd))}))

    # prior-only reference: what you get by guessing, for scale
    pri = dtr["p2"]
    rows.append({"estimator": "prior_only", "n_scored": len(truth),
                 "bias": float(np.mean(np.median(pri) - truth)),
                 "rmse": float(np.sqrt(np.mean((np.median(pri) - truth) ** 2))),
                 "mae": float(np.mean(np.abs(np.median(pri) - truth))),
                 "corr": 0.0,
                 "coverage_90": float(np.mean(
                     (truth >= np.percentile(pri, 5)) & (truth <= np.percentile(pri, 95)))),
                 "mean_interval_width": float(np.percentile(pri, 95) - np.percentile(pri, 5))})

    hdr = f"{'estimator':14s} {'bias':>8s} {'RMSE':>8s} {'corr':>7s} {'cov90':>7s} {'width':>8s}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['estimator']:14s} {r['bias']:+8.3f} {r['rmse']:8.3f} "
              f"{r['corr']:7.3f} {r['coverage_90']:7.3f} {r['mean_interval_width']:8.3f}")
    for r in rows:
        r |= {"regime": regime, "T": T, "n_bank": n_bank, "n_test": n_test}
    np.savez_compressed(RESULTS / f"bank_{regime}_T{T}.npz",
                        S=Str, G=Gtr, **{f"theta_{k}": v for k, v in dtr.items()})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-bank", type=int, default=6000)
    ap.add_argument("--n-test", type=int, default=800)
    ap.add_argument("--lengths", type=int, nargs="+", default=[2000])
    ap.add_argument("--regimes", nargs="+", default=["oracle", "wide"])
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    rows = []
    for T in args.lengths:
        for regime in args.regimes:
            rows += run_regime(regime, args.n_bank, args.n_test, T, args.seed)
    (RESULTS / "estimators.json").write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {RESULTS/'estimators.json'}")


if __name__ == "__main__":
    main()
