"""YH007-1 — aggregate (板無し即時 clearing) で Kronos shared signal + 2 readings を回す。

spec 002 §5 (YH007-1) の最小実装の experiment ラッパー。core を import するだけ。

実行 (mock signal):
    uv run python -m experiments.speculation_game.yh007_1_aggregate --backend mock

実行 (実 Kronos, 閉ループ; KRONOS_PATH 必須):
    KRONOS_PATH=/path/to/Kronos \\
      uv run python -m experiments.speculation_game.yh007_1_aggregate --backend kronos --n-steps 30
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from abm_models.kronos_aggregate import (
    KronosAggregateMarket,
    constant_signal_provider,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "kronos"], default="mock")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-trend", type=int, default=25)
    p.add_argument("--n-fade", type=int, default=25)
    p.add_argument("--n-warmup", type=int, default=128)
    p.add_argument("--n-steps", type=int, default=200)
    p.add_argument("--kappa", type=float, default=0.001)
    p.add_argument("--initial-price", type=float, default=100.0)
    p.add_argument("--mock-pred", type=float, default=100.5,
                   help="mock backend: 固定 pred_close_mean (last_close 比で drift を決める)")
    p.add_argument("--kronos-lookback", type=int, default=128)
    p.add_argument("--kronos-sample-count", type=int, default=1)
    args = p.parse_args()

    if args.backend == "mock":
        provider = constant_signal_provider(pred_close_mean=args.mock_pred, pred_close_std=1.0)
    else:
        from abm_models.kronos_aggregate.kronos_signal import make_kronos_signal_provider
        provider = make_kronos_signal_provider(
            lookback=args.kronos_lookback,
            sample_count=args.kronos_sample_count,
        )

    market = KronosAggregateMarket(
        signal_provider=provider,
        n_trend=args.n_trend, n_fade=args.n_fade,
        kappa=args.kappa,
        n_warmup=args.n_warmup, n_steps=args.n_steps,
        initial_price=args.initial_price,
    )

    t0 = time.time()
    res = market.run(seed=args.seed)
    dt = time.time() - t0

    prices = res["prices"]
    returns = res["returns"]
    actions = res["actions"]
    drift = res["drift"]

    n_trend, n_fade = res["n_trend"], res["n_fade"]
    trend_actions = actions[:, :n_trend]
    fade_actions = actions[:, n_trend:]
    excess = actions.sum(axis=1)

    print(f"[yh007-1/{args.backend}] seed={args.seed}  steps={args.n_steps}  "
          f"warmup={args.n_warmup}  N={n_trend}+{n_fade}  dt={dt:.2f}s")
    print(f"  price : start={prices[0]:.4f}  end={prices[-1]:.4f}  "
          f"min={prices.min():.4f}  max={prices.max():.4f}")
    print(f"  return: mean={returns.mean():+.5e}  std={returns.std():.5e}  "
          f"|r|_max={np.abs(returns).max():.5e}")
    print(f"  drift : mean={drift.mean():+.4f}  >0 frac={(drift > 0).mean():.3f}  "
          f"<0 frac={(drift < 0).mean():.3f}")
    print(f"  excess: mean={excess.mean():+.2f}  max={excess.max():+d}  min={excess.min():+d}")
    print(f"  split : trend mean action={trend_actions.mean():+.3f}  "
          f"fade mean action={fade_actions.mean():+.3f} "
          f"(逆符号なら ① alpha 生成相互作用 ✓)")


if __name__ == "__main__":
    main()
