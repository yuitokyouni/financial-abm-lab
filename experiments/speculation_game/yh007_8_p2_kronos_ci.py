"""YH007-8 P2 (spec 003 §3.6 + §3.2 + §4): CI×Kronos vs ZI-matched ablation。

指揮 (architect) への必須返却:
  (1) per-bar batched Kronos latency (= 共有 hub 1 回 predict で全 agent quantile)
  (2) Kronos の (v − mid) の AR(1) φ/σ 実測値 (ZI-matched 較正用)

副産物:
  - 分散注入診断 §3.2 (herding≠degeneracy: placement price の時間平均分散 ≠ 0 かつ時系列変動)
  - SF 指標 (Hill α / ret_acf / vol_acf) の market vs mid
  - aggressive rate (Kronos 投入で帯から外れたら P1.5 発動 trigger)

実行:
    KRONOS_PATH=/path/to/Kronos uv run python \\
      -m experiments.speculation_game.yh007_8_p2_kronos_ci \\
      --n-seeds 4 --warmup-steps 200 --main-steps 1500 --n-zi 20 --n-kronos 10
"""
from __future__ import annotations

import argparse
import json
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


def _placement_variance_diag(agents) -> dict:
    """spec 003 §3.2 herding vs degeneracy 診断。

    各 bar での placement price の agent 横断分散の時間平均と時系列 std を出す。
    - time-mean variance > 0 → 配置に分散がある (degeneracy 否定)
    - time-series std > 0 → 分散自体が時系列で変動する (herding として観測可)
    """
    # bar → list[price] across agents
    bar_to_prices: dict[int, list[float]] = {}
    for a in agents:
        bar_size = getattr(a, "bar_size", 10)
        for t, side, price, payload in a.action_log:
            if side != 0 and price is not None:
                bar_to_prices.setdefault(t // bar_size, []).append(float(price))
    if not bar_to_prices:
        return {"n_bars": 0, "var_mean": float("nan"), "var_ts_std": float("nan")}
    vars_by_bar = [float(np.var(ps, ddof=0)) for ps in bar_to_prices.values() if len(ps) >= 2]
    if not vars_by_bar:
        return {"n_bars": len(bar_to_prices), "var_mean": float("nan"), "var_ts_std": float("nan")}
    return {
        "n_bars": len(vars_by_bar),
        "var_mean": float(np.mean(vars_by_bar)),
        "var_ts_std": float(np.std(vars_by_bar, ddof=1)) if len(vars_by_bar) > 1 else 0.0,
    }


def _v_minus_mid_ar1(agents) -> dict:
    """(v − mid) の時系列を agent 横断で集めて AR(1) fit。

    v_t = φ * v_{t-1} + ε, ε ~ N(0, σ)。
    φ < 1 で mean-reverting (現 mid 周辺に係留)、φ ~ 1 で random walk。
    spec 003 §4 ZI-matched の AR(1) on (v−mid) 較正用。
    """
    series: list[np.ndarray] = []
    for a in agents:
        bar_size = getattr(a, "bar_size", 10)
        # bar 単位で (v − mid) を時系列化 (同 bar 内では agent は 1 回 evaluate のみ想定)
        vs_minus_mid_by_bar: dict[int, float] = {}
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload or "mid" not in payload:
                continue
            vs_minus_mid_by_bar[t // bar_size] = float(payload["v"]) - float(payload["mid"])
        if len(vs_minus_mid_by_bar) >= 3:
            bars_sorted = sorted(vs_minus_mid_by_bar.keys())
            arr = np.array([vs_minus_mid_by_bar[b] for b in bars_sorted], dtype=np.float64)
            series.append(arr)
    if not series:
        return {"n_agents": 0, "phi": float("nan"), "sigma": float("nan"),
                "v_minus_mid_std": float("nan")}
    # 全 agent から (x_{t-1}, x_t) を集めて 1 個の AR(1) 推定
    xs_prev = []
    xs_curr = []
    for s in series:
        xs_prev.extend(s[:-1].tolist())
        xs_curr.extend(s[1:].tolist())
    xs_prev = np.array(xs_prev); xs_curr = np.array(xs_curr)
    if xs_prev.size < 3 or float(np.var(xs_prev)) <= 0:
        return {"n_agents": len(series), "phi": float("nan"), "sigma": float("nan"),
                "v_minus_mid_std": float("nan")}
    phi = float(np.cov(xs_prev, xs_curr, ddof=0)[0, 1] / np.var(xs_prev))
    residuals = xs_curr - phi * xs_prev
    return {
        "n_agents": len(series),
        "n_pairs": int(xs_prev.size),
        "phi": phi,
        "sigma": float(np.std(residuals, ddof=1)) if residuals.size > 1 else 0.0,
        "v_minus_mid_std": float(np.std(np.concatenate(series), ddof=1)),
        "v_minus_mid_mean": float(np.mean(np.concatenate(series))),
    }


def _summary_one_seed(seed: int, **kwargs) -> dict:
    m = SelfOrganizedBookMarket(**kwargs)
    t0 = time.time()
    res = m.run(seed=seed)
    run_dt = time.time() - t0
    n_sub = res["n_submitted"]
    n_exec = res["n_executed"]
    agg_rate = n_exec / max(n_sub, 1)
    sf_market = _sf(res["returns_main_market"])
    sf_mid = _sf(res["returns_main_mid"])
    # Kronos hub call latency
    calls = res["kronos_hub_calls"]
    dts = [c[1] for c in calls] if calls else []
    latency = {
        "n_calls": len(dts),
        "mean_dt": float(np.mean(dts)) if dts else float("nan"),
        "median_dt": float(np.median(dts)) if dts else float("nan"),
        "p95_dt": float(np.percentile(dts, 95)) if dts else float("nan"),
        "total_dt": float(sum(dts)),
    }
    # 分散注入診断 (Kronos のみ; ZI も診断したいなら別途)
    placement_diag = _placement_variance_diag(res["kronos_agents"])
    v_mid_diag = _v_minus_mid_ar1(res["kronos_agents"])
    return {
        "seed": seed, "run_dt": run_dt,
        "n_sub": n_sub, "n_exec": n_exec, "agg_rate": agg_rate,
        "sf_market": sf_market, "sf_mid": sf_mid,
        "latency": latency,
        "placement_diag": placement_diag,
        "v_mid_diag": v_mid_diag,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n-seeds", type=int, default=4)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1500)
    p.add_argument("--n-zi", type=int, default=20)
    p.add_argument("--n-kronos", type=int, default=10)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--order-ttl", type=int, default=15)
    p.add_argument("--kronos-lookback-bars", type=int, default=16)
    p.add_argument("--kronos-n-samples", type=int, default=32)
    p.add_argument("--out-json", type=str, default="/tmp/yh007_8_p2_kronos.json")
    args = p.parse_args()

    common = dict(
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_zi=args.n_zi, n_kronos=args.n_kronos,
        bar_size=args.bar_size, order_ttl=args.order_ttl,
        sigma_eval=5e-5, margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=args.kronos_lookback_bars,
        kronos_n_samples=args.kronos_n_samples,
        kronos_margin_min=3e-5, kronos_margin_max=1e-4,
    )
    rows = []
    for seed in range(args.n_seeds):
        print(f"\n[seed={seed}] start ...", flush=True)
        r = _summary_one_seed(seed, **common)
        rows.append(r)
        sm = r["sf_market"]; sd = r["sf_mid"]
        print(f"  run_dt={r['run_dt']:.1f}s  agg={r['agg_rate']:.3f}  "
              f"hub calls={r['latency']['n_calls']}  "
              f"per-call median={r['latency']['median_dt']:.3f}s p95={r['latency']['p95_dt']:.3f}s")
        if sm is not None:
            print(f"  market: Hill={sm['hill_alpha']:.3f} ret1={sm['ret_acf'].get(1, float('nan')):+.3f}"
                  f" vol50={sm['vol_acf'].get(50, float('nan')):+.3f}")
        if sd is not None:
            print(f"  mid   : Hill={sd['hill_alpha']:.3f} ret1={sd['ret_acf'].get(1, float('nan')):+.3f}"
                  f" vol50={sd['vol_acf'].get(50, float('nan')):+.3f}")
        pd_ = r["placement_diag"]
        print(f"  placement: n_bars={pd_['n_bars']} var_mean={pd_['var_mean']:.3e} "
              f"var_ts_std={pd_['var_ts_std']:.3e}")
        vd = r["v_mid_diag"]
        print(f"  (v-mid) AR(1): phi={vd['phi']:+.4f} sigma={vd['sigma']:.4e} "
              f"v-mid std={vd['v_minus_mid_std']:.4e} mean={vd['v_minus_mid_mean']:+.4e}")

    # ---- 全 seed 集約 (指揮への返却) ----
    print("\n=== aggregate over seeds ===")
    agg_rates = np.array([r["agg_rate"] for r in rows])
    print(f"  agg_rate: mean={agg_rates.mean():.4f} std={agg_rates.std(ddof=1) if agg_rates.size>1 else 0:.4f}"
          f"  (target [0.05, 0.20])")
    # latency
    medians = np.array([r["latency"]["median_dt"] for r in rows if not np.isnan(r["latency"]["median_dt"])])
    p95s = np.array([r["latency"]["p95_dt"] for r in rows if not np.isnan(r["latency"]["p95_dt"])])
    print(f"  per-bar Kronos batched latency: median={medians.mean():.3f}s p95={p95s.mean():.3f}s "
          f"(n_samples={args.kronos_n_samples}, n_agents={args.n_kronos})")
    # AR(1) of (v-mid)
    phis = np.array([r["v_mid_diag"]["phi"] for r in rows
                     if not np.isnan(r["v_mid_diag"]["phi"])])
    sigmas = np.array([r["v_mid_diag"]["sigma"] for r in rows
                       if not np.isnan(r["v_mid_diag"]["sigma"])])
    stds = np.array([r["v_mid_diag"]["v_minus_mid_std"] for r in rows
                     if not np.isnan(r["v_mid_diag"]["v_minus_mid_std"])])
    print(f"  (v−mid) AR(1) over seeds: phi mean={phis.mean():+.4f} std={phis.std(ddof=1) if phis.size>1 else 0:.4f}")
    print(f"                            sigma mean={sigmas.mean():.4e} std={sigmas.std(ddof=1) if sigmas.size>1 else 0:.4e}")
    print(f"  v−mid std mean={stds.mean():.4e}  (ZI-matched dose match の target)")
    # SF
    def _sf_summary(rows, source, key, lag=None):
        arr = []
        for r in rows:
            sf = r[source]
            if sf is None: continue
            if lag is None: arr.append(sf.get(key, float("nan")))
            else: arr.append(sf.get(key, {}).get(lag, float("nan")))
        a = np.array(arr, dtype=float); a = a[~np.isnan(a)]
        return (float(a.mean()), float(a.std(ddof=1)) if a.size > 1 else 0.0, int(a.size))
    for name, key, lag in [
        ("Hill α (mid)", "hill_alpha", None),
        ("ret_acf τ=1 (mid)", "ret_acf", 1),
        ("vol_acf τ=50 (mid)", "vol_acf", 50),
    ]:
        m_, s_, n_ = _sf_summary(rows, "sf_mid", key, lag)
        print(f"  {name}: mean={m_:+.4f} std={s_:.4f} (n={n_})")

    out = Path(args.out_json); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, default=str, indent=2))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()
