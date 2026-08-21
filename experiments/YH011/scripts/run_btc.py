"""YH011 step 4 -- the BTC number, and whether it is allowed to exist.

Applies the GARCH-free estimator to Coinbase BTC-USD hourly returns, window by
window, and gates every window on the model-adequacy test from step 3. A
window whose summary vector sits outside the model's reachable set gets
NOT_IDENTIFIED, not a percentage: the posterior would still return one, and it
would be the least-bad corner of the prior rather than a measurement.

Also runs the one external check available without ground truth: algorithmic
participation in BTC grew substantially over 2016-2026, so an estimator that
is measuring anything real should trend upward. A flat or noisy p2-hat series
is evidence against the estimate, not a neutral result.
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from btc_data import load, windows
from inference import ABCPosterior
from summaries import FEATURE_NAMES, summary_vector

warnings.filterwarnings("ignore")
RESULTS = Path(__file__).resolve().parents[1] / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=None, help="npz bank from run_estimators")
    ap.add_argument("--window", type=int, default=2000)
    ap.add_argument("--regime", default="wide")
    args = ap.parse_args()

    bank_path = Path(args.bank) if args.bank else (
        RESULTS / f"bank_{args.regime}_T{args.window}.npz")
    z = np.load(bank_path)
    S, p2 = z["S"], z["theta_p2"]
    print(f"bank {bank_path.name}: {len(S)} draws, "
          f"p2 prior [{p2.min():.2f}, {p2.max():.2f}]")

    abc = ABCPosterior(S, p2, accept_frac=0.02)

    # null distribution of the support distance, from the bank against itself
    rng = np.random.default_rng(0)
    idx = rng.choice(len(abc.raw), min(600, len(abc.raw)), replace=False)
    d_null = abc.support_distance(abc.raw[idx])
    gate = float(np.percentile(d_null, 99))
    print(f"support-distance null: median {np.median(d_null):.4f}, "
          f"99th pct {gate:.4f}  <- gate")

    ts, r = load()
    wins = windows(ts, r, args.window)
    print(f"{len(wins)} gap-free BTC windows of {args.window} hourly returns\n")

    rows = []
    print(f"{'window':10s} {'end':10s} {'support d':>10s} {'gate':>7s} "
          f"{'p2 median':>10s} {'90% interval':>18s}   status")
    for w in wins:
        x = np.array([summary_vector(w["returns"])[k] for k in FEATURE_NAMES])
        d = float(abc.support_distance(x[None, :])[0])
        inside = d <= gate
        post = abc.posterior(x)
        status = "estimated" if inside else "NOT_IDENTIFIED (out of model reach)"
        rows.append({
            "start": w["start"], "end": w["end"], "label": w["label"],
            "support_distance": d, "gate": gate, "within_model_reach": inside,
            "p2_median": post["median"], "p2_q05": post["q05"],
            "p2_q95": post["q95"],
            "summary": dict(zip(FEATURE_NAMES, x.tolist())),
        })
        end = datetime.fromtimestamp(w["end"], timezone.utc).strftime("%Y-%m")
        print(f"{w['label']:10s} {end:10s} {d:10.4f} {gate:7.4f} "
              f"{post['median']:10.3f} [{post['q05']:7.3f},{post['q95']:7.3f}]"
              f"   {status}")

    n_in = sum(r_["within_model_reach"] for r_ in rows)
    print(f"\n{n_in}/{len(rows)} windows inside the model's reachable set")

    verdict = {"windows_within_reach": n_in, "windows_total": len(rows)}
    if n_in >= 3:
        t = np.array([r_["start"] for r_ in rows if r_["within_model_reach"]],
                     dtype=float)
        v = np.array([r_["p2_median"] for r_ in rows if r_["within_model_reach"]])
        t = (t - t.mean()) / t.std()
        slope = float(np.polyfit(t, v, 1)[0])
        # permutation test on the time trend
        perm = [abs(np.polyfit(t, rng.permutation(v), 1)[0]) for _ in range(5000)]
        verdict |= {"time_trend_slope_per_sd": slope,
                    "trend_p_value": float(np.mean(np.array(perm) >= abs(slope)))}
        print(f"time trend of p2-hat: {slope:+.4f} per sd of calendar time "
              f"(permutation p = {verdict['trend_p_value']:.3f})")
    else:
        verdict["time_trend_slope_per_sd"] = None
        verdict["trend_p_value"] = None
        print("time trend not computed: too few windows survive the "
              "adequacy gate for a trend to mean anything.")

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "btc_estimates.json").write_text(json.dumps(
        {"bank": bank_path.name, "window": args.window,
         "verdict": verdict, "windows": rows}, indent=1))
    print(f"\nwrote {RESULTS/'btc_estimates.json'}")


if __name__ == "__main__":
    main()
