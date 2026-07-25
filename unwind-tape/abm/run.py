"""CLI entry point for the ABM skeleton.

Usage (run from the ``unwind-tape/`` directory)::

    python -m abm.run smoke               # smoke test (proof the skeleton runs)
    python -m abm.run exp1 [--seeds N]    # size effect  + delta fit
    python -m abm.run exp2 [--seeds N]    # buyback
    python -m abm.run exp3 [--seeds N]    # market drift
    python -m abm.run exp4 [--seeds N]    # information (s2 premium)
    python -m abm.run all  [--seeds N]

Results are written to ``abm/out/<exp>_detail.csv`` (per-seed) and
``abm/out/<exp>_summary.csv`` (seed means). Seeds are ``range(seeds)`` so runs
are reproducible.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from . import experiments as X
from .config import baseline
from .market import Market

OUT_DIR = Path(__file__).parent / "out"


def _write_csv(path, rows):
    """Write a list of flat dicts to CSV (union of keys, stable order)."""
    if not rows:
        return
    keys = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path}  ({len(rows)} rows)")


def _seeds(n):
    return list(range(n))


# --------------------------------------------------------------------------
# Smoke test 1: closed-loop continuity (drop then partial mean reversion)
# --------------------------------------------------------------------------
def smoke_closed_loop(seed=0, shock_frac=0.5, settle_steps=1500):
    """Inject one mid-size sell in steady state; show drop then recovery.

    Proves the loop is closed: after a one-off liquidity shock the FCN
    fundamentalists absorb and price mean-reverts (partial recovery) with no
    further selling. The shock is sized as a fraction of standing bid depth so
    it reliably walks the book.
    """
    print("[smoke 1] closed-loop continuity (one-off sell -> drop -> recovery)")
    cfg = baseline()
    m = Market(cfg)
    m._reset(seed)
    m.warmup()
    p0 = m.mid
    bid_depth = sum(sum(o[2] for o in dq) for dq in m.book.bids.values())
    shock = max(int(shock_frac * bid_depth), 5)
    filled, vwap, _ = m.book.market_order("sell", shock)
    m._record_mid()
    p_after = m.mid
    for _ in range(settle_steps):
        m._base_step()
    p_settle = m.mid
    drop = (p_after - p0) / p0
    recov = (p_settle - p_after) / p0
    print(f"  V(per-step)={m.V:.3f}  bid_depth={bid_depth}  shock_sell={shock} shares  filled={filled}")
    print(f"  pre-shock mid   P0      = {p0:.4f}")
    print(f"  post-shock mid  P_after = {p_after:.4f}   drop = {drop*100:+.3f}%")
    print(f"  settled mid     P_settle= {p_settle:.4f}   move-from-trough = {recov*100:+.3f}%")
    if drop < 0 and recov > 0:
        frac = recov / (-drop) if drop != 0 else float("nan")
        print(f"  => price fell then recovered {frac*100:.1f}% of the drop "
              f"(mean reversion present).")
    else:
        print("  => NOTE: expected drop-then-recovery not observed; retune params.")
    return {"p0": p0, "p_after": p_after, "p_settle": p_settle,
            "drop": drop, "recovery": recov}


# --------------------------------------------------------------------------
# Smoke test 2: light exp1 (IS monotone in Q/V + delta)
# --------------------------------------------------------------------------
def smoke_exp1(n_seeds=20, grid=(1, 5, 20)):
    print(f"\n[smoke 2] light exp1: Q/V={list(grid)}, seeds={n_seeds}")
    rows, summary, meta = X.exp1(_seeds(n_seeds), grid=list(grid), verbose=True)
    xs = [s["IS_mean"] for s in summary]
    monotone = all(b >= a for a, b in zip(xs, xs[1:]))
    print(f"  IS_mean by Q/V: {[round(v, 5) for v in xs]}")
    print(f"  monotone increasing in Q/V: {monotone}")
    print(f"  delta_hat={meta['delta']:.3f}  R2={meta['r2']:.3f}")
    return rows, summary, meta, monotone


def cmd_smoke(args):
    smoke_closed_loop()
    smoke_exp1(n_seeds=args.seeds if args.seeds else 20)


def _run_exp(name, fn, args):
    n = args.seeds if args.seeds else 60
    print(f"[{name}] seeds={n}")
    rows, summary, meta = fn(_seeds(n))
    _write_csv(OUT_DIR / f"{name}_detail.csv", rows)
    _write_csv(OUT_DIR / f"{name}_summary.csv", summary)
    if meta:
        print(f"  meta: {meta}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="abm.run", description="ABM skeleton runner")
    p.add_argument("command",
                   choices=["smoke", "exp1", "exp2", "exp3", "exp4", "all"])
    p.add_argument("--seeds", type=int, default=0,
                   help="number of seeds (default: 20 for smoke, 60 for exps)")
    args = p.parse_args(argv)

    if args.command == "smoke":
        cmd_smoke(args)
        return
    table = {"exp1": X.exp1, "exp2": X.exp2, "exp3": X.exp3, "exp4": X.exp4}
    if args.command == "all":
        for name, fn in table.items():
            _run_exp(name, fn, args)
    else:
        _run_exp(args.command, table[args.command], args)


if __name__ == "__main__":
    main(sys.argv[1:])
