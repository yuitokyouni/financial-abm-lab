"""YH007-8 P3-F (§3.8): quantile mid 再センタリング kronos の substrate 検証。

P3-D/E の判定 (bounce の必要十分条件 = sticky anchor) を受けた fix F:
    v_i = mid + (X_i − median(X))
予測の水準 (sticky) を捨て、形状 (幅・歪み) だけを配置に使う。

合格判定 (spec 003 §6 の二重条件):
  (i)  ret_acf[1] ∈ [−0.1, +0.1]  (D1 系の実測 −0.04〜−0.06 が期待値)
  (ii) Hill α / vol_acf / std 健全 + agg parity (zi_matched 0.102 と同桁)

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.YH007.scripts.yh007_8_p3f_recenter --n-seeds 8 --main-steps 2000
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from abm_models.self_organized_book import SelfOrganizedBookMarket
from experiments.YH007.scripts.yh007_8_p3d_shared_ar1 import _metrics
from experiments.YH007.scripts.yh007_8_p3prime2_arb_grid import _agg


def run_kronos_recenter(seed: int, common: dict) -> dict:
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
        kronos_eval_mode="recenter",
    )
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0
    return {"seed": seed, "dt": dt, **_metrics(res, res["kronos_agents"])}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=8)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=2000)
    p.add_argument("--n-strategy", type=int, default=10)
    p.add_argument("--n-zi-liq", type=int, default=10)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--p3prime2-json", type=str, default="/tmp/yh007_8_p3prime2.json")
    p.add_argument("--p3d-json", type=str, default="/tmp/yh007_8_p3d.json")
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p3f.json")
    args = p.parse_args()

    common = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_strategy=args.n_strategy, n_zi_liq=args.n_zi_liq,
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
    )
    rows: list[dict] = []
    for seed in range(args.n_seeds):
        r = run_kronos_recenter(seed, common)
        rows.append(r)
        print(f"[recenter/seed={seed}] dt={r['dt']:.0f}s  ret1={r['ret_acf_mid'][0]:+.3f}  "
              f"same={r['all_same_rate']:.2f} |net|={r['mean_abs_net_side']:.2f}  "
              f"agg={r['agg_strategy']:.3f}", flush=True)

    # --- 参照行 ---
    refs: dict[str, list[dict]] = {}
    p3p2 = Path(args.p3prime2_json)
    if p3p2.exists():
        d = json.loads(p3p2.read_text())
        if "kronos_arb=0.00" in d:
            refs["ref:kronos_chase"] = d["kronos_arb=0.00"]
    p3d = Path(args.p3d_json)
    if p3d.exists():
        d = json.loads(p3d.read_text())["results"]
        for k in ("zi_matched", "D1_Wk", "E_W0"):
            if k in d:
                refs[f"ref:{k}"] = d[k]

    def _row(name, rr):
        a_ret1 = _agg(rr, ("ret_acf_mid", 0))
        a_vol1 = _agg(rr, ("vol_acf_mid", 0))
        a_hill = _agg(rr, ("sf_mid", "hill_alpha"))
        a_std = _agg(rr, ("sf_mid", "std"))
        a_agg = _agg(rr, ("agg_strategy",))
        a_same = _agg(rr, ("all_same_rate",))
        a_net = _agg(rr, ("mean_abs_net_side",))
        same_s = (f"{a_same['mean']:.2f}" if np.isfinite(a_same["mean"]) else " n/a")
        net_s = (f"{a_net['mean']:.2f}" if np.isfinite(a_net["mean"]) else " n/a")
        print(f"  {name:>18}  {a_ret1['mean']:+.3f}±{a_ret1['std']:.2f}  "
              f"{a_vol1['mean']:+.3f}±{a_vol1['std']:.2f}  "
              f"{a_hill['mean']:+.2f}±{a_hill['std']:.2f}  "
              f"{a_std['mean']:.2e}  {a_agg['mean']:.3f}  {same_s}  {net_s}")

    print("\n=== P3-F recenter vs 参照 ===")
    print(f"  {'cond':>18}  {'ret_acf[1]':>12}  {'vol_acf[1]':>12}  {'Hill_α':>10}  "
          f"{'std':>9}  {'agg':>5}  {'same':>4}  {'|net|':>5}")
    for name, rr in refs.items():
        _row(name, rr)
    _row("kronos_recenter", rows)

    # --- 合格判定 ---
    ret1 = _agg(rows, ("ret_acf_mid", 0))["mean"]
    ok_i = abs(ret1) < 0.1
    agg = _agg(rows, ("agg_strategy",))["mean"]
    print(f"\n判定 (i) |ret_acf[1]|={abs(ret1):.3f} < 0.1 : {'PASS' if ok_i else 'FAIL'}")
    print(f"判定 (ii) agg={agg:.3f} (zi_matched 参照 0.102 と同桁か), "
          f"Hill/vol_acf/std は表を目視")

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"args": vars(args), "rows": rows}, default=str, indent=2))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
