"""YH007-8 P1 — ZI-naïve/matched で tick 較正 + power analysis pilot (spec 003 §5, §7)。

合格基準 (P1):
  - mid 連続性: mid 増分中央値 ~2-5 tick (0/±1 張り付き無し)
  - power analysis: ZI-matched の seed 間 SF std を実測 → 必要 seed 数を逆算

P1 では tick / 分散の幾つかの組合せで pilot を回し、
  (mid 増分の tick 単位分布, |r|_max/std, SF 指標の seed 間 std) を表示する。

実行:
    uv run python -m experiments.speculation_game.yh007_8_p1_calibration \\
      --n-seeds 8 --warmup-steps 200 --main-steps 1000 --n-zi 30

出力: /tmp/yh007_8_p1_pilot.json (multi-seed × multi-config の SF テーブル)。
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from abm_models.kronos_lob.bar_aggregator import closes_to_returns
from abm_models.self_organized_book import SelfOrganizedBookMarket
from stylized_facts import stylized_facts_summary


def _sf(returns: np.ndarray) -> dict | None:
    if returns.size < 4:
        return None
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    return stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)


def _required_n_for_detection(
    std: float, effect_size: float, alpha: float = 0.05, power: float = 0.80
) -> int:
    """両側 z-test の必要 seed 数 (Wald 近似): N ≥ ((z_α + z_β) × std / effect)^2。"""
    # z_{α/2} for two-sided = 1.96 at α=0.05
    z_alpha = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else math.sqrt(2) * 1.96
    # z_{β} for power=0.80 = 0.8416
    z_beta = 0.8416212335729143 if abs(power - 0.80) < 1e-9 else math.sqrt(2) * 0.84
    if effect_size <= 0:
        return -1
    n = ((z_alpha + z_beta) * std / effect_size) ** 2
    return max(1, int(math.ceil(n)))


def _mid_increment_tick_distribution(history_mid, tick_size: float) -> dict:
    closes = history_mid["close"].to_numpy(dtype=np.float64)
    if closes.size < 2:
        return {"n": 0}
    diffs = np.diff(closes)
    ticks = np.round(diffs / tick_size).astype(int)
    median_abs = float(np.median(np.abs(ticks))) if ticks.size else float("nan")
    p0 = float(np.mean(ticks == 0))
    p1 = float(np.mean(np.abs(ticks) == 1))
    p_extreme = float(np.mean(np.abs(ticks) >= 100))
    return {
        "n": int(ticks.size),
        "median_abs_tick": median_abs,
        "p0_tick": p0,
        "p1_tick": p1,
        "p_ge_100_tick": p_extreme,
    }


def run_config(
    label: str, *, n_seeds: int, warmup_steps: int, main_steps: int,
    n_zi: int, bar_size: int, order_ttl: int, sigma_eval: float,
    margin_min: float, margin_max: float, tick_size: float,
    zi_mode: str,
) -> dict:
    rows = []
    for seed in range(n_seeds):
        m = SelfOrganizedBookMarket(
            warmup_steps=warmup_steps, main_steps=main_steps,
            n_zi=n_zi, bar_size=bar_size, order_ttl=order_ttl,
            sigma_eval=sigma_eval,
            margin_min=margin_min, margin_max=margin_max,
            tick_size=tick_size, zi_mode=zi_mode,
        )
        t0 = time.time()
        res = m.run(seed=seed)
        dt = time.time() - t0

        n_sub = sum(sum(1 for _, side, p, _ in a.action_log if side != 0 and p is not None)
                    for a in res["agents"])
        n_exec = sum(len(a.executed_log) for a in res["agents"])
        agg_rate = n_exec / max(n_sub, 1)

        sf_market = _sf(res["returns_main_market"])
        sf_mid = _sf(res["returns_main_mid"])
        mid_diag = _mid_increment_tick_distribution(res["history_mid"], tick_size)

        rmax_over_std_mid = (float(np.abs(res["returns_main_mid"]).max()) /
                             float(np.std(res["returns_main_mid"])))\
            if res["returns_main_mid"].size > 1 and np.std(res["returns_main_mid"]) > 0\
            else float("nan")

        rows.append({
            "seed": seed, "dt": dt,
            "n_sub": n_sub, "n_exec": n_exec, "agg_rate": agg_rate,
            "sf_market": sf_market, "sf_mid": sf_mid,
            "mid_diag": mid_diag,
            "rmax_over_std_mid": rmax_over_std_mid,
            "n_returns_mid": int(res["returns_main_mid"].size),
        })

    def _grab(rows, source, key, lag=None):
        out = []
        for r in rows:
            sf = r[source]
            if sf is None:
                continue
            if lag is None:
                out.append(sf.get(key, float("nan")))
            else:
                out.append(sf.get(key, {}).get(lag, float("nan")))
        return np.array(out, dtype=float)

    hill_m = _grab(rows, "sf_market", "hill_alpha")
    hill_d = _grab(rows, "sf_mid", "hill_alpha")
    ret1_m = _grab(rows, "sf_market", "ret_acf", 1)
    ret1_d = _grab(rows, "sf_mid", "ret_acf", 1)
    vol50_m = _grab(rows, "sf_market", "vol_acf", 50)
    vol50_d = _grab(rows, "sf_mid", "vol_acf", 50)
    agg_rates = np.array([r["agg_rate"] for r in rows])
    mid_med_ticks = np.array([r["mid_diag"].get("median_abs_tick", np.nan) for r in rows])

    def _stat(arr):
        a = arr[~np.isnan(arr)]
        if a.size == 0:
            return {"mean": float("nan"), "std": float("nan"), "n": 0}
        return {"mean": float(a.mean()), "std": float(a.std(ddof=1) if a.size > 1 else 0.0),
                "n": int(a.size)}

    return {
        "label": label, "n_seeds": n_seeds, "n_bars_main": rows[0]["n_returns_mid"] + 1 if rows else 0,
        "agg_rate": _stat(agg_rates),
        "mid_med_abs_tick": _stat(mid_med_ticks),
        "Hill_market": _stat(hill_m),
        "Hill_mid": _stat(hill_d),
        "ret_acf_1_market": _stat(ret1_m),
        "ret_acf_1_mid": _stat(ret1_d),
        "vol_acf_50_market": _stat(vol50_m),
        "vol_acf_50_mid": _stat(vol50_d),
        "rmax_over_std_mid": _stat(np.array([r["rmax_over_std_mid"] for r in rows])),
        "rows": rows,
    }


def _print_block(b: dict) -> None:
    print(f"\n=== {b['label']} (n_seeds={b['n_seeds']}, n_bars≈{b['n_bars_main']}) ===")
    print(f"  agg_rate          : mean={b['agg_rate']['mean']:.4f} std={b['agg_rate']['std']:.4f}")
    print(f"  mid Δ median|tick|: mean={b['mid_med_abs_tick']['mean']:.2f} std={b['mid_med_abs_tick']['std']:.2f}")
    print(f"  Hill α (market)   : mean={b['Hill_market']['mean']:+.3f} std={b['Hill_market']['std']:.3f}")
    print(f"  Hill α (mid)      : mean={b['Hill_mid']['mean']:+.3f} std={b['Hill_mid']['std']:.3f}")
    print(f"  ret_acf[1] market : mean={b['ret_acf_1_market']['mean']:+.4f} std={b['ret_acf_1_market']['std']:.4f}")
    print(f"  ret_acf[1] mid    : mean={b['ret_acf_1_mid']['mean']:+.4f} std={b['ret_acf_1_mid']['std']:.4f}")
    print(f"  vol_acf[50] market: mean={b['vol_acf_50_market']['mean']:+.4f} std={b['vol_acf_50_market']['std']:.4f}")
    print(f"  vol_acf_50 mid    : mean={b['vol_acf_50_mid']['mean']:+.4f} std={b['vol_acf_50_mid']['std']:.4f}")
    print(f"  |r|_max/std (mid) : mean={b['rmax_over_std_mid']['mean']:.2f} std={b['rmax_over_std_mid']['std']:.2f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=8)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1000)
    p.add_argument("--n-zi", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--order-ttl", type=int, default=15)
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p1_pilot.json")
    args = p.parse_args()

    common = dict(n_seeds=args.n_seeds, warmup_steps=args.warmup_steps,
                  main_steps=args.main_steps, n_zi=args.n_zi,
                  bar_size=args.bar_size, order_ttl=args.order_ttl,
                  margin_min=0.001, margin_max=0.01)

    # tick 較正のための 2 構成。tick_size を粗 / 細で振る。
    configs = [
        ("ZI-naive  tick_coarse(1e-3) sigma=0.005",
         dict(zi_mode="naive", sigma_eval=0.005, tick_size=1e-3)),
        ("ZI-naive  tick_fine  (1e-5) sigma=0.005",
         dict(zi_mode="naive", sigma_eval=0.005, tick_size=1e-5)),
        ("ZI-matched mu=0  sigma=0.005 (control)",
         dict(zi_mode="matched", sigma_eval=0.005, tick_size=1e-5)),
        ("ZI-matched mu=0  sigma=0.010 (high vol)",
         dict(zi_mode="matched", sigma_eval=0.010, tick_size=1e-5)),
    ]

    results = []
    for label, cfg in configs:
        b = run_config(label, **common, **cfg)
        _print_block(b)
        results.append(b)

    # ---- power analysis pilot (CI×Kronos vs ZI-matched の検出力) ----
    # P3 で実装する CI×Kronos の effect size の上限見積りに使う。
    # ZI-matched 2 種の std を「effect size = ?」が検出できるかで逆算。
    print("\n=== power analysis pilot ===")
    print("各 SF 指標の seed 間 std から、effect_size を検出するための必要 seed 数を逆算。")
    print(" α=0.05, power=0.80, 両側 z-test (Wald)")
    headline = [
        ("Hill α (mid)", "Hill_mid"),
        ("ret_acf[1] mid", "ret_acf_1_mid"),
        ("vol_acf[50] mid", "vol_acf_50_mid"),
    ]
    # ZI-matched mu=0 (3 番目) を control 想定
    ctrl = results[2]
    for name, key in headline:
        std_ctrl = ctrl[key]["std"]
        print(f"  {name}: ctrl std={std_ctrl:.4f}")
        for effect in (0.1, 0.3, 0.5, 1.0):
            n_req = _required_n_for_detection(std_ctrl, effect)
            print(f"    effect={effect:.2f} → 必要 seed ≥ {n_req}")

    # JSON 保存
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, default=str, indent=2))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()
