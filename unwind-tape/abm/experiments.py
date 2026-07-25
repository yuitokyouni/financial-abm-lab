"""Experiment drivers (sweeps 1-4).

Each experiment fixes every treatment variable at baseline and sweeps exactly
one. Every condition is averaged over M seeds. Drivers return
``(rows, summary)``:

  - ``rows``   : one dict per (condition, seed)  -> per-seed detail CSV
  - ``summary``: one dict per condition (seed means) -> plot-ready CSV

Analysis helpers (log-log delta fit for exp1) live here too. numpy only.
"""

from __future__ import annotations

import numpy as np

from .config import baseline
from .market import Market

# --- sweep grids (baseline everywhere else) -------------------------------
EXP1_QOVER_V = [0.5, 1, 2, 5, 10, 20, 50, 100]
EXP2_BUYBACK = [0.0, 0.1, 0.22, 0.4]
EXP3_DRIFT = [-0.06, -0.03, 0.0, 0.03, 0.06]
EXP4_INFO = [False, True]


def loglog_fit(x, y):
    """Fit ln(y) = delta*ln(x) + c by least squares. Returns (delta, c, r2).

    Points with non-positive x or y are dropped (log undefined). ``delta`` is
    the impact exponent; delta = 0.5 is the square-root law.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = (x > 0) & (y > 0)
    x, y = x[mask], y[mask]
    if len(x) < 2:
        return float("nan"), float("nan"), float("nan")
    lx, ly = np.log(x), np.log(y)
    A = np.vstack([lx, np.ones_like(lx)]).T
    (delta, c), *_ = np.linalg.lstsq(A, ly, rcond=None)
    pred = delta * lx + c
    ss_res = float(np.sum((ly - pred) ** 2))
    ss_tot = float(np.sum((ly - ly.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(delta), float(c), float(r2)


def _mean(rows, key):
    vals = [r[key] for r in rows]
    return float(np.mean(vals)) if vals else float("nan")


def _summarize(cond_rows, cond_value_key, cond_value):
    """Collapse per-seed rows of one condition into a seed-mean summary dict."""
    out = {cond_value_key: cond_value, "n_seeds": len(cond_rows)}
    for k in ("s1", "s2", "s3", "IS", "sigma", "Q", "V", "seller_filled"):
        out[k + "_mean"] = _mean(cond_rows, k)
    for k in ("s2", "IS"):
        out[k + "_std"] = float(np.std([r[k] for r in cond_rows])) if cond_rows else float("nan")
    return out


def _run_condition(cfg, seeds, **overrides):
    """Run one treatment condition across all seeds; return per-seed rows."""
    m = Market(cfg)
    params = {
        "Qover_V": overrides.get("Qover_V", cfg.default_Qover_V),
        "W": overrides.get("W", cfg.default_W),
        "announce_info": overrides.get("announce_info", cfg.default_announce_info),
        "buyback_ratio": overrides.get("buyback_ratio", cfg.default_buyback_ratio),
        "mkt_drift": overrides.get("mkt_drift", cfg.default_mkt_drift),
    }
    rows = []
    for seed in seeds:
        rows.append(m.run_event(seed=seed, **params))
    return rows


# --- experiment 1: size effect --------------------------------------------
def exp1(seeds, grid=None, cfg=None, verbose=True):
    """Sweep Q/V; fit IS ~ (Q/V)^delta by log-log regression (delta=0.5 = sqrt)."""
    cfg = cfg or baseline()
    grid = grid or EXP1_QOVER_V
    rows, summary = [], []
    for q in grid:
        cr = _run_condition(cfg, seeds, Qover_V=q)
        rows.extend(cr)
        s = _summarize(cr, "Qover_V", q)
        summary.append(s)
        if verbose:
            print(f"  Q/V={q:>6}: IS_mean={s['IS_mean']:+.5f}  "
                  f"s3_mean={s['s3_mean']:+.5f}  sigma={s['sigma_mean']:.5f}")
    delta, c, r2 = loglog_fit([s["Qover_V"] for s in summary],
                              [s["IS_mean"] for s in summary])
    if verbose:
        print(f"  log-log fit: delta={delta:.3f}  R2={r2:.3f}  "
              f"(delta=0.5 is the square-root law)")
    meta = {"delta": delta, "intercept": c, "r2": r2}
    return rows, summary, meta


# --- experiment 2: buyback -------------------------------------------------
def exp2(seeds, grid=None, cfg=None, verbose=True):
    """Sweep buyback_ratio at Q/V=15; report IS(beta=0) - IS(beta=0.22)."""
    cfg = cfg or baseline()
    grid = grid or EXP2_BUYBACK
    rows, summary = [], []
    by_beta = {}
    for beta in grid:
        cr = _run_condition(cfg, seeds, buyback_ratio=beta)
        rows.extend(cr)
        s = _summarize(cr, "buyback_ratio", beta)
        summary.append(s)
        by_beta[beta] = s["IS_mean"]
        if verbose:
            print(f"  beta={beta:>4}: IS_mean={s['IS_mean']:+.5f}  s3_mean={s['s3_mean']:+.5f}")
    diff = None
    if 0.0 in by_beta and 0.22 in by_beta:
        diff = by_beta[0.0] - by_beta[0.22]
        if verbose:
            print(f"  IS(beta=0) - IS(beta=0.22) = {diff:+.5f}")
    meta = {"IS_diff_0_vs_0.22": diff}
    return rows, summary, meta


# --- experiment 3: market drift -------------------------------------------
def exp3(seeds, grid=None, cfg=None, verbose=True):
    """Sweep mkt_drift at Q/V=15; show how IS moves with the market backdrop."""
    cfg = cfg or baseline()
    grid = grid or EXP3_DRIFT
    rows, summary = [], []
    for mu in grid:
        cr = _run_condition(cfg, seeds, mkt_drift=mu)
        rows.extend(cr)
        s = _summarize(cr, "mkt_drift", mu)
        summary.append(s)
        if verbose:
            print(f"  mu={mu:+.3f}: IS_mean={s['IS_mean']:+.5f}  s2_mean={s['s2_mean']:+.5f}")
    meta = {}
    return rows, summary, meta


# --- experiment 4: information (s2) ---------------------------------------
def exp4(seeds, grid=None, cfg=None, verbose=True):
    """Toggle announce_info at Q/V=15; report the s2 (front-running) premium."""
    cfg = cfg or baseline()
    grid = grid or EXP4_INFO
    rows, summary = [], []
    by_info = {}
    for info in grid:
        cr = _run_condition(cfg, seeds, announce_info=info)
        rows.extend(cr)
        s = _summarize(cr, "announce_info", info)
        summary.append(s)
        by_info[info] = s
        if verbose:
            print(f"  announce_info={str(info):>5}: s1={s['s1_mean']:+.5f}  "
                  f"s2={s['s2_mean']:+.5f}  IS={s['IS_mean']:+.5f}")
    diff = None
    if True in by_info and False in by_info:
        diff = by_info[True]["s2_mean"] - by_info[False]["s2_mean"]
        if verbose:
            print(f"  s2(info ON) - s2(info OFF) = {diff:+.5f}  (front-running premium)")
    meta = {"s2_premium_on_minus_off": diff}
    return rows, summary, meta
