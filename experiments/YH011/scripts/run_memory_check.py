"""YH011 step 3b -- the specific thing the model cannot do: volatility memory.

The joint adequacy test says BTC is out of reach. This says *why*, in a form
that does not depend on the summary vector chosen.

The model's volatility recursion has one lag. Its |r| autocorrelation
therefore decays geometrically. Real markets -- BTC very much included --
decay far more slowly than any geometric rate that also matches lag 1. So the
question is not "which p2 fits BTC" but "is there any (p1, p2, k, lam, gam)
whose |r| ACF matches BTC at lag 1 AND at lag 20". Answered by search over a
generous prior, at two sampling frequencies so the verdict is not an artefact
of the hourly clock.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np

from btc_data import load, windows
from nh_har import simulate_population_har
from nh_model import simulate_population
from run_model_adequacy import draw

warnings.filterwarnings("ignore")
RESULTS = Path(__file__).resolve().parents[1] / "results"
LAGS = [1, 2, 5, 10, 20, 50, 100]


def acf_abs(r: np.ndarray, lags=LAGS) -> np.ndarray:
    a = np.abs(r - r.mean())
    a = a - a.mean()
    den = float((a ** 2).sum())
    return np.array([float((a[:-L] * a[L:]).sum() / den) if den > 0 else np.nan
                     for L in lags])


def aggregate(r: np.ndarray, factor: int) -> np.ndarray:
    n = len(r) // factor
    return r[:n * factor].reshape(n, factor).sum(axis=1)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["nh", "nh_har"], default="nh")
    args = ap.parse_args()
    sim = simulate_population if args.model == "nh" else simulate_population_har
    rng = np.random.default_rng(11)
    ts, r = load()

    series = {}
    fin = np.isfinite(r)
    series["hourly"] = [w["returns"] for w in windows(ts, r, 2000)]
    # daily: sum 24 contiguous hourly returns; a day containing a tape gap is
    # dropped rather than summed over the hole
    day = []
    for i in range(0, len(r) - 24, 24):
        seg = r[i:i + 24]
        day.append(seg.sum() if np.isfinite(seg).all() else np.nan)
    day = np.array(day)
    day = day[np.isfinite(day)]
    series["daily"] = [day]

    print("drawing model cloud ...", flush=True)
    theta = draw(4000, rng)
    out = {}
    for freq, segs in series.items():
        n = len(segs[0])
        btc = np.nanmean([acf_abs(s) for s in segs], axis=0)
        M = sim(theta, n, seed=21)
        model = np.array([acf_abs(x) for x in M])
        ok = np.isfinite(model).all(axis=1)
        model, th = model[ok], {k: v[ok] for k, v in theta.items()}

        # the draws that match BTC at lag 1, then where they land at lag 20
        j1, j20 = LAGS.index(1), LAGS.index(20)
        close = np.abs(model[:, j1] - btc[j1]) < 0.02
        print(f"\n=== [{args.model}] {freq}  (n = {n} per segment, "
              f"{len(segs)} segment(s)) ===")
        print(f"{'lag':>5s} {'BTC':>9s} {'model best-lag1 med':>21s} "
              f"{'model max over prior':>22s}")
        rows = []
        for i, L in enumerate(LAGS):
            sub = model[close, i] if close.sum() >= 20 else np.array([np.nan])
            rows.append({"lag": L, "btc": float(btc[i]),
                         "model_matched_lag1_median": float(np.nanmedian(sub)),
                         "model_max_over_prior": float(np.nanmax(model[:, i]))})
            print(f"{L:5d} {btc[i]:9.4f} {np.nanmedian(sub):21.4f} "
                  f"{np.nanmax(model[:, i]):22.4f}")
        reach20 = float((model[:, j20] >= btc[j20]).mean())
        joint = float(((np.abs(model[:, j1] - btc[j1]) < 0.03)
                       & (model[:, j20] >= btc[j20] - 0.02)).mean())
        print(f"  draws with acf|r|(20) >= BTC's {btc[j20]:.3f}: "
              f"{reach20*100:.2f}% of the prior")
        print(f"  draws matching BTC at lag 1 AND reaching lag 20: {joint*100:.2f}%")
        out[freq] = {"n_obs": n, "n_segments": len(segs), "lags": LAGS,
                     "rows": rows, "frac_prior_reaching_lag20": reach20,
                     "frac_prior_matching_both": joint,
                     "n_close_at_lag1": int(close.sum()),
                     "n_model_draws": int(len(model))}

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"memory_check_{args.model}.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {RESULTS/f'memory_check_{args.model}.json'}")


if __name__ == "__main__":
    main()
