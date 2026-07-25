"""Block-into-state experiment (YH009 ABM, emergence arm).

Question this answers -- the one an ABM is *uniquely* able to answer:

    Take the SAME market world at the SAME instant. Walk a large sell block into
    it, or don't. How does the block change the subsequent path, and does that
    change depend on the market's *state* at the moment of injection?

In real data the counterfactual ("what would Furukawa have done without the
block") is never observable. The model is deterministic in its seed, so we
snapshot the market at t*, run TWO continuations from that identical snapshot
(same rng stream) -- one with the block, one without -- and the difference is the
block's *pure causal effect* on that path. Over many endogenous states this
isolates STATE dependence, not size (the block is held fixed).

The cascade channel is the MomentumTaker population (agents.py): it crosses the
spread on momentum with no inventory brake, so a block that flips the momentum
sign can tip a self-feeding cascade -- or, in a strong young up-trend, get
absorbed while price keeps rising. Both outcomes from one rule; the pre-injection
state is meant to separate them. Whether it actually does is the open question
this harness measures (it does NOT assume the answer).

Speed: the agent population is immutable after construction, so we snapshot only
the *mutable* market state (book, inventory, rng, history) and share the agents
-- ~100x cheaper than deepcopy, which makes thousands of paired probes feasible.

numpy only. Run: ``python3 -m abm.regime`` (from unwind-tape/).
"""
from __future__ import annotations

import argparse
import copy
import csv
import math
from pathlib import Path

import numpy as np

from .agents import MomentumTaker
from .config import regime_variant
from .market import Market

FEATURES = ["mom_s", "mom_l", "gap_s", "gap_l", "vol", "taker_inv"]


def _measure_state(m: Market) -> dict:
    """Battery of pre-injection state features (history/inventory only, no lookahead).

    mom_s/mom_l : short/long trend return (direction + strength)
    gap_s/gap_l : short/long deviation from the moving-average price (overextension)
    vol         : local realised volatility
    taker_inv   : net momentum-taker inventory / (V*400) -- how loaded the amplifier is
    """
    mids, rets, mid = m._mid_hist, m._ret_hist, m.mid

    def ret_over(k):
        return math.log(mid / mids[-k]) if len(mids) > k and mids[-k] > 0 else 0.0

    def gap(w):
        win = mids[-w:] if len(mids) >= 2 else mids
        ma = sum(win) / len(win) if win else mid
        return (mid - ma) / ma if ma > 0 else 0.0

    def vol(k):
        rk = rets[-k:]
        return float(np.std(rk)) if len(rk) > 1 else 0.0

    tinv = sum(m.inventory.get(a.agent_id, 0.0)
               for a in m.agents if isinstance(a, MomentumTaker))
    tinv_n = tinv / (m.V * 400.0) if m.V else 0.0
    return {"mom_s": ret_over(50), "mom_l": ret_over(200),
            "gap_s": gap(100), "gap_l": gap(400), "vol": vol(100),
            "taker_inv": tinv_n}


def _snapshot(m: Market) -> dict:
    """Copy only the MUTABLE market state; agents/config are shared (immutable)."""
    return {"book": copy.deepcopy(m.book), "inv": dict(m.inventory),
            "rng": copy.deepcopy(m.rng), "mh": list(m._mid_hist),
            "rh": list(m._ret_hist), "log_v": m.log_v,
            "last": m.last_price, "phase": m.phase}


def _restore(m: Market, s: dict) -> None:
    m.book = copy.deepcopy(s["book"]); m.inventory = dict(s["inv"])
    m.rng = copy.deepcopy(s["rng"]); m._mid_hist = list(s["mh"])
    m._ret_hist = list(s["rh"]); m.log_v = s["log_v"]
    m.last_price = s["last"]; m.phase = s["phase"]


def _run_post(m: Market, steps: int, block: float = 0.0,
              n_slices: int = 30, slice_gap: int = 3):
    """Advance ``steps`` background steps, optionally walking a sell ``block`` as
    ``n_slices`` slices over the first ``n_slices*slice_gap`` steps. Returns
    (log return over the window, trough = min log price vs start)."""
    p0 = m.mid
    q_slice = block / n_slices if (block > 0 and n_slices > 0) else 0.0
    carry = 0.0; fired = 0; trough = 0.0
    for t in range(steps):
        if q_slice > 0.0 and fired < n_slices and t % slice_gap == 0:
            carry += q_slice
            q = int(carry); carry -= q
            if q > 0:
                m._market_order(-5, "sell", q)      # SELLER_AGENT_ID
            fired += 1
        m._base_step()
        if p0 > 0 and m.mid > 0:
            trough = min(trough, math.log(m.mid / p0))
    ret = math.log(m.mid / p0) if p0 > 0 and m.mid > 0 else 0.0
    return ret, trough


def _run_free(m: Market, steps: int) -> float:
    return _run_post(m, steps)[0]


def run_block_into_state(cfg=None, seeds=range(120), *, block_qov=15.0,
                         post_steps=150, n_probes=12, probe_gap=150,
                         warmup_extra=800, tip_drop=0.03, verbose=True):
    """Paired-counterfactual sweep of a fixed block across endogenous states.

    Per seed: warm up, free-run; at each of ``n_probes`` checkpoints measure the
    state battery, then run the paired (block / no-block) continuation from an
    identical snapshot (same rng). ``tipped`` = the block deepened the trough by
    more than ``tip_drop`` (block-attributable drawdown). The base market keeps
    free-running unperturbed between probes.
    """
    cfg = cfg or regime_variant()
    rows = []
    for seed in seeds:
        m = Market(cfg); m._reset(seed); m.warmup()
        _run_free(m, warmup_extra)
        block = int(round(block_qov * m.V * post_steps))
        for _ in range(n_probes):
            _run_free(m, probe_gap)
            st = _measure_state(m)
            snap = _snapshot(m)
            ret_no, tr_no = _run_post(m, post_steps)              # no-block arm
            _restore(m, snap)                                     # same rng state
            ret_blk, tr_blk = _run_post(m, post_steps, block=block)
            _restore(m, snap)                                     # base continues clean
            rows.append({"seed": seed, "block": block, **st,
                         "ret_no": ret_no, "ret_blk": ret_blk,
                         "delta": ret_blk - ret_no,
                         "trough_no": tr_no, "trough_blk": tr_blk,
                         "tipped": 1 if (tr_blk - tr_no) < -tip_drop else 0})
    if verbose:
        _report(rows, block_qov)
    return rows


def _corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _report(rows, block_qov):
    d = np.array([r["delta"] for r in rows])
    tip = np.array([r["tipped"] for r in rows], float)
    X = np.array([[r[f] for f in FEATURES] for r in rows], float)
    print(f"\nn={len(rows)}  block Q/V={block_qov}  tip-rate={tip.mean():.0%}  "
          f"delta[min={d.min():+.3f} max={d.max():+.3f} sd={d.std():.3f}]")
    print("  feature      corr(,delta)  corr(,tipped)   tip% lo-tercile -> hi-tercile")
    for j, f in enumerate(FEATURES):
        x = X[:, j]
        o = np.argsort(x); n = len(o)
        lo = tip[o[:n // 3]].mean(); hi = tip[o[2 * n // 3:]].mean()
        print(f"  {f:<11} {_corr(x, d):>+9.3f}    {_corr(x, tip):>+9.3f}      "
              f"{lo:>5.0%} -> {hi:>4.0%}")
    # multivariate linear predictability of delta from the whole battery
    A = np.hstack([X, np.ones((len(X), 1))])
    coef, *_ = np.linalg.lstsq(A, d, rcond=None)
    pred = A @ coef
    r2 = 1 - np.sum((d - pred) ** 2) / np.sum((d - d.mean()) ** 2) if np.std(d) > 0 else float("nan")
    print(f"  --> multivariate R^2 (delta ~ all 6 features) = {r2:.3f}  "
          f"(near 0 = state does not predict = path-chaotic)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=120)
    ap.add_argument("--probes", type=int, default=12)
    ap.add_argument("--block-qov", type=float, default=15.0)
    ap.add_argument("--post-steps", type=int, default=150)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rows = run_block_into_state(seeds=range(a.seeds), block_qov=a.block_qov,
                                post_steps=a.post_steps, n_probes=a.probes)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nwrote {a.out}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
