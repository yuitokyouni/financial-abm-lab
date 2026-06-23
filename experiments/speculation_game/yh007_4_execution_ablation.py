"""YH007-4 — 執行層 ablation: execution_horizon ∈ {1, 5, 10, ...} で SF がどう動くか。

spec §5 YH007-4: 執行層 (機構 2) を on/off。Bouchaud 仮説 = 大口 parent 分割執行 →
符号付きフロー自己相関 → vol clustering 寄与。execution_horizon=1 は YH007-3 と等価
(pass-through), >1 で TWAP-like 分割。

実行 (mock, adaptive 構成で 3 horizon を比較):
    uv run python -m experiments.speculation_game.yh007_4_execution_ablation --horizons 1 5 10

実行 (実 Kronos, 重い):
    KRONOS_PATH=/path/to/Kronos \\
      uv run python -m experiments.speculation_game.yh007_4_execution_ablation \\
      --backend kronos --horizons 1 5 --warmup-steps 100 --main-steps 300 --bar-size 10 --lookback-bars 16
"""
from __future__ import annotations

import argparse
import time
from typing import List

import numpy as np

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket
from stylized_facts import stylized_facts_summary


def _summarize_one(
    horizon: int, *, backend: str, seed: int, warmup_steps: int, main_steps: int,
    n_adaptive: int, n_fcn: int, bar_size: int, lookback_bars: int,
    score_window: int, kronos_sample_count: int, initial_price: float, mock_pred: float,
) -> dict:
    if backend == "mock":
        provider = constant_signal_provider(pred_close_mean=mock_pred, pred_close_std=1.0)
    else:
        from abm_models.kronos_aggregate.kronos_signal import make_kronos_signal_provider
        provider = make_kronos_signal_provider(lookback=lookback_bars, sample_count=kronos_sample_count)

    model = KronosLOBMarket(
        signal_provider=provider,
        warmup_steps=warmup_steps, main_steps=main_steps,
        n_trend=0, n_fade=0, n_fcn=n_fcn, n_adaptive=n_adaptive,
        bar_size=bar_size, lookback_bars=lookback_bars,
        order_volume=1, initial_market_price=initial_price,
        score_window=score_window, execution_horizon=horizon,
    )
    t0 = time.time()
    res = model.run(seed=seed)
    dt = time.time() - t0

    prices = res["prices"]
    returns = res["returns"]
    if returns.size < 4:
        return {"horizon": horizon, "dt": dt, "n_bars": int(prices.size), "sf": None}

    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    sf = stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)
    return {
        "horizon": horizon, "dt": dt, "n_bars": int(prices.size),
        "p_start": float(prices[0]), "p_end": float(prices[-1]),
        "sf": sf,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "kronos"], default="mock")
    p.add_argument("--seed", type=int, default=777)
    p.add_argument("--horizons", type=int, nargs="+", default=[1, 5, 10])
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1200)
    p.add_argument("--n-adaptive", type=int, default=30)
    p.add_argument("--n-fcn", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=16)
    p.add_argument("--score-window", type=int, default=50)
    p.add_argument("--initial-price", type=float, default=300.0)
    p.add_argument("--mock-pred", type=float, default=300.6)
    p.add_argument("--kronos-sample-count", type=int, default=1)
    args = p.parse_args()

    rows = []
    for h in args.horizons:
        print(f"\n[yh007-4/{args.backend}] horizon={h} start ...", flush=True)
        res = _summarize_one(
            h, backend=args.backend, seed=args.seed,
            warmup_steps=args.warmup_steps, main_steps=args.main_steps,
            n_adaptive=args.n_adaptive, n_fcn=args.n_fcn,
            bar_size=args.bar_size, lookback_bars=args.lookback_bars,
            score_window=args.score_window,
            kronos_sample_count=args.kronos_sample_count,
            initial_price=args.initial_price, mock_pred=args.mock_pred,
        )
        rows.append(res)
        sf = res["sf"]
        if sf is None:
            print(f"  horizon={h}: returns too short")
            continue
        print(f"  horizon={h} dt={res['dt']:.1f}s bars={res['n_bars']}  "
              f"p {res['p_start']:.4f}→{res['p_end']:.4f}")
        print(f"    Hill α={sf['hill_alpha']:.3f}  std={sf['std']:.4e}")
        print(f"    ret_acf τ=1: {sf['ret_acf'].get(1, float('nan')):+.4f}  "
              f"ret_acf τ=50: {sf['ret_acf'].get(50, float('nan')):+.4f}")
        print(f"    vol_acf τ=1: {sf['vol_acf'].get(1, float('nan')):+.4f}  "
              f"vol_acf τ=50: {sf['vol_acf'].get(50, float('nan')):+.4f}")

    print("\n[YH007-4 ablation summary]")
    print(f"  {'horizon':>8} {'bars':>6} {'Hill α':>8} {'ret_acf[1]':>11} {'vol_acf[1]':>11} {'vol_acf[50]':>12}")
    for r in rows:
        sf = r["sf"]
        if sf is None:
            print(f"  {r['horizon']:>8} {r['n_bars']:>6}  (returns too short)")
            continue
        print(f"  {r['horizon']:>8} {r['n_bars']:>6} {sf['hill_alpha']:>+8.3f} "
              f"{sf['ret_acf'].get(1, float('nan')):>+11.4f} "
              f"{sf['vol_acf'].get(1, float('nan')):>+11.4f} "
              f"{sf['vol_acf'].get(50, float('nan')):>+12.4f}")
    print("\n  期待 (Bouchaud 仮説): horizon ↑ → vol_acf τ=50 ↑ (vol clustering 強化)")


if __name__ == "__main__":
    main()
