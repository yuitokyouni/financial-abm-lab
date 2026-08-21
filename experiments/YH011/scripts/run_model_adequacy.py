"""YH011 step 3 -- before estimating p2 on BTC, can the model reach BTC at all?

An ABC posterior always returns a number. It returns one even when the
observation lies nowhere near anything the model can generate -- it simply
reports the least-bad corner of the prior. So the estimate is only meaningful
after this gate: is BTC's summary vector inside the model's reachable set?

Test: draw a deliberately *generous* prior -- wider than the one the estimator
study uses -- keep only stationary points, simulate, and ask for each BTC
window how far it sits from the nearest model draw in rank-normalised summary
space. The reference distribution is the same distance computed for held-out
*model* windows, which is the null: it says how far a genuine draw from this
model typically lands from the rest of the cloud. A BTC distance out in the
right tail of that null is the model failing to reach the data, and no
calibration of the estimator repairs it.

Reported per feature as well as jointly, because *which* feature is out of
reach is the finding: a tail index the model cannot bend to is a different
problem from a volatility memory it structurally does not have.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np

from btc_data import load, windows
from inference import rank_normalise
from nh_har import simulate_population_har
from nh_model import Params, simulate_population
from summaries import BLIND_SPOTS, FEATURE_NAMES, summary_vector

warnings.filterwarnings("ignore")
RESULTS = Path(__file__).resolve().parents[1] / "results"
FIELDS = list(Params.__dataclass_fields__)

# Deliberately more generous than the estimator prior: if the model cannot
# reach BTC even here, the shortfall is structural rather than a bad prior.
GENEROUS = {"rho": (4.0, 4.0), "k": (0.05, 1.20), "p1": (0.00, 0.80),
            "p2": (0.00, 0.80), "lam": (0.10, 4.00), "gam": (0.10, 4.00),
            "h_coef": (0.00, 1.00)}


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


def draw(n: int, rng) -> dict[str, np.ndarray]:
    out = {f: [] for f in FIELDS}
    got = 0
    while got < n:
        m = int((n - got) * 2.0) + 128
        d = {f: (np.full(m, GENEROUS[f][0]) if GENEROUS[f][0] == GENEROUS[f][1]
                 else rng.uniform(*GENEROUS[f], m)) for f in FIELDS}
        rk = d["rho"] * d["k"]
        lyap = _lyapunov(rk, d["p1"] * d["lam"], d["p2"] * d["gam"])
        ok = lyap < -0.01
        idx = np.flatnonzero(ok)[:n - got]
        for f in FIELDS:
            out[f].append(d[f][idx])
        got += len(idx)
    return {f: np.concatenate(v)[:n] for f, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-draws", type=int, default=15000)
    ap.add_argument("--window", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", choices=["nh", "nh_har"], default="nh",
                    help="nh = the paper's one-lag recursion; "
                         "nh_har = the heterogeneous-horizon extension")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    print(f"[{args.model}] drawing {args.n_draws} stationary points "
          f"from the generous prior ...", flush=True)
    theta = draw(args.n_draws, rng)
    sim = (simulate_population if args.model == "nh"
           else simulate_population_har)
    R = sim(theta, args.window, seed=args.seed + 1)
    print("summaries ...", flush=True)
    M = np.array([[summary_vector(r)[k] for k in FEATURE_NAMES] for r in R])
    keep = np.isfinite(M).all(axis=1)
    M = M[keep]
    print(f"  {len(M)} usable model draws", flush=True)

    ts, r = load()
    wins = windows(ts, r, args.window)
    B = np.array([[summary_vector(w["returns"])[k] for k in FEATURE_NAMES]
                  for w in wins])
    print(f"  {len(B)} BTC windows of {args.window} hourly returns", flush=True)

    # --- per-feature reachability
    per_feature = []
    for j, f in enumerate(FEATURE_NAMES):
        lo, hi = M[:, j].min(), M[:, j].max()
        inside = (B[:, j] >= lo) & (B[:, j] <= hi)
        per_feature.append({
            "feature": f,
            "model_min": float(lo), "model_max": float(hi),
            "model_p05": float(np.percentile(M[:, j], 5)),
            "model_p95": float(np.percentile(M[:, j], 95)),
            "btc_median": float(np.median(B[:, j])),
            "btc_p05": float(np.percentile(B[:, j], 5)),
            "btc_p95": float(np.percentile(B[:, j], 95)),
            "btc_windows_inside_model_range": float(inside.mean()),
            "sieve_blind_spots": BLIND_SPOTS.get(f, []),
        })

    # --- joint reachability, with a calibrated null
    n_ref = min(2000, len(M) // 4)
    ref_idx = rng.choice(len(M), n_ref, replace=False)
    mask = np.ones(len(M), bool); mask[ref_idx] = False
    cloud, held = M[mask], M[ref_idx]

    Z, tf = rank_normalise(cloud)
    sd = Z.std(axis=0); sd[sd == 0] = 1.0
    Zc = Z / sd
    nf = Zc.shape[1]

    def nn_dist(X):
        Q = tf(X) / sd
        out = np.empty(len(Q))
        for i in range(len(Q)):
            out[i] = np.min(np.linalg.norm(Zc - Q[i], axis=1))
        return out / np.sqrt(nf)

    d_null = nn_dist(held)
    d_btc = nn_dist(B)
    thresh = float(np.percentile(d_null, 99))
    pvals = [float((d_null >= d).mean()) for d in d_btc]

    joint = {
        "null_median": float(np.median(d_null)),
        "null_p99": thresh,
        "btc_median": float(np.median(d_btc)),
        "btc_min": float(d_btc.min()),
        "btc_windows_beyond_null_p99": float((d_btc > thresh).mean()),
        "btc_window_pvalues": pvals,
        "n_model_cloud": int(len(cloud)), "n_null": int(n_ref),
        "n_btc_windows": int(len(B)),
    }

    print(f"\n{'feature':18s} {'model range':>26s} {'BTC median':>11s} "
          f"{'BTC windows in range':>21s}")
    for d in per_feature:
        rng_s = f"[{d['model_min']:9.3f},{d['model_max']:9.3f}]"
        flag = "" if d["btc_windows_inside_model_range"] > 0.5 else "   <-- OUT OF REACH"
        print(f"{d['feature']:18s} {rng_s:>26s} {d['btc_median']:11.3f} "
              f"{d['btc_windows_inside_model_range']:20.2f}{flag}")

    print(f"\njoint nearest-neighbour distance (rank-normalised, per feature)")
    print(f"  model-vs-model null: median {joint['null_median']:.4f}, "
          f"99th pct {thresh:.4f}")
    print(f"  BTC windows:         median {joint['btc_median']:.4f}, "
          f"closest {joint['btc_min']:.4f}")
    print(f"  BTC windows beyond the null's 99th percentile: "
          f"{joint['btc_windows_beyond_null_p99']*100:.0f}%")
    print(f"  largest single-window p-value: {max(pvals):.4f}")

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"model_adequacy_{args.model}.json").write_text(json.dumps(
        {"model": args.model, "window": args.window,
         "n_draws": args.n_draws, "prior": GENEROUS,
         "per_feature": per_feature, "joint": joint}, indent=1))
    print(f"\nwrote {RESULTS/f'model_adequacy_{args.model}.json'}")


if __name__ == "__main__":
    main()
