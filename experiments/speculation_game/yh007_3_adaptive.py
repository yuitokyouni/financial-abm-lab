"""YH007-3 — GCMG 適応 agent (Trend/Fade 内生選択 + Kronos 確信度連動の参加閾値)。

spec §5 YH007-3: 逆張り比率を内生決定。
mock / 実 Kronos 両 backend で SF baseline を計算し、YH007-2 (静的混合) と比較する。

実行 (mock):
    uv run python -m experiments.speculation_game.yh007_3_adaptive --backend mock --main-steps 2000 --n-adaptive 40

実行 (実 Kronos, 重い):
    KRONOS_PATH=/path/to/Kronos \\
      uv run python -m experiments.speculation_game.yh007_3_adaptive --backend kronos \\
      --warmup-steps 100 --main-steps 200 --bar-size 10 --lookback-bars 16 --n-adaptive 30
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

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
    p.add_argument("--n-adaptive", type=int, default=50)
    p.add_argument("--n-fcn", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=32)
    p.add_argument("--score-window", type=int, default=50)
    p.add_argument("--r-min-base", type=float, default=0.0)
    p.add_argument("--r-min-conf-coef", type=float, default=0.0)
    p.add_argument("--order-volume", type=int, default=1)
    p.add_argument("--initial-price", type=float, default=300.0)
    p.add_argument("--mock-pred", type=float, default=300.6)
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
        n_trend=0, n_fade=0, n_fcn=args.n_fcn, n_adaptive=args.n_adaptive,
        bar_size=args.bar_size, lookback_bars=args.lookback_bars,
        order_volume=args.order_volume, initial_market_price=args.initial_price,
        score_window=args.score_window,
        r_min_base=args.r_min_base, r_min_conf_coef=args.r_min_conf_coef,
    )

    t0 = time.time()
    res = model.run(seed=args.seed)
    dt = time.time() - t0
    prices = res["prices"]; returns = res["returns"]

    # 戦略選択の時系列
    strat_by_step: dict[int, Counter] = {}
    for log in res["adaptive_actions"]:
        for t, _, strat, _, _ in log:
            strat_by_step.setdefault(t, Counter())[strat] += 1
    steps_sorted = sorted(strat_by_step.keys())
    trend_frac = np.array([strat_by_step[s]["trend"] / max(sum(strat_by_step[s].values()), 1) for s in steps_sorted])
    fade_frac = np.array([strat_by_step[s]["fade"] / max(sum(strat_by_step[s].values()), 1) for s in steps_sorted])
    abst_frac = np.array([strat_by_step[s]["abstain"] / max(sum(strat_by_step[s].values()), 1) for s in steps_sorted])

    print(f"[yh007-3/{args.backend}] seed={args.seed} warmup={args.warmup_steps} "
          f"main={args.main_steps} bar={args.bar_size} N_adaptive={args.n_adaptive} "
          f"T={args.score_window} r_min={args.r_min_base} dt={dt:.2f}s")
    print(f"  bars : {len(prices)}")
    print(f"  price: start={prices[0]:.5f} end={prices[-1]:.5f} "
          f"min={prices.min():.5f} max={prices.max():.5f}")
    print(f"  strategy mix (over {len(steps_sorted)} active steps):")
    print(f"    trend: mean={trend_frac.mean():.3f} std={trend_frac.std():.3f}")
    print(f"    fade : mean={fade_frac.mean():.3f} std={fade_frac.std():.3f}")
    print(f"    abst : mean={abst_frac.mean():.3f} std={abst_frac.std():.3f}")
    print(f"    (std > 0 = 内生比率が時系列で変動している ✓)")

    if returns.size < 4:
        print("  [SF] returns too short for SF.")
        return

    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    sf = stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)
    print(f"  [SF] std={sf['std']:.4e}  Hill α={sf['hill_alpha']:.3f}")
    print(f"  [SF] ret_acf: " + ", ".join(f"τ={l}:{sf['ret_acf'][l]:+.4f}" for l in sf["ret_acf"]))
    print(f"  [SF] vol_acf: " + ", ".join(f"τ={l}:{sf['vol_acf'][l]:+.4f}" for l in sf["vol_acf"]))
    print(f"  [SF] kurt   : " + ", ".join(f"w={w}:{sf['kurt'][w]:+.2f}" for w in sf["kurt"]))

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
