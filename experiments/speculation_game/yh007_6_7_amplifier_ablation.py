"""YH007-6/7 — 増幅器 ablation: Predator (機構 4) と Spoofer (機構 5) を on/off。

spec §5 / §2: 機構 4 (新規 LIMIT を食う捕食) と機構 5 (見せ板) は econophysics の通説で
"増幅器" とされる (SF は spoofing 登場前から普遍)。本実験では、(1)(2)(3) 系の機構を
入れた状態で (4)(5) を追加すると SF 指標がどう動くかを観察する。

ablation 4 条件:
  none  : 既定 (adaptive のみ)
  pred  : + PredatorAgent×N
  spoof : + SpooferAgent×N
  both  : + 両方

実行 (mock):
    uv run python -m experiments.speculation_game.yh007_6_7_amplifier_ablation \\
      --conditions none pred spoof both --main-steps 1200 --n-adaptive 30
"""
from __future__ import annotations

import argparse
import time

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


_PRESETS = {
    "none":  {"n_predator": 0, "n_spoofer": 0},
    "pred":  {"n_predator": 10, "n_spoofer": 0},
    "spoof": {"n_predator": 0, "n_spoofer": 5},
    "both":  {"n_predator": 10, "n_spoofer": 5},
}


def _summarize_one(cond: str, *, backend: str, seed: int, warmup_steps: int, main_steps: int,
                   n_adaptive: int, n_fcn: int, bar_size: int, lookback_bars: int,
                   score_window: int, execution_horizon: int, kronos_sample_count: int,
                   initial_price: float, mock_pred: float, spoof_volume: int,
                   spoof_offset_ticks: int) -> dict:
    preset = _PRESETS[cond]
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
        score_window=score_window, execution_horizon=execution_horizon,
        n_predator=preset["n_predator"], predator_order_volume=1,
        n_spoofer=preset["n_spoofer"],
        spoof_volume=spoof_volume, spoof_offset_ticks=spoof_offset_ticks,
    )
    t0 = time.time()
    res = model.run(seed=seed)
    dt = time.time() - t0
    n_pred = sum(len(l) for l in res.get("predation_logs", []))
    n_spoof = sum(len(l) for l in res.get("spoof_logs", []))
    sf_market = _sf_from_history(res["history_market"])
    sf_mid = _sf_from_history(res["history_mid"])
    r_m = closes_to_returns(res["history_market"]["close"].to_numpy(dtype="float64"))
    r_d = closes_to_returns(res["history_mid"]["close"].to_numpy(dtype="float64"))
    return {"cond": cond, "dt": dt, "n_bars": int(len(res["history_market"])),
            "preset": preset, "n_pred": n_pred, "n_spoof": n_spoof,
            "sf_market": sf_market, "sf_mid": sf_mid,
            "abs_r_max_market": float(np.abs(r_m).max()) if r_m.size else float("nan"),
            "abs_r_max_mid": float(np.abs(r_d).max()) if r_d.size else float("nan")}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["mock", "kronos"], default="mock")
    p.add_argument("--seed", type=int, default=777)
    p.add_argument("--conditions", nargs="+", default=["none", "pred", "spoof", "both"])
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1200)
    p.add_argument("--n-adaptive", type=int, default=30)
    p.add_argument("--n-fcn", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=16)
    p.add_argument("--score-window", type=int, default=50)
    p.add_argument("--execution-horizon", type=int, default=1)
    p.add_argument("--initial-price", type=float, default=300.0)
    p.add_argument("--mock-pred", type=float, default=300.6)
    p.add_argument("--kronos-sample-count", type=int, default=1)
    p.add_argument("--spoof-volume", type=int, default=200)
    p.add_argument("--spoof-offset-ticks", type=int, default=5)
    args = p.parse_args()

    rows = []
    for c in args.conditions:
        if c not in _PRESETS:
            print(f"  unknown condition: {c}"); continue
        print(f"\n[yh007-6_7/{args.backend}] cond={c} preset={_PRESETS[c]} start ...", flush=True)
        r = _summarize_one(c, backend=args.backend, seed=args.seed,
                           warmup_steps=args.warmup_steps, main_steps=args.main_steps,
                           n_adaptive=args.n_adaptive, n_fcn=args.n_fcn,
                           bar_size=args.bar_size, lookback_bars=args.lookback_bars,
                           score_window=args.score_window,
                           execution_horizon=args.execution_horizon,
                           kronos_sample_count=args.kronos_sample_count,
                           initial_price=args.initial_price, mock_pred=args.mock_pred,
                           spoof_volume=args.spoof_volume,
                           spoof_offset_ticks=args.spoof_offset_ticks)
        rows.append(r)
        for src in ("market", "mid"):
            sf = r[f"sf_{src}"]
            if sf is None: continue
            print(f"  [{src:>6}] cond={c:>5} dt={r['dt']:.1f}s bars={r['n_bars']} "
                  f"pred={r['n_pred']} spoof={r['n_spoof']} "
                  f"|r|_max={r['abs_r_max_'+src]:.4e}  Hill α={sf['hill_alpha']:.3f} "
                  f"ret_acf[1]={sf['ret_acf'].get(1, float('nan')):+.4f} "
                  f"vol_acf[50]={sf['vol_acf'].get(50, float('nan')):+.4f}")

    print("\n[YH007-6/7 ablation summary — market vs mid]")
    print(f"  {'cond':>6} {'n_pred':>6} {'n_spoof':>7}  "
          f"{'Hill_m':>8} {'Hill_mid':>9}  "
          f"{'ret1_m':>9} {'ret1_mid':>10}  "
          f"{'vol50_m':>10} {'vol50_mid':>11}  "
          f"{'|r|_m':>10} {'|r|_mid':>10}")
    for r in rows:
        sm, sd, pre = r["sf_market"], r["sf_mid"], r["preset"]
        if sm is None or sd is None:
            print(f"  {r['cond']:>6}  (returns too short)"); continue
        print(f"  {r['cond']:>6} {pre['n_predator']:>6} {pre['n_spoofer']:>7}  "
              f"{sm['hill_alpha']:>+8.3f} {sd['hill_alpha']:>+9.3f}  "
              f"{sm['ret_acf'].get(1, float('nan')):>+9.4f} "
              f"{sd['ret_acf'].get(1, float('nan')):>+10.4f}  "
              f"{sm['vol_acf'].get(50, float('nan')):>+10.4f} "
              f"{sd['vol_acf'].get(50, float('nan')):>+11.4f}  "
              f"{r['abs_r_max_market']:>10.3e} {r['abs_r_max_mid']:>10.3e}")
    import json
    out_path = f"/tmp/yh007_6_7_ablation_{args.backend}_seed{args.seed}.json"
    with open(out_path, "w") as f:
        json.dump([{"cond": r["cond"], "preset": r["preset"], "n_bars": r["n_bars"],
                    "sf_market": r["sf_market"], "sf_mid": r["sf_mid"],
                    "abs_r_max_market": r["abs_r_max_market"],
                    "abs_r_max_mid": r["abs_r_max_mid"]} for r in rows],
                  f, default=str)
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
