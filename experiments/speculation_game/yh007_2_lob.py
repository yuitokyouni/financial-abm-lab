"""YH007-2 — PAMS CDA LOB + MMFCN + Kronos shared-signal × 2-reading の baseline。

spec 002 §5 YH007-2 / §8: bar_size 集約した close 列で SF (Hill α, vol_acf, ret_acf)
を計算。受け入れ基準は「fat tail / vol clustering / リターン無相関」が出るかの確認。
出なければ YH007-3 以降の機構で達成、出ればこの baseline 自体が成果。

実行 (mock signal, 高速):
    uv run python -m experiments.speculation_game.yh007_2_lob --backend mock --main-steps 2000

実行 (実 Kronos, 閉ループ; KRONOS_PATH 必須, 重い):
    KRONOS_PATH=/path/to/Kronos \\
      uv run python -m experiments.speculation_game.yh007_2_lob --backend kronos \\
      --warmup-steps 100 --main-steps 200 --bar-size 10 --lookback-bars 32
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket
from stylized_facts import stylized_facts_summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "kronos"], default="mock")
    p.add_argument("--seed", type=int, default=777)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=2000)
    p.add_argument("--n-trend", type=int, default=25)
    p.add_argument("--n-fade", type=int, default=25)
    p.add_argument("--n-fcn", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=32)
    p.add_argument("--order-volume", type=int, default=1)
    p.add_argument("--initial-price", type=float, default=300.0)
    p.add_argument("--mock-pred", type=float, default=300.6,
                   help="mock backend の固定 pred_close_mean")
    p.add_argument("--kronos-sample-count", type=int, default=1)
    args = p.parse_args()

    if args.backend == "mock":
        provider = constant_signal_provider(pred_close_mean=args.mock_pred, pred_close_std=1.0)
    else:
        from abm_models.kronos_aggregate.kronos_signal import make_kronos_signal_provider
        provider = make_kronos_signal_provider(
            lookback=args.lookback_bars, sample_count=args.kronos_sample_count,
        )

    model = KronosLOBMarket(
        signal_provider=provider,
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_trend=args.n_trend, n_fade=args.n_fade, n_fcn=args.n_fcn,
        bar_size=args.bar_size, lookback_bars=args.lookback_bars,
        order_volume=args.order_volume, initial_market_price=args.initial_price,
    )

    t0 = time.time()
    res = model.run(seed=args.seed)
    dt = time.time() - t0

    prices = res["prices"]
    returns = res["returns"]
    n_trend_acts = sum(len(al) for al in res["trend_actions"])
    n_fade_acts = sum(len(al) for al in res["fade_actions"])
    sig_log = res["signal_log"]
    n_signals = sum(1 for _, s in sig_log if s is not None)

    print(f"[yh007-2/{args.backend}] seed={args.seed} warmup={args.warmup_steps} "
          f"main={args.main_steps} bar={args.bar_size} dt={dt:.2f}s")
    print(f"  bars : {len(prices)} (warmup+main / bar_size)")
    print(f"  price: start={prices[0]:.5f} end={prices[-1]:.5f} "
          f"min={prices.min():.5f} max={prices.max():.5f}")
    print(f"  acts : trend={n_trend_acts} fade={n_fade_acts}  signals={n_signals}")

    if returns.size < 4:
        print("  [SF] returns too short for SF.")
        return

    # SF: spec §8 受け入れ基準 (vol_acf τ=50 正の緩減衰、Hill α ∈ [2,5])
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    sf = stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)
    print(f"  [SF] std={sf['std']:.4e}  Hill α={sf['hill_alpha']:.3f}")
    print(f"  [SF] ret_acf: " + ", ".join(f"τ={l}:{sf['ret_acf'][l]:+.4f}" for l in sf["ret_acf"]))
    print(f"  [SF] vol_acf: " + ", ".join(f"τ={l}:{sf['vol_acf'][l]:+.4f}" for l in sf["vol_acf"]))
    print(f"  [SF] kurt   : " + ", ".join(f"w={w}:{sf['kurt'][w]:+.2f}" for w in sf["kurt"]))

    # 受け入れ基準の自動判定 (緩い目安、spec §8)
    alpha = sf["hill_alpha"]
    vol_50 = sf["vol_acf"].get(50, np.nan)
    ret_1 = sf["ret_acf"].get(1, np.nan)
    print()
    print(f"  [verdict / spec §8 目安]")
    print(f"    fat tail (Hill α ∈ [2,5]): {'✓' if 2.0 <= alpha <= 5.0 else '✗'}  α={alpha:.3f}")
    print(f"    vol clustering (vol_acf τ=50 > 0): "
          f"{'✓' if (not np.isnan(vol_50) and vol_50 > 0.0) else '✗'}  vol_acf[50]={vol_50:+.4f}")
    print(f"    returns ≈ uncorrelated (|ret_acf τ=1| < 0.1): "
          f"{'✓' if (not np.isnan(ret_1) and abs(ret_1) < 0.1) else '✗'}  ret_acf[1]={ret_1:+.4f}")


if __name__ == "__main__":
    main()
