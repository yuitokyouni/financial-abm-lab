"""metrics.py -- disposition proxy, ATH asymmetry, and bootstrap distributions.

Everything is reported as a DISTRIBUTION (bootstrap), not a point estimate
(brief section 4 / Stage 1 requirement). Conventions:
  P(sell) is the group-normalized probe output (see model.ProbeModel).
  disposition_proxy = P(sell | gain) - P(sell | loss)        (>0 = human-like)
  ath_asymmetry     = P(sell | dropped_near) - P(sell | no_drop)  (>0 = human-like)
"""
from __future__ import annotations
import numpy as np


def bootstrap_mean_ci(values, n_resamples, seed, alpha=0.05):
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_resamples, len(v)))
    boot = v[idx].mean(axis=1)
    return {
        "mean": float(v.mean()),
        "lo": float(np.quantile(boot, alpha / 2)),
        "hi": float(np.quantile(boot, 1 - alpha / 2)),
        "boot_mean": float(boot.mean()),
        "boot_sd": float(boot.std()),
        "n": int(len(v)),
        "frac_positive": float((v > 0).mean()),
    }


def paired_diff_ci(diffs, n_resamples, seed, alpha=0.05):
    """Bootstrap CI for a paired difference (already per-pair diffs)."""
    return bootstrap_mean_ci(diffs, n_resamples, seed, alpha)


def marginal_disposition(random_records, p_sell_by_idx, n_resamples, seed):
    """Marginal P(sell|gain) vs P(sell|loss) over the random ensemble.
    p_sell_by_idx: list aligned with random_records (one P(sell) each)."""
    gain = [p for r, p in zip(random_records, p_sell_by_idx)
            if r["meta"]["gain_sign"] == "gain" and not np.isnan(p)]
    loss = [p for r, p in zip(random_records, p_sell_by_idx)
            if r["meta"]["gain_sign"] == "loss" and not np.isnan(p)]
    g = bootstrap_mean_ci(gain, n_resamples, seed)
    l = bootstrap_mean_ci(loss, n_resamples, seed + 1)
    # bootstrap the difference of independent groups
    rng = np.random.default_rng(seed + 2)
    ga, la = np.asarray(gain), np.asarray(loss)
    bg = ga[rng.integers(0, len(ga), (n_resamples, len(ga)))].mean(1)
    bl = la[rng.integers(0, len(la), (n_resamples, len(la)))].mean(1)
    d = bg - bl
    return {
        "p_sell_gain": g, "p_sell_loss": l,
        "disposition_proxy": {
            "mean": float(np.mean(ga) - np.mean(la)),
            "lo": float(np.quantile(d, 0.025)), "hi": float(np.quantile(d, 0.975)),
            "boot_sd": float(d.std()), "frac_positive": float((d > 0).mean()),
            "n_gain": len(gain), "n_loss": len(loss)},
    }


def paired_disposition(disp_pairs, p_gain, p_loss, n_resamples, seed):
    diffs = [pg - pl for pg, pl in zip(p_gain, p_loss)
             if not (np.isnan(pg) or np.isnan(pl))]
    return {"disposition_proxy_paired": paired_diff_ci(diffs, n_resamples, seed),
            "per_pair_diffs_summary": _summ(diffs)}


def paired_ath_asymmetry(ath_pairs, p_no_drop, p_dropped, n_resamples, seed):
    diffs = [pd - pn for pn, pd in zip(p_no_drop, p_dropped)
             if not (np.isnan(pn) or np.isnan(pd))]
    overall = paired_diff_ci(diffs, n_resamples, seed)
    # split by gain/loss context
    by = {}
    for sign in ("gain", "loss"):
        d = [pd - pn for r, pn, pd in zip(ath_pairs, p_no_drop, p_dropped)
             if r["meta"]["gain_sign"] == sign and not (np.isnan(pn) or np.isnan(pd))]
        by[sign] = paired_diff_ci(d, n_resamples, seed + 1)
    return {"ath_asymmetry": overall, "ath_asymmetry_by_sign": by,
            "per_pair_diffs_summary": _summ(diffs)}


def _summ(v):
    v = np.asarray([x for x in v if not np.isnan(x)], dtype=float)
    if len(v) == 0:
        return {}
    return {"mean": float(v.mean()), "median": float(np.median(v)),
            "sd": float(v.std()), "min": float(v.min()), "max": float(v.max()),
            "q10": float(np.quantile(v, .1)), "q90": float(np.quantile(v, .9))}
