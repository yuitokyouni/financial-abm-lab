"""Block-into-state experiment (YH009 ABM, emergence arm).

Question this answers -- the one an ABM is *uniquely* able to answer:

    Take the SAME market world at the SAME instant. Drop a large sell block into
    it, or don't. How does the block change the subsequent path, and does that
    change depend on the market's *state* at the moment of injection?

In real data the counterfactual ("what would Furukawa have done without the
block") is never observable. Here the model is deterministic in its seed, so we
snapshot the market at t*, run TWO continuations from that identical snapshot
(same rng stream) -- one with the block, one without -- and the difference is the
block's *pure causal effect* on that path. Averaging paired deltas over many
endogenous states isolates STATE dependence, not size (the block is held fixed).

This is the emergence arm: the cascade is the FCN chartists (g2) chasing the
block-induced drop, withdrawing bids, amplifying. Whether it *tips* is
path/state dependent -- which is exactly why a fixed-size block gives R^2~=0
against realised cost in the tape. No predators, no announcement, no injected
drop: just a block hitting a running market in different states.

State at t* (measured from pre-injection info only -- no lookahead):
  * ``r_pre``   : log return over the last ``k`` steps  (trend direction+strength)
  * ``ma_gap``  : (mid - MA_price)/MA_price over ``ma_win``  (overextension / 伸び切り)
  * ``vol_pre`` : std of the last ``k`` per-step returns    (local fragility)

Outcome:
  * ``ret_no``  : post-window return WITHOUT the block (the counterfactual)
  * ``ret_blk`` : post-window return WITH the block
  * ``delta``   : ret_blk - ret_no  = causal effect of the block on the path
                  (delta ~ 0  -> absorbed;  delta << 0 -> cascade)

numpy only. Run: ``python3 -m abm.regime`` (from unwind-tape/).
"""
from __future__ import annotations

import argparse
import copy
import csv
import math
from pathlib import Path

import numpy as np

from .config import baseline, regime_variant
from .market import Market


def _measure_state(m: Market, k: int, ma_win: int) -> dict:
    """State at the current instant, from history only (no lookahead)."""
    mids = m._mid_hist
    rets = m._ret_hist
    mid = m.mid
    r_pre = math.log(mid / mids[-k]) if len(mids) > k and mids[-k] > 0 else 0.0
    win = mids[-ma_win:] if len(mids) >= 2 else mids
    ma = sum(win) / len(win) if win else mid
    ma_gap = (mid - ma) / ma if ma > 0 else 0.0
    rk = rets[-k:]
    vol_pre = float(np.std(rk)) if len(rk) > 1 else 0.0
    return {"r_pre": r_pre, "ma_gap": ma_gap, "vol_pre": vol_pre}


def _run_free(m: Market, steps: int) -> float:
    """Advance ``steps`` background steps; return the log price change over them."""
    return _run_post(m, steps)


def _run_post(m: Market, steps: int, block: float = 0.0,
              n_slices: int = 30, slice_gap: int = 3) -> float:
    """Advance ``steps`` background steps, optionally executing a sell ``block``
    as ``n_slices`` slices over the first ``n_slices*slice_gap`` steps.

    A block must WALK replenishing liquidity over time (like a real offering /
    run_event's unannounced arm), not dump instantly -- an instant market order
    discards everything past the thin resting book, so size stops mattering.
    The background steps are identical to the no-block arm (same rng), so the
    sliced sells are the only difference -> the paired delta is the block's
    causal effect and now scales with block size.
    """
    p0 = m.mid
    q_slice = block / n_slices if (block > 0 and n_slices > 0) else 0.0
    carry = 0.0
    fired = 0
    for t in range(steps):
        if q_slice > 0.0 and fired < n_slices and t % slice_gap == 0:
            carry += q_slice
            q = int(carry)
            carry -= q
            if q > 0:
                m._market_order(-5, "sell", q)      # SELLER_AGENT_ID
            fired += 1
        m._base_step()
    return math.log(m.mid / p0) if p0 > 0 and m.mid > 0 else 0.0


def run_block_into_state(cfg=None, seeds=range(40), *, block_qov=8.0,
                         post_steps=400, k=200, ma_win=400,
                         n_probes=12, probe_gap=180, warmup_extra=600,
                         verbose=True):
    """Paired-counterfactual sweep of a fixed block across endogenous states.

    For each seed: warm up, then free-run; at ``n_probes`` checkpoints spaced
    ``probe_gap`` apart, measure the state and run the paired (block / no-block)
    continuation from an identical deepcopy snapshot. The base market keeps
    free-running unperturbed (the probes are isolated side-branches).
    """
    cfg = cfg or regime_variant()
    rows = []
    for seed in seeds:
        m = Market(cfg)
        m._reset(seed)
        m.warmup()
        # a little extra free run so the state isn't always "just off fundamental"
        _run_free(m, warmup_extra)
        block = int(round(block_qov * m.V * post_steps))
        for _ in range(n_probes):
            _run_free(m, probe_gap)
            st = _measure_state(m, k, ma_win)
            # paired counterfactual from an identical snapshot (same rng state):
            # both arms run identical background steps; arm_blk also walks the
            # block as slices -> the sliced sells are the only difference.
            arm_no = copy.deepcopy(m)
            arm_blk = copy.deepcopy(m)
            ret_no = _run_post(arm_no, post_steps)
            ret_blk = _run_post(arm_blk, post_steps, block=block)
            rows.append({
                "seed": seed, "block": block,
                **st,
                "ret_no": ret_no, "ret_blk": ret_blk,
                "delta": ret_blk - ret_no,
            })
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
    rp = np.array([r["r_pre"] for r in rows])
    mg = np.array([r["ma_gap"] for r in rows])
    vp = np.array([r["vol_pre"] for r in rows])
    print(f"\nblock-into-state: n={len(rows)}  block Q/V(post)={block_qov}")
    print(f"  delta: mean={d.mean():+.4f}  sd={d.std():.4f}  "
          f"min={d.min():+.4f}  max={d.max():+.4f}")
    print(f"  state ranges: r_pre[{rp.min():+.3f},{rp.max():+.3f}] "
          f"ma_gap[{mg.min():+.3f},{mg.max():+.3f}] vol_pre[{vp.min():.4f},{vp.max():.4f}]")
    print(f"  corr(delta, r_pre) ={_corr(d, rp):+.3f}   "
          f"(-> up-momentum absorbs [+] or cascades [-]?)")
    print(f"  corr(delta, ma_gap)={_corr(d, mg):+.3f}   "
          f"(-> overextension deepens the block hit?)")
    print(f"  corr(delta, vol_pre)={_corr(d, vp):+.3f}")
    # terciles of overextension (伸び切り)
    print("\n  delta by ma_gap tercile (伸び切り度):")
    order = np.argsort(mg)
    for name, idx in (("低(縮)", order[:len(order)//3]),
                      ("中", order[len(order)//3:2*len(order)//3]),
                      ("高(伸び切り)", order[2*len(order)//3:])):
        dd = d[idx]
        print(f"    {name:<12} ma_gap~{mg[idx].mean():+.3f}  "
              f"delta mean={dd.mean():+.4f}  cascade率(delta<-0.02)={np.mean(dd < -0.02):.0%}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--block-qov", type=float, default=8.0)
    ap.add_argument("--post-steps", type=int, default=400)
    ap.add_argument("--probes", type=int, default=12)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    rows = run_block_into_state(seeds=range(a.seeds), block_qov=a.block_qov,
                                post_steps=a.post_steps, n_probes=a.probes)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {a.out}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
