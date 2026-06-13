"""σ/N/fee/c/dt の sweep を回し、結果＋per-run runtime を出力する。

runtime_sec の総和が実験B の grid 見積もり（B1 compute 予算）の入力になる。
有限 grid を回して必ず終了する（無限ループ無し）。

使用例:
  python scripts/run_sweep.py --lambda 5,10,15 --N 1,5,20 --fee 0,0.001 --seeds 4 --out results.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microstructure import SimConfig, run  # noqa: E402


def _floats(s: str) -> list[float]:
    return [float(x) for x in s.split(",") if x != ""]


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x != ""]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="実験A sweep harness")
    ap.add_argument("--n-periods", type=int, default=200000)
    ap.add_argument("--lambda", dest="lam", type=_floats, default=[10.0])
    ap.add_argument("--sigma", type=_floats, default=[0.0])
    ap.add_argument("--N", type=_ints, default=[1])
    ap.add_argument("--fee", type=_floats, default=[0.0])
    ap.add_argument("--c", type=_floats, default=[0.0])
    ap.add_argument("--dt", type=_floats, default=[1e-2])
    ap.add_argument("--alpha", type=float, default=0.4)
    ap.add_argument("--half-spread", type=float, default=0.1)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args(argv)

    rows = []
    total_runtime = 0.0
    for dt in args.dt:
        for lam in args.lam:
            for sigma in args.sigma:
                for N in args.N:
                    for fee in args.fee:
                        for c in args.c:
                            for seed in range(args.seeds):
                                cfg = SimConfig(
                                    n_periods=args.n_periods, seed=seed, dt=dt,
                                    sigma=sigma, lambda_jump=lam,
                                    alpha=args.alpha, half_spread=args.half_spread,
                                    mechanism="batch" if N > 1 else "continuous",
                                    batch_interval=N, fee=fee, opp_cost=c)
                                r = run(cfg)
                                total_runtime += r.runtime_sec
                                rows.append(dict(
                                    dt=dt, lam=lam, sigma=sigma, N=N, fee=fee, c=c,
                                    seed=seed,
                                    extraction=r.metrics.extraction,
                                    extraction_rate=r.extraction_rate,
                                    effective_spread=r.metrics.effective_spread,
                                    participation_margin=r.metrics.participation_margin,
                                    mm_exits=r.metrics.mm_exits,
                                    runtime_sec=r.runtime_sec))

    print(f"{len(rows)} runs, total_runtime={total_runtime:.2f}s "
          f"(B1 compute 入力), mean={total_runtime/max(len(rows),1):.4f}s/run")
    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
