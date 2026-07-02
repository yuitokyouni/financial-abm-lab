"""YH007-8 P3'' arb_fraction grid: §3.7 gain↔SF trade-off を一気にマップ。

裁定 §12 round5 caveat の「強すぎ振動」「弱すぎ残存」のスイートスポット探索。
arb_fraction ∈ {0.0, 0.3, 0.5, 0.7, 1.0} で kronos を走らせ、ZI-matched は 1 回だけ。

合格判定 (二重):
  (i) ret_acf τ=1 → ~0 (substrate clean)
  (ii) Hill α / vol_acf 健全 (= 価格ピン留めしない、SF 候補が残る)

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.speculation_game.yh007_8_p3prime2_arb_grid --n-seeds 8 --main-steps 2000
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from abm_models.kronos_lob.bar_aggregator import closes_to_returns
from abm_models.self_organized_book import SelfOrganizedBookMarket
from stylized_facts import return_acf, stylized_facts_summary, volatility_acf


def _sf(returns):
    if returns.size < 4: return None
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    return stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)


def _acf_shape(returns, kind, max_lag=10):
    if returns.size <= max_lag + 1:
        return [float("nan")] * max_lag
    fn = return_acf if kind == "ret" else volatility_acf
    return [float(x) for x in fn(returns, max_lag=max_lag)]


def _run_kronos(seed: int, arb_fraction: float, **common) -> dict:
    m = SelfOrganizedBookMarket(
        warmup_steps=common["warmup_steps"], main_steps=common["main_steps"],
        n_zi=common["n_zi_liq"], zi_mode="naive",
        n_kronos=common["n_strategy"],
        bar_size=10, order_ttl=15,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=common["kronos_lookback_bars"],
        kronos_n_samples=common["kronos_n_samples"],
        kronos_margin_min=3.0e-5, kronos_margin_max=1.0e-4,
        kronos_arb_fraction=arb_fraction,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0
    n_sub_strat = sum(sum(1 for _, side, p, _ in a.action_log if side != 0 and p is not None)
                      for a in res["kronos_agents"])
    n_exec_strat = sum(len(a.executed_log) for a in res["kronos_agents"])
    return {
        "seed": seed, "arb_fraction": arb_fraction, "dt": dt,
        "agg_strategy": n_exec_strat / max(n_sub_strat, 1),
        "n_bars_returns_mid": int(res["returns_main_mid"].size),
        "sf_mid": _sf(res["returns_main_mid"]),
        "ret_acf_mid": _acf_shape(res["returns_main_mid"], "ret"),
        "vol_acf_mid": _acf_shape(res["returns_main_mid"], "vol"),
        "max_over_std_mid": float(np.abs(res["returns_main_mid"]).max() /
                                  max(np.std(res["returns_main_mid"]), 1e-12)),
    }


def _run_zi(seed: int, zi_strategy_margin_min: float, zi_strategy_margin_max: float, **common) -> dict:
    m = SelfOrganizedBookMarket(
        warmup_steps=common["warmup_steps"], main_steps=common["main_steps"],
        n_zi=common["n_zi_liq"], zi_mode="naive",
        n_kronos=0,
        n_zi_strategy=common["n_strategy"],
        zi_strategy_mode="matched_ar1",
        zi_strategy_phi_ar1=0.418, zi_strategy_sigma_ar1_abs=6e-3, zi_strategy_mu_ar1=0.0,
        zi_strategy_margin_min=zi_strategy_margin_min,
        zi_strategy_margin_max=zi_strategy_margin_max,
        bar_size=10, order_ttl=15,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0
    strat = [a for a in res["zi_agents"] if getattr(a, "zi_mode", "") == "matched_ar1"]
    n_sub_strat = sum(sum(1 for _, side, p, _ in a.action_log if side != 0 and p is not None)
                      for a in strat)
    n_exec_strat = sum(len(a.executed_log) for a in strat)
    return {
        "seed": seed, "dt": dt,
        "agg_strategy": n_exec_strat / max(n_sub_strat, 1),
        "n_bars_returns_mid": int(res["returns_main_mid"].size),
        "sf_mid": _sf(res["returns_main_mid"]),
        "ret_acf_mid": _acf_shape(res["returns_main_mid"], "ret"),
        "vol_acf_mid": _acf_shape(res["returns_main_mid"], "vol"),
        "max_over_std_mid": float(np.abs(res["returns_main_mid"]).max() /
                                  max(np.std(res["returns_main_mid"]), 1e-12)),
    }


def _agg(rows, key_path):
    vals = []
    for r in rows:
        v = r
        for k in key_path:
            v = v.get(k) if isinstance(v, dict) else (v[k] if v is not None and isinstance(v, list) else None)
            if v is None: break
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(float(v))
    if not vals: return {"mean": float("nan"), "std": float("nan"), "n": 0}
    a = np.array(vals)
    return {"mean": float(a.mean()),
            "std": float(a.std(ddof=1)) if a.size > 1 else 0.0, "n": int(a.size)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=8)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=2000)
    p.add_argument("--n-strategy", type=int, default=10)
    p.add_argument("--n-zi-liq", type=int, default=10)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--zi-strategy-margin-min", type=float, default=2.5e-5)
    p.add_argument("--zi-strategy-margin-max", type=float, default=1.2e-4)
    p.add_argument("--arb-grid", type=float, nargs="+", default=[0.0, 0.3, 0.5, 0.7, 1.0])
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p3prime2.json")
    args = p.parse_args()

    common = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_strategy=args.n_strategy, n_zi_liq=args.n_zi_liq,
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
    )

    grid_results: dict[str, list[dict]] = {}
    # Kronos grid
    for arb in args.arb_grid:
        key = f"kronos_arb={arb:.2f}"
        grid_results[key] = []
        for seed in range(args.n_seeds):
            print(f"\n[{key}/seed={seed}] start ...", flush=True)
            r = _run_kronos(seed, arb, **common)
            grid_results[key].append(r)
            sm = r["sf_mid"]
            ret1 = r["ret_acf_mid"][0]
            vol1 = r["vol_acf_mid"][0]
            print(f"  dt={r['dt']:.1f}s agg_strat={r['agg_strategy']:.3f}  "
                  f"ret1={ret1:+.3f} vol1={vol1:+.3f} "
                  f"Hill={sm['hill_alpha'] if sm else float('nan'):.3f}")
    # ZI-matched 1 回
    grid_results["zi_matched"] = []
    for seed in range(args.n_seeds):
        print(f"\n[zi_matched/seed={seed}] start ...", flush=True)
        r = _run_zi(seed, args.zi_strategy_margin_min, args.zi_strategy_margin_max, **common)
        grid_results["zi_matched"].append(r)
        sm = r["sf_mid"]
        print(f"  dt={r['dt']:.1f}s agg_strat={r['agg_strategy']:.3f}  "
              f"ret1={r['ret_acf_mid'][0]:+.3f}  Hill={sm['hill_alpha'] if sm else float('nan'):.3f}")

    # 集約
    print("\n=== gain vs SF table ===")
    print(f"  {'cond':>20} {'agg':>7} {'ret_acf[1]':>12} {'ret_acf[2]':>12} "
          f"{'vol_acf[1]':>12} {'Hill_α':>10} {'|r|max/std':>12} {'std':>11}")
    for key in [f"kronos_arb={a:.2f}" for a in args.arb_grid] + ["zi_matched"]:
        rows = grid_results[key]
        ag_agg = _agg(rows, ("agg_strategy",))
        ag_ret1 = _agg(rows, ("ret_acf_mid", 0))
        ag_ret2 = _agg(rows, ("ret_acf_mid", 1))
        ag_vol1 = _agg(rows, ("vol_acf_mid", 0))
        ag_hill = _agg(rows, ("sf_mid", "hill_alpha"))
        ag_jump = _agg(rows, ("max_over_std_mid",))
        ag_std = _agg(rows, ("sf_mid", "std"))
        print(f"  {key:>20}  {ag_agg['mean']:.3f}±{ag_agg['std']:.3f}  "
              f"{ag_ret1['mean']:+.3f}±{ag_ret1['std']:.2f}  "
              f"{ag_ret2['mean']:+.3f}±{ag_ret2['std']:.2f}  "
              f"{ag_vol1['mean']:+.3f}±{ag_vol1['std']:.2f}  "
              f"{ag_hill['mean']:+.2f}±{ag_hill['std']:.2f}  "
              f"{ag_jump['mean']:.2f}±{ag_jump['std']:.2f}  "
              f"{ag_std['mean']:.2e}±{ag_std['std']:.2e}")

    out = Path(args.out_json); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(grid_results, default=str, indent=2))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()
