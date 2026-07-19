"""YH007-8 P3-D: 共有 AR(1) ZI 対照 — bounce の犯人が S2/S3 構造か Kronos 情報かを判定。

P3'' 裁定図 (entanglement map §3-4) の対照 D:
  P3 の matched_ar1 (per-agent 独立 AR1、現 mid 係留) に対し、構造軸を 1 本ずつ埋める:
    D1 (S2 のみ): deviation を全 agent で共有 (SharedAR1Hub)、係留は現 mid のまま
    D2 (S2+S3):   共有 + 係留を SMA-8 (直近 8 完結 bar close) に変更 (Kronos 慣性 proxy)
  各々 rank band W ∈ {0, W_kron} (W_kron は較正 run から実測)。

判定:
  D1/D2 が kronos の ret_acf[1] ≈ −0.24 を再現 → bounce は共有 sticky anchor の構造署名
  再現しない → Kronos 固有成分 (予測の非線形性) が残る

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.speculation_game.yh007_8_p3d_shared_ar1 --n-seeds 8 --main-steps 2000
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from abm_models.self_organized_book import SelfOrganizedBookMarket
from experiments.speculation_game.yh007_8_p3prime2_arb_grid import _acf_shape, _agg, _sf


# ---------------------------------------------------------------- diagnostics

def _sides_per_bar(agents, bar_size: int) -> dict[int, list[int]]:
    """strategy agent 群の submission side を bar ごとに pool。"""
    out: dict[int, list[int]] = {}
    for a in agents:
        for t, side, price, payload in a.action_log:
            if side != 0 and price is not None:
                out.setdefault(t // bar_size, []).append(int(side))
    return out


def _side_stats(sides_per_bar: dict[int, list[int]]) -> dict:
    """same-side 診断: 全員同方向 bar 率と |net| 平均。"""
    all_same, abs_net, n_bars = 0, [], 0
    for _, sides in sides_per_bar.items():
        if len(sides) < 2:
            continue
        n_bars += 1
        if len(set(sides)) == 1:
            all_same += 1
        abs_net.append(abs(sum(sides)) / len(sides))
    return {
        "n_bars_ge2": n_bars,
        "all_same_rate": all_same / max(n_bars, 1),
        "mean_abs_net_side": float(np.mean(abs_net)) if abs_net else float("nan"),
    }


def _metrics(res, strategy_agents) -> dict:
    r = res["returns_main_mid"]
    n_sub = sum(sum(1 for _, s, p, _ in a.action_log if s != 0 and p is not None)
                for a in strategy_agents)
    n_exec = sum(len(a.executed_log) for a in strategy_agents)
    return {
        "agg_strategy": n_exec / max(n_sub, 1),
        "n_bars_returns_mid": int(r.size),
        "sf_mid": _sf(r),
        "ret_acf_mid": _acf_shape(r, "ret"),
        "vol_acf_mid": _acf_shape(r, "vol"),
        "max_over_std_mid": float(np.abs(r).max() / max(np.std(r), 1e-12)),
        **_side_stats(_sides_per_bar(strategy_agents, res["bar_size"])),
    }


# ---------------------------------------------------------------- calibration

def calibrate_kronos_band(common: dict, seed: int = 0, main_steps: int = 800) -> dict:
    """短い kronos run 1 本から rank band 半幅と same-side 参照値を実測。

    band は agent action_log の payload (v, rank) から bar ごとに再構成:
      halfwidth(bar) = (max_rank_v − min_rank_v) / 2
    """
    m = SelfOrganizedBookMarket(
        warmup_steps=common["warmup_steps"], main_steps=main_steps,
        n_zi=common["n_zi_liq"], zi_mode="naive",
        n_kronos=common["n_strategy"],
        bar_size=10, order_ttl=15,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=common["kronos_lookback_bars"],
        kronos_n_samples=common["kronos_n_samples"],
        kronos_margin_min=3.0e-5, kronos_margin_max=1.0e-4,
        kronos_arb_fraction=0.0,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0
    bar_size = res["bar_size"]
    # (bar, agent_rank) → v を dedupe (v は bar 内固定)
    v_by_bar: dict[int, dict[float, float]] = {}
    for a in res["kronos_agents"]:
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload:
                continue
            v_by_bar.setdefault(t // bar_size, {})[float(payload["rank"])] = float(payload["v"])
    halfwidths = [(max(vm.values()) - min(vm.values())) / 2.0
                  for vm in v_by_bar.values() if len(vm) >= common["n_strategy"] - 1]
    side_stats = _side_stats(_sides_per_bar(res["kronos_agents"], bar_size))
    return {
        "dt": dt,
        "n_bars_with_full_band": len(halfwidths),
        "band_halfwidth_median": float(np.median(halfwidths)) if halfwidths else float("nan"),
        "band_halfwidth_p25": float(np.percentile(halfwidths, 25)) if halfwidths else float("nan"),
        "band_halfwidth_p75": float(np.percentile(halfwidths, 75)) if halfwidths else float("nan"),
        "kronos_side_stats": side_stats,
    }


# ---------------------------------------------------------------- runs

def run_zi_cond(seed: int, mode: str, band: float, anchor_bars: int, common: dict,
                hub_scope: str = "shared") -> dict:
    m = SelfOrganizedBookMarket(
        warmup_steps=common["warmup_steps"], main_steps=common["main_steps"],
        n_zi=common["n_zi_liq"], zi_mode="naive",
        n_kronos=0,
        n_zi_strategy=common["n_strategy"],
        zi_strategy_mode=mode,
        zi_strategy_phi_ar1=0.418, zi_strategy_sigma_ar1_abs=6e-3, zi_strategy_mu_ar1=0.0,
        zi_strategy_margin_min=2.5e-5, zi_strategy_margin_max=1.2e-4,
        zi_strategy_band_halfwidth=band,
        zi_strategy_anchor_smooth_bars=anchor_bars,
        zi_strategy_hub_scope=hub_scope,
        bar_size=10, order_ttl=15,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0
    strat = [a for a in res["zi_agents"] if getattr(a, "zi_mode", "") == mode]
    return {"seed": seed, "dt": dt, **_metrics(res, strat)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=8)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=2000)
    p.add_argument("--n-strategy", type=int, default=10)
    p.add_argument("--n-zi-liq", type=int, default=10)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--w-band", type=str, default="auto",
                   help="'auto' = kronos 較正 run から実測、または float 直接指定")
    p.add_argument("--anchor-smooth-bars", type=int, default=8)
    p.add_argument("--p3prime2-json", type=str, default="/tmp/yh007_8_p3prime2.json",
                   help="P3'' の結果 JSON (kronos 参照行の再掲用、無ければ skip)")
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p3d.json")
    args = p.parse_args()

    common = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_strategy=args.n_strategy, n_zi_liq=args.n_zi_liq,
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
    )
    out: dict = {"args": vars(args)}

    # --- W 較正 ---
    if args.w_band == "auto":
        print("[calib] kronos 短 run で band halfwidth を実測 ...", flush=True)
        try:
            calib = calibrate_kronos_band(common)
            w_band = calib["band_halfwidth_median"]
            print(f"[calib] dt={calib['dt']:.0f}s  W_median={w_band:.4f} "
                  f"(IQR {calib['band_halfwidth_p25']:.4f}..{calib['band_halfwidth_p75']:.4f})  "
                  f"kronos all_same_rate={calib['kronos_side_stats']['all_same_rate']:.3f} "
                  f"|net|={calib['kronos_side_stats']['mean_abs_net_side']:.3f}", flush=True)
            out["calibration"] = calib
        except Exception as e:  # KRONOS 環境なし等
            w_band = 0.01
            print(f"[calib] 失敗 ({e!r}) → fallback W={w_band}", flush=True)
            out["calibration"] = {"error": repr(e), "fallback_w": w_band}
    else:
        w_band = float(args.w_band)
        out["calibration"] = {"manual_w": w_band}
    if not (w_band > 0) or not np.isfinite(w_band):
        w_band = 0.01

    # --- 条件表 ---
    conds = [
        ("zi_matched", dict(mode="matched_ar1", band=0.0, anchor_bars=0)),
        ("D1_W0", dict(mode="shared_ar1", band=0.0, anchor_bars=0)),
        ("D1_Wk", dict(mode="shared_ar1", band=w_band, anchor_bars=0)),
        ("D2_W0", dict(mode="shared_ar1", band=0.0, anchor_bars=args.anchor_smooth_bars)),
        ("D2_Wk", dict(mode="shared_ar1", band=w_band, anchor_bars=args.anchor_smooth_bars)),
        # E: deviation per-agent 独立 (S2 除去)、sticky anchor (S3) のみ残す
        ("E_W0", dict(mode="shared_ar1", band=0.0, anchor_bars=args.anchor_smooth_bars,
                      hub_scope="per_agent")),
        ("E_Wk", dict(mode="shared_ar1", band=w_band, anchor_bars=args.anchor_smooth_bars,
                      hub_scope="per_agent")),
    ]
    results: dict[str, list[dict]] = {}
    for name, kw in conds:
        results[name] = []
        for seed in range(args.n_seeds):
            r = run_zi_cond(seed, common=common, **kw)
            results[name].append(r)
            print(f"[{name}/seed={seed}] dt={r['dt']:.1f}s  ret1={r['ret_acf_mid'][0]:+.3f}  "
                  f"same={r['all_same_rate']:.2f} |net|={r['mean_abs_net_side']:.2f}  "
                  f"agg={r['agg_strategy']:.3f}", flush=True)
    out["results"] = results

    # --- P3'' kronos 参照行 ---
    ref_rows = {}
    p3p2 = Path(args.p3prime2_json)
    if p3p2.exists():
        ref = json.loads(p3p2.read_text())
        for key in ("kronos_arb=0.00", "kronos_arb=1.00"):
            if key in ref:
                ref_rows[key] = ref[key]

    # --- table ---
    def _row(name, rows):
        ag_ret1 = _agg(rows, ("ret_acf_mid", 0))
        ag_vol1 = _agg(rows, ("vol_acf_mid", 0))
        ag_hill = _agg(rows, ("sf_mid", "hill_alpha"))
        ag_std = _agg(rows, ("sf_mid", "std"))
        ag_agg = _agg(rows, ("agg_strategy",))
        ag_same = _agg(rows, ("all_same_rate",))
        ag_net = _agg(rows, ("mean_abs_net_side",))
        same_s = (f"{ag_same['mean']:.2f}±{ag_same['std']:.2f}"
                  if np.isfinite(ag_same["mean"]) else "   n/a   ")
        net_s = (f"{ag_net['mean']:.2f}±{ag_net['std']:.2f}"
                 if np.isfinite(ag_net["mean"]) else "   n/a   ")
        print(f"  {name:>16}  {ag_ret1['mean']:+.3f}±{ag_ret1['std']:.2f}  "
              f"{ag_vol1['mean']:+.3f}±{ag_vol1['std']:.2f}  "
              f"{ag_hill['mean']:+.2f}±{ag_hill['std']:.2f}  "
              f"{ag_std['mean']:.2e}  {ag_agg['mean']:.3f}  {same_s}  {net_s}")

    print("\n=== P3-D shared AR(1) 対照 vs P3'' 参照 ===")
    print(f"  {'cond':>16}  {'ret_acf[1]':>12}  {'vol_acf[1]':>12}  {'Hill_α':>10}  "
          f"{'std':>9}  {'agg':>5}  {'same_rate':>9}  {'|net|':>9}")
    for key, rows in ref_rows.items():
        _row(f"ref:{key}", rows)
    for name, _ in conds:
        _row(name, results[name])

    outp = Path(args.out_json)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, default=str, indent=2))
    print(f"\nsaved: {outp}")


if __name__ == "__main__":
    main()
