"""YH007-5 — 流動性ゆらぎ ablation (機構 1, Farmer-Gillemot-Lillo-Mike-Sen 2004)。

spec §5 YH007-5 / §2 機構 1: 大変化は大口注文ではなく板の **gap** で起きる。
薄い瞬間に普通サイズの成行 → fat tail。
ablation: MMFCN の depth (n_fcn × fcn_order_volume) を厚/中/薄で振り、Hill α / vol_acf を比較。

実行 (mock, adaptive 構成):
    uv run python -m experiments.speculation_game.yh007_5_liquidity_ablation \\
      --liq-levels thin,medium,thick

各 level の意味:
  thin   : n_fcn=10, fcn_order_volume=10  (薄い板, gap 多い → fat tail 期待)
  medium : n_fcn=30, fcn_order_volume=30  (baseline)
  thick  : n_fcn=60, fcn_order_volume=60  (厚い板, gap 少ない → fat tail 弱化期待)
"""
from __future__ import annotations

import argparse
import time

import numpy as np

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket
from stylized_facts import stylized_facts_summary


_LIQ_PRESETS = {
    "thin":   {"n_fcn": 10, "fcn_order_volume": 10},
    "medium": {"n_fcn": 30, "fcn_order_volume": 30},
    "thick":  {"n_fcn": 60, "fcn_order_volume": 60},
}


def _summarize_one(level: str, *, backend: str, seed: int, warmup_steps: int, main_steps: int,
                   n_adaptive: int, bar_size: int, lookback_bars: int, score_window: int,
                   execution_horizon: int, kronos_sample_count: int, initial_price: float,
                   mock_pred: float) -> dict:
    preset = _LIQ_PRESETS[level]
    if backend == "mock":
        provider = constant_signal_provider(pred_close_mean=mock_pred, pred_close_std=1.0)
    else:
        from abm_models.kronos_aggregate.kronos_signal import make_kronos_signal_provider
        provider = make_kronos_signal_provider(lookback=lookback_bars, sample_count=kronos_sample_count)

    model = KronosLOBMarket(
        signal_provider=provider,
        warmup_steps=warmup_steps, main_steps=main_steps,
        n_trend=0, n_fade=0, n_fcn=preset["n_fcn"], n_adaptive=n_adaptive,
        bar_size=bar_size, lookback_bars=lookback_bars,
        order_volume=1, initial_market_price=initial_price,
        score_window=score_window, execution_horizon=execution_horizon,
        fcn_order_volume=preset["fcn_order_volume"],
    )
    t0 = time.time()
    res = model.run(seed=seed)
    dt = time.time() - t0
    prices = res["prices"]
    returns = res["returns"]
    if returns.size < 4:
        return {"level": level, "dt": dt, "n_bars": int(prices.size),
                "preset": preset, "sf": None}
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    sf = stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)
    return {"level": level, "dt": dt, "n_bars": int(prices.size), "preset": preset,
            "p_start": float(prices[0]), "p_end": float(prices[-1]),
            "abs_r_max": float(np.abs(returns).max()), "sf": sf}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "kronos"], default="mock")
    p.add_argument("--seed", type=int, default=777)
    p.add_argument("--liq-levels", type=str, default="thin,medium,thick")
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1200)
    p.add_argument("--n-adaptive", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=16)
    p.add_argument("--score-window", type=int, default=50)
    p.add_argument("--execution-horizon", type=int, default=1)
    p.add_argument("--initial-price", type=float, default=300.0)
    p.add_argument("--mock-pred", type=float, default=300.6)
    p.add_argument("--kronos-sample-count", type=int, default=1)
    args = p.parse_args()

    levels = [s.strip() for s in args.liq_levels.split(",") if s.strip()]
    rows = []
    for lvl in levels:
        if lvl not in _LIQ_PRESETS:
            print(f"  unknown level: {lvl} (choose from {sorted(_LIQ_PRESETS)})"); continue
        print(f"\n[yh007-5/{args.backend}] level={lvl} preset={_LIQ_PRESETS[lvl]} start ...", flush=True)
        r = _summarize_one(lvl, backend=args.backend, seed=args.seed,
                           warmup_steps=args.warmup_steps, main_steps=args.main_steps,
                           n_adaptive=args.n_adaptive, bar_size=args.bar_size,
                           lookback_bars=args.lookback_bars, score_window=args.score_window,
                           execution_horizon=args.execution_horizon,
                           kronos_sample_count=args.kronos_sample_count,
                           initial_price=args.initial_price, mock_pred=args.mock_pred)
        rows.append(r)
        sf = r["sf"]
        if sf is None:
            print(f"  level={lvl}: returns too short"); continue
        print(f"  level={lvl:>6} dt={r['dt']:.1f}s bars={r['n_bars']}  "
              f"|r|_max={r['abs_r_max']:.4e}  Hill α={sf['hill_alpha']:.3f}")
        print(f"    ret_acf τ=1: {sf['ret_acf'].get(1, float('nan')):+.4f}  "
              f"vol_acf τ=50: {sf['vol_acf'].get(50, float('nan')):+.4f}")

    print("\n[YH007-5 ablation summary]")
    print(f"  {'level':>8} {'n_fcn':>6} {'fcn_vol':>8} {'Hill α':>8} "
          f"{'|r|_max':>10} {'vol_acf[50]':>12}")
    for r in rows:
        sf = r["sf"]; pre = r["preset"]
        if sf is None:
            print(f"  {r['level']:>8} {pre['n_fcn']:>6} {pre['fcn_order_volume']:>8}  (returns too short)")
            continue
        print(f"  {r['level']:>8} {pre['n_fcn']:>6} {pre['fcn_order_volume']:>8} "
              f"{sf['hill_alpha']:>+8.3f} {r['abs_r_max']:>10.4e} "
              f"{sf['vol_acf'].get(50, float('nan')):>+12.4f}")
    print("\n  期待 (機構 1 = 板 gap): thin → Hill α↓ (fat tail), |r|_max↑ (大変動が出やすい)")


if __name__ == "__main__":
    main()
