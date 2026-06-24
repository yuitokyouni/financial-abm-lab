"""YH007-8 P3 (spec 003 §5 + §7): CI×Kronos vs ZI-matched(AR(1) on v−mid) を multi-seed で比較。

成功条件 3 (§6): ZI-matched control 比で Kronos 寄与が分離できる
  = SF 指標に統計的有意な差 (Welch t-test, two-sided)

ZI-matched AR(1) 較正値: P2 実測 φ=0.418, σ=6e-3 absolute on mid=300 (= 裁定 A)。

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.speculation_game.yh007_8_p3_kronos_vs_zi \\
      --n-seeds 8 --main-steps 2000
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


def _v_mid_diag(agents) -> dict:
    """各 agent の (v-mid) bar 系列を集めて AR(1) fit と全体 std/mean。"""
    series = []
    for a in agents:
        if not a.action_log:
            continue
        bar_size = getattr(a, "bar_size", 10)
        bars = {}
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload or "mid" not in payload:
                continue
            bars[t // bar_size] = float(payload["v"]) - float(payload["mid"])
        if len(bars) >= 10:
            ks = sorted(bars.keys())
            series.append(np.array([bars[k] for k in ks], dtype=np.float64))
    if not series:
        return {"phi": float("nan"), "sigma": float("nan"),
                "v_mid_std": float("nan"), "v_mid_mean": float("nan"),
                "n_agents": 0}
    xs_prev, xs_curr = [], []
    for s in series:
        xs_prev.extend(s[:-1].tolist()); xs_curr.extend(s[1:].tolist())
    xs_prev = np.array(xs_prev); xs_curr = np.array(xs_curr)
    var_prev = float(np.var(xs_prev))
    if var_prev <= 0 or xs_prev.size < 3:
        return {"phi": float("nan"), "sigma": float("nan"),
                "v_mid_std": float(np.std(np.concatenate(series), ddof=1)),
                "v_mid_mean": float(np.mean(np.concatenate(series))),
                "n_agents": len(series)}
    phi = float(np.cov(xs_prev, xs_curr, ddof=0)[0, 1] / var_prev)
    residuals = xs_curr - phi * xs_prev
    return {
        "phi": phi, "sigma": float(np.std(residuals, ddof=1)),
        "v_mid_std": float(np.std(np.concatenate(series), ddof=1)),
        "v_mid_mean": float(np.mean(np.concatenate(series))),
        "n_agents": len(series),
    }


def _placement_var(agents) -> dict:
    bar_to_prices: dict[int, list[float]] = {}
    for a in agents:
        bar_size = getattr(a, "bar_size", 10)
        for t, side, price, payload in a.action_log:
            if side != 0 and price is not None:
                bar_to_prices.setdefault(t // bar_size, []).append(float(price))
    if not bar_to_prices:
        return {"n_bars": 0, "var_mean": float("nan"), "var_ts_std": float("nan")}
    vars_ = [float(np.var(ps, ddof=0)) for ps in bar_to_prices.values() if len(ps) >= 2]
    if not vars_:
        return {"n_bars": len(bar_to_prices), "var_mean": float("nan"),
                "var_ts_std": float("nan")}
    return {
        "n_bars": len(vars_),
        "var_mean": float(np.mean(vars_)),
        "var_ts_std": float(np.std(vars_, ddof=1)) if len(vars_) > 1 else 0.0,
    }


def _max_over_std(returns: np.ndarray) -> float:
    if returns.size < 2 or np.std(returns) <= 0:
        return float("nan")
    return float(np.abs(returns).max() / np.std(returns))


def _run_one_seed(seed: int, *, condition: str, common: dict) -> dict:
    if condition == "kronos":
        kwargs = dict(common,
                      n_kronos=common["n_agents"], n_zi=0,
                      zi_mode="naive")  # n_zi=0 で ZI 無し
    elif condition == "zi_matched":
        kwargs = dict(common,
                      n_kronos=0, n_zi=common["n_agents"],
                      zi_mode="matched_ar1",
                      zi_phi_ar1=0.418, zi_sigma_ar1_abs=6e-3, zi_mu_ar1=0.0)
    else:
        raise ValueError(f"unknown condition: {condition}")
    # kronos/zi 内部キー除去
    n_agents = kwargs.pop("n_agents")
    m = SelfOrganizedBookMarket(**kwargs)
    t0 = time.time()
    res = m.run(seed=seed)
    dt = time.time() - t0

    agents = res["kronos_agents"] if condition == "kronos" else res["zi_agents"]
    sf_market = _sf(res["returns_main_market"])
    sf_mid = _sf(res["returns_main_mid"])
    return {
        "seed": seed, "condition": condition, "dt": dt,
        "agg_rate": res["n_executed"] / max(res["n_submitted"], 1),
        "n_bars_returns_mid": int(res["returns_main_mid"].size),
        "sf_market": sf_market, "sf_mid": sf_mid,
        "max_over_std_mid": _max_over_std(res["returns_main_mid"]),
        "v_mid": _v_mid_diag(agents),
        "placement": _placement_var(agents),
    }


def _aggregate(rows: list[dict], key_path) -> dict:
    """key_path = ("sf_mid", "hill_alpha") or ("sf_mid", "ret_acf", 1) etc."""
    vals = []
    for r in rows:
        v = r
        try:
            for k in key_path:
                if isinstance(v, dict):
                    v = v.get(k, v.get(str(k)))
                else:
                    v = None
                if v is None: break
        except Exception:
            v = None
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(float(v))
    if not vals:
        return {"mean": float("nan"), "std": float("nan"), "n": 0, "vals": []}
    a = np.array(vals)
    return {"mean": float(a.mean()),
            "std": float(a.std(ddof=1)) if a.size > 1 else 0.0,
            "n": int(a.size), "vals": vals}


def _welch_t(a: list[float], b: list[float]) -> dict:
    """Welch's t-test (両側)。p-value は Welch-Satterthwaite degrees of freedom + Student t CDF。"""
    if len(a) < 2 or len(b) < 2:
        return {"t": float("nan"), "df": float("nan"), "p": float("nan")}
    aa = np.array(a); bb = np.array(b)
    m1, m2 = aa.mean(), bb.mean()
    v1, v2 = aa.var(ddof=1), bb.var(ddof=1)
    n1, n2 = aa.size, bb.size
    se = math.sqrt(v1/n1 + v2/n2)
    if se <= 0:
        return {"t": float("nan"), "df": float("nan"), "p": float("nan"),
                "diff": float(m1 - m2)}
    t = (m1 - m2) / se
    df = (v1/n1 + v2/n2) ** 2 / ((v1/n1)**2 / (n1-1) + (v2/n2)**2 / (n2-1))
    # student-t p-value (両側)
    from math import lgamma, log, exp
    # incomplete beta による t-cdf 計算は重いので scipy が無い場合の近似版
    try:
        from scipy.stats import t as stt
        p = float(2.0 * (1.0 - stt.cdf(abs(t), df)))
    except ImportError:
        # 正規近似 (df>30 で十分)
        from math import erf, sqrt
        p = float(2.0 * (1.0 - 0.5*(1.0 + erf(abs(t)/sqrt(2.0)))))
    return {"t": float(t), "df": float(df), "p": p, "diff": float(m1 - m2)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=8)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=2000)
    p.add_argument("--n-agents", type=int, default=10)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--order-ttl", type=int, default=15)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p3.json")
    args = p.parse_args()

    common = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_agents=args.n_agents,  # _run_one_seed で kronos/zi に分配
        bar_size=args.bar_size, order_ttl=args.order_ttl,
        # ZI 側 (matched_ar1) のスケール
        sigma_eval=5e-5, margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
        # Kronos 側
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
        kronos_margin_min=3e-5, kronos_margin_max=1e-4,
    )

    all_rows: dict[str, list[dict]] = {"kronos": [], "zi_matched": []}
    for cond in ("kronos", "zi_matched"):
        for seed in range(args.n_seeds):
            print(f"\n[{cond}/seed={seed}] start ...", flush=True)
            r = _run_one_seed(seed, condition=cond, common=common)
            all_rows[cond].append(r)
            sm = r["sf_mid"]
            print(f"  dt={r['dt']:.1f}s  agg={r['agg_rate']:.3f}  bars_ret={r['n_bars_returns_mid']}")
            if sm:
                print(f"  mid: Hill={sm['hill_alpha']:.3f} "
                      f"ret1={sm['ret_acf'].get(1, float('nan')):+.3f} "
                      f"vol50={sm['vol_acf'].get(50, float('nan')):+.3f} "
                      f"|r|_max/std={r['max_over_std_mid']:.2f}")
            vmd = r["v_mid"]
            print(f"  (v-mid): phi={vmd['phi']:+.3f} sigma={vmd['sigma']:.4e} "
                  f"std={vmd['v_mid_std']:.4e} mean={vmd['v_mid_mean']:+.4e}")

    # ---- 集約 + Welch t-test ----
    print("\n=== aggregate ===")
    metrics = [
        ("Hill α (mid)", ("sf_mid", "hill_alpha")),
        ("ret_acf τ=1 (mid)", ("sf_mid", "ret_acf", 1)),
        ("vol_acf τ=50 (mid)", ("sf_mid", "vol_acf", 50)),
        ("kurt w=16 (mid)", ("sf_mid", "kurt", 16)),
        ("|r|_max/std (mid)", ("max_over_std_mid",)),
        ("agg_rate", ("agg_rate",)),
    ]
    summary = {}
    print(f"  {'metric':>22}  {'kronos (m±s, n)':>22}  {'zi_matched (m±s, n)':>22}  "
          f"{'diff':>10}  {'t':>7}  {'p':>8}")
    for name, kp in metrics:
        ag_k = _aggregate(all_rows["kronos"], kp)
        ag_z = _aggregate(all_rows["zi_matched"], kp)
        tres = _welch_t(ag_k["vals"], ag_z["vals"])
        summary[name] = {"kronos": ag_k, "zi_matched": ag_z, "welch": tres}
        sig = "***" if tres["p"] < 0.001 else "**" if tres["p"] < 0.01 \
              else "*" if tres["p"] < 0.05 else ""
        print(f"  {name:>22}  "
              f"{ag_k['mean']:+.4f}±{ag_k['std']:.4f} ({ag_k['n']:>2})  "
              f"{ag_z['mean']:+.4f}±{ag_z['std']:.4f} ({ag_z['n']:>2})  "
              f"{tres.get('diff', float('nan')):+10.4f}  "
              f"{tres['t']:>+7.3f}  {tres['p']:.4f}{sig}")

    # dose match 検証
    print("\n=== dose match check ((v−mid) AR(1)) ===")
    for cond in ("kronos", "zi_matched"):
        phis = [r["v_mid"]["phi"] for r in all_rows[cond]
                if not math.isnan(r["v_mid"]["phi"])]
        stds = [r["v_mid"]["v_mid_std"] for r in all_rows[cond]
                if not math.isnan(r["v_mid"]["v_mid_std"])]
        print(f"  {cond:>12}: phi mean={np.mean(phis):+.4f} std={np.std(phis, ddof=1) if len(phis)>1 else 0:.4f}  "
              f"v-mid std mean={np.mean(stds):.4e}")

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"rows": all_rows, "summary": summary},
                                   default=str, indent=2))
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
