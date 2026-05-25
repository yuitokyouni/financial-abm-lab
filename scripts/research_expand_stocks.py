#!/usr/bin/env python3
"""Research script: expand JPX 2014 treatment/control groups and re-derive DiD.

Goal: determine if more stocks can narrow CI95 enough to get at least one
conclusive fact (CI95 not crossing zero).
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np
import yfinance as yf
from prism.facts.estimators import FACT_REGISTRY, ESTIMATOR_VERSION

# ── Extended TOPIX 100 treatment group (stocks affected by 2014-01-14 tick change) ──
# These are large-cap TOPIX 100 constituents as of early 2014.
# The tick reduction applied to stocks priced > 3000 JPY.
EXTENDED_TREATMENT = [
    # Original 15
    "7203.T", "6758.T", "9984.T", "8306.T", "6501.T",
    "7267.T", "9432.T", "8058.T", "6902.T", "4502.T",
    "6301.T", "8031.T", "4503.T", "6752.T", "7751.T",
    # Additional TOPIX 100 large-cap
    "8316.T",  # SMFG
    "8411.T",  # Mizuho
    "6861.T",  # Keyence
    "6954.T",  # FANUC
    "6971.T",  # Kyocera
    "4901.T",  # Fujifilm
    "8766.T",  # Tokio Marine
    "8001.T",  # ITOCHU
    "6702.T",  # Fujitsu
    "5401.T",  # Nippon Steel
    "2502.T",  # Asahi Group
    "6503.T",  # Mitsubishi Electric
    "3382.T",  # Seven & i
    "4452.T",  # Kao
    "8802.T",  # Mitsubishi Estate
    "9020.T",  # JR East
    "9022.T",  # JR Central
    "7269.T",  # Suzuki Motor
    "8035.T",  # Tokyo Electron
    "6762.T",  # TDK
    "7741.T",  # HOYA
    "4507.T",  # Shionogi
    "8591.T",  # ORIX
    "4578.T",  # Otsuka Holdings
    "6326.T",  # Kubota
]

# Extended control group: mid-cap TSE stocks NOT in TOPIX 100 treatment
EXTENDED_CONTROL = [
    # Original 10
    "2914.T", "9433.T", "4661.T", "6367.T", "4568.T",
    "6594.T", "4063.T", "6273.T", "7974.T", "9983.T",
    # Additional non-TOPIX-100 mid-caps
    "6645.T",  # Omron
    "6479.T",  # Minebea Mitsumi
    "7272.T",  # Yamaha Motor
    "6869.T",  # Sysmex
    "4519.T",  # Chugai Pharma
    "9735.T",  # Secom
    "2413.T",  # M3
    "4911.T",  # Shiseido
    "6506.T",  # Yaskawa
    "7733.T",  # Olympus
]

EVENT_DATE = "2014-01-14"
PRE_START = "2013-01-14"  # 12 months pre (longer window for power)
PRE_END = "2014-01-13"
POST_START = "2014-01-14"
POST_END = "2015-01-14"  # 12 months post


def fetch_returns(tickers: list[str], start: str, end: str) -> tuple[np.ndarray, list[str]]:
    """Fetch log-returns, dropping stocks with >10% missing data."""
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if data.empty:
        return np.array([]), []

    if len(tickers) == 1:
        prices = data["Close"].values.reshape(-1, 1)
        valid = tickers
    else:
        prices = data["Close"].values.astype(np.float64)
        cols = list(data["Close"].columns)
        nan_frac = np.isnan(prices).mean(axis=0)
        keep = nan_frac < 0.1
        prices = prices[:, keep]
        valid = [cols[i] for i in range(len(cols)) if keep[i]]

    mask = ~np.isnan(prices).any(axis=1)
    prices = prices[mask]

    if len(prices) < 30:
        return np.array([]), []

    log_ret = np.diff(np.log(prices), axis=0)
    return log_ret, valid


def compute_stock_fact(returns_1d: np.ndarray, fact_id: str) -> float:
    """Compute a single fact for one stock's return series."""
    fn = FACT_REGISTRY[fact_id]
    result = fn(returns_1d)
    return result.value


def did_estimate(
    treat_pre: np.ndarray,
    treat_post: np.ndarray,
    ctrl_pre: np.ndarray,
    ctrl_post: np.ndarray,
    fact_id: str,
) -> tuple[float, tuple[float, float], int, int]:
    """Compute DiD estimate with bootstrap CI95 on stock-level estimates.

    Returns: (delta_hat, (ci_lo, ci_hi), n_treatment, n_control)
    """
    n_treat = treat_pre.shape[1]
    n_ctrl = ctrl_pre.shape[1]

    # Stock-level fact estimates
    treat_pre_facts = np.array([compute_stock_fact(treat_pre[:, i], fact_id) for i in range(n_treat)])
    treat_post_facts = np.array([compute_stock_fact(treat_post[:, i], fact_id) for i in range(n_treat)])
    ctrl_pre_facts = np.array([compute_stock_fact(ctrl_pre[:, i], fact_id) for i in range(n_ctrl)])
    ctrl_post_facts = np.array([compute_stock_fact(ctrl_post[:, i], fact_id) for i in range(n_ctrl)])

    # Remove NaN stocks
    treat_valid = ~(np.isnan(treat_pre_facts) | np.isnan(treat_post_facts))
    ctrl_valid = ~(np.isnan(ctrl_pre_facts) | np.isnan(ctrl_post_facts))

    treat_pre_f = treat_pre_facts[treat_valid]
    treat_post_f = treat_post_facts[treat_valid]
    ctrl_pre_f = ctrl_pre_facts[ctrl_valid]
    ctrl_post_f = ctrl_post_facts[ctrl_valid]

    n_t = len(treat_pre_f)
    n_c = len(ctrl_pre_f)

    if n_t < 3 or n_c < 3:
        return np.nan, (np.nan, np.nan), n_t, n_c

    # DiD: (treat_post - treat_pre) - (ctrl_post - ctrl_pre)
    treat_diff = treat_post_f - treat_pre_f
    ctrl_diff = ctrl_post_f - ctrl_pre_f
    delta_hat = float(np.mean(treat_diff) - np.mean(ctrl_diff))

    # Bootstrap CI95 (stock-level resampling)
    rng = np.random.default_rng(42)
    n_boot = 5000
    boot_deltas = np.empty(n_boot)
    for b in range(n_boot):
        t_idx = rng.integers(0, n_t, size=n_t)
        c_idx = rng.integers(0, n_c, size=n_c)
        boot_delta = np.mean(treat_diff[t_idx]) - np.mean(ctrl_diff[c_idx])
        boot_deltas[b] = boot_delta

    ci_lo = float(np.percentile(boot_deltas, 2.5))
    ci_hi = float(np.percentile(boot_deltas, 97.5))

    return delta_hat, (ci_lo, ci_hi), n_t, n_c


def main():
    print("=" * 70)
    print("JPX 2014 DiD re-derivation — expanded stock universe")
    print(f"Pre:  {PRE_START} to {PRE_END}")
    print(f"Post: {POST_START} to {POST_END}")
    print(f"Treatment candidates: {len(EXTENDED_TREATMENT)}")
    print(f"Control candidates:   {len(EXTENDED_CONTROL)}")
    print("=" * 70)

    # Fetch data
    print("\nFetching treatment pre-period...")
    t_pre, t_ids_pre = fetch_returns(EXTENDED_TREATMENT, PRE_START, PRE_END)
    print(f"  → {len(t_ids_pre)} stocks, {t_pre.shape[0] if len(t_pre) > 0 else 0} days")

    print("Fetching treatment post-period...")
    t_post, t_ids_post = fetch_returns(EXTENDED_TREATMENT, POST_START, POST_END)
    print(f"  → {len(t_ids_post)} stocks, {t_post.shape[0] if len(t_post) > 0 else 0} days")

    print("Fetching control pre-period...")
    c_pre, c_ids_pre = fetch_returns(EXTENDED_CONTROL, PRE_START, PRE_END)
    print(f"  → {len(c_ids_pre)} stocks, {c_pre.shape[0] if len(c_pre) > 0 else 0} days")

    print("Fetching control post-period...")
    c_post, c_ids_post = fetch_returns(EXTENDED_CONTROL, POST_START, POST_END)
    print(f"  → {len(c_ids_post)} stocks, {c_post.shape[0] if len(c_post) > 0 else 0} days")

    # Find stocks present in both periods
    treat_ids = sorted(set(t_ids_pre) & set(t_ids_post))
    ctrl_ids = sorted(set(c_ids_pre) & set(c_ids_post))
    print(f"\nStocks surviving both periods: {len(treat_ids)} treatment, {len(ctrl_ids)} control")

    if len(treat_ids) < 5 or len(ctrl_ids) < 3:
        print("ERROR: insufficient stocks")
        return

    # Align columns
    def select(ret, all_ids, keep_ids):
        idx = [all_ids.index(t) for t in keep_ids if t in all_ids]
        return ret[:, idx]

    tp = select(t_pre, t_ids_pre, treat_ids)
    tpo = select(t_post, t_ids_post, treat_ids)
    cp = select(c_pre, c_ids_pre, ctrl_ids)
    cpo = select(c_post, c_ids_post, ctrl_ids)

    # Run DiD for each fact
    facts = ["volatility_clustering", "leverage_effect", "gain_loss_asymmetry",
             "fat_tails", "abs_autocorrelation", "squared_return_acf"]

    print("\n" + "=" * 70)
    print(f"{'Fact':30s} {'delta_hat':>10s} {'CI95_lo':>10s} {'CI95_hi':>10s} {'Crosses 0?':>12s} {'N_t':>5s} {'N_c':>5s}")
    print("-" * 70)

    conclusive = 0
    results = {}
    for fid in facts:
        delta, ci, n_t, n_c = did_estimate(tp, tpo, cp, cpo, fid)
        crosses = "YES" if (ci[0] <= 0 <= ci[1]) else "NO"
        if crosses == "NO":
            conclusive += 1
        print(f"{fid:30s} {delta:+10.4f} {ci[0]:+10.4f} {ci[1]:+10.4f} {crosses:>12s} {n_t:5d} {n_c:5d}")
        results[fid] = {"delta_hat": delta, "ci95": list(ci), "n_treat": n_t, "n_ctrl": n_c}

    print("-" * 70)
    print(f"\nConclusive facts (CI95 excludes zero): {conclusive}/6")

    # Also try with original small sample for comparison
    print("\n\n" + "=" * 70)
    print("COMPARISON: Original 15+10 stocks with 6-month windows")
    print("=" * 70)

    orig_treat = [t for t in EXTENDED_TREATMENT[:15] if t in treat_ids]
    orig_ctrl = [t for t in EXTENDED_CONTROL[:10] if t in ctrl_ids]

    # Need to re-fetch with 6-month window for fair comparison
    from datetime import datetime, timedelta
    event = datetime(2014, 1, 14)
    pre6_start = (event - timedelta(days=180)).strftime("%Y-%m-%d")
    post6_end = (event + timedelta(days=180)).strftime("%Y-%m-%d")

    t_pre6, t_ids_pre6 = fetch_returns(EXTENDED_TREATMENT[:15], pre6_start, PRE_END)
    t_post6, t_ids_post6 = fetch_returns(EXTENDED_TREATMENT[:15], POST_START, post6_end)
    c_pre6, c_ids_pre6 = fetch_returns(EXTENDED_CONTROL[:10], pre6_start, PRE_END)
    c_post6, c_ids_post6 = fetch_returns(EXTENDED_CONTROL[:10], POST_START, post6_end)

    ot_ids = sorted(set(t_ids_pre6) & set(t_ids_post6))
    oc_ids = sorted(set(c_ids_pre6) & set(c_ids_post6))
    print(f"Original stocks surviving: {len(ot_ids)} treatment, {len(oc_ids)} control")

    otp = select(t_pre6, t_ids_pre6, ot_ids)
    otpo = select(t_post6, t_ids_post6, ot_ids)
    ocp = select(c_pre6, c_ids_pre6, oc_ids)
    ocpo = select(c_post6, c_ids_post6, oc_ids)

    print(f"\n{'Fact':30s} {'delta_hat':>10s} {'CI95_lo':>10s} {'CI95_hi':>10s} {'Crosses 0?':>12s}")
    print("-" * 70)
    for fid in facts:
        delta, ci, n_t, n_c = did_estimate(otp, otpo, ocp, ocpo, fid)
        crosses = "YES" if (ci[0] <= 0 <= ci[1]) else "NO"
        print(f"{fid:30s} {delta:+10.4f} {ci[0]:+10.4f} {ci[1]:+10.4f} {crosses:>12s}")

    return results


if __name__ == "__main__":
    main()
