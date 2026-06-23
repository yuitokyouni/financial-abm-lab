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
from abm_models.kronos_lob.bar_aggregator import closes_to_returns
from stylized_facts import stylized_facts_summary


def _sf_from_history(history) -> dict | None:
    closes = history["close"].to_numpy(dtype="float64")
    returns = closes_to_returns(closes)
    if returns.size < 4:
        return None
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    return stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)


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

    sf_market = _sf_from_history(res["history_market"])
    sf_mid = _sf_from_history(res["history_mid"])
    n_bars = int(len(res["history_market"]))
    return {
        "horizon": horizon, "dt": dt, "n_bars": n_bars,
        "sf_market": sf_market, "sf_mid": sf_mid,
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
        for src in ("market", "mid"):
            sf = res[f"sf_{src}"]
            if sf is None:
                continue
            print(f"  [{src:>6}] h={h} dt={res['dt']:.1f}s bars={res['n_bars']}  "
                  f"Hill α={sf['hill_alpha']:.3f} "
                  f"ret_acf[1]={sf['ret_acf'].get(1, float('nan')):+.4f} "
                  f"vol_acf[50]={sf['vol_acf'].get(50, float('nan')):+.4f}")

    print("\n[YH007-4 ablation summary — market vs mid]")
    print(f"  {'horizon':>8} {'bars':>6}  "
          f"{'Hill_m':>8} {'Hill_mid':>9}  "
          f"{'ret1_m':>9} {'ret1_mid':>10}  "
          f"{'vol50_m':>10} {'vol50_mid':>11}")
    for r in rows:
        sm, sd = r["sf_market"], r["sf_mid"]
        if sm is None or sd is None:
            print(f"  {r['horizon']:>8} {r['n_bars']:>6}  (returns too short)")
            continue
        print(f"  {r['horizon']:>8} {r['n_bars']:>6}  "
              f"{sm['hill_alpha']:>+8.3f} {sd['hill_alpha']:>+9.3f}  "
              f"{sm['ret_acf'].get(1, float('nan')):>+9.4f} "
              f"{sd['ret_acf'].get(1, float('nan')):>+10.4f}  "
              f"{sm['vol_acf'].get(50, float('nan')):>+10.4f} "
              f"{sd['vol_acf'].get(50, float('nan')):>+11.4f}")
    import json
    out_path = f"/tmp/yh007_4_ablation_{args.backend}_seed{args.seed}.json"
    with open(out_path, "w") as f:
        json.dump([{"horizon": r["horizon"], "n_bars": r["n_bars"],
                    "sf_market": r["sf_market"], "sf_mid": r["sf_mid"]} for r in rows],
                  f, default=str)
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
