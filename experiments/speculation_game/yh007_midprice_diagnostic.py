"""YH007 診断: 同一 run の history を market 価格 vs mid 価格で SF 算出して比較。

目的: ret_acf τ=1 ≈ -0.5 が Roll 1984 の bid-ask bounce アーティファクトかを
直接検証する。mid で同 SF を測って ret_acf τ=1 がほぼ 0 に潰れれば bounce は
測定アーティファクト確定 → 既存 ablation の指標を mid 版で読み直せる。

実行:
    uv run python -m experiments.speculation_game.yh007_midprice_diagnostic \\
      --warmup-steps 200 --main-steps 1000 --n-adaptive 30 --bar-size 10 \\
      --lookback-bars 16 --score-window 50 --out-png /tmp/yh007_mid_vs_market.png
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket
from abm_models.kronos_lob.bar_aggregator import closes_to_returns
from stylized_facts import stylized_facts_summary


def _sf(returns: np.ndarray) -> dict:
    if returns.size < 4:
        return None
    acf_lags = tuple(int(x) for x in (1, 5, 14, 50, 200) if x < returns.size)
    kurt_windows = tuple(int(x) for x in (1, 16, 64, 256) if x < returns.size)
    return stylized_facts_summary(returns, acf_lags=acf_lags, kurt_windows=kurt_windows)


def _print_sf(label: str, sf: dict) -> None:
    if sf is None:
        print(f"  [{label}] (too short)")
        return
    ret1 = sf["ret_acf"].get(1, float("nan"))
    vol50 = sf["vol_acf"].get(50, float("nan"))
    print(f"  [{label}] Hill α={sf['hill_alpha']:.3f}  std={sf['std']:.4e}  "
          f"ret_acf τ=1={ret1:+.4f}  vol_acf τ=50={vol50:+.4f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=777)
    p.add_argument("--warmup-steps", type=int, default=200)
    p.add_argument("--main-steps", type=int, default=1000)
    p.add_argument("--n-adaptive", type=int, default=30)
    p.add_argument("--n-fcn", type=int, default=30)
    p.add_argument("--bar-size", type=int, default=10)
    p.add_argument("--lookback-bars", type=int, default=16)
    p.add_argument("--score-window", type=int, default=50)
    p.add_argument("--mock-pred", type=float, default=300.6)
    p.add_argument("--out-png", type=str, default="/tmp/yh007_mid_vs_market.png")
    args = p.parse_args()

    provider = constant_signal_provider(pred_close_mean=args.mock_pred, pred_close_std=1.0)
    m = KronosLOBMarket(
        signal_provider=provider,
        warmup_steps=args.warmup_steps, main_steps=args.main_steps,
        n_trend=0, n_fade=0, n_fcn=args.n_fcn, n_adaptive=args.n_adaptive,
        bar_size=args.bar_size, lookback_bars=args.lookback_bars,
        order_volume=1, score_window=args.score_window,
        price_source="market",  # primary はどちらでもよい、両方 res に入る
    )
    t0 = time.time()
    res = m.run(seed=args.seed)
    dt = time.time() - t0

    hm = res["history_market"]
    hd = res["history_mid"]
    closes_market = hm["close"].to_numpy(dtype=np.float64)
    closes_mid = hd["close"].to_numpy(dtype=np.float64)
    ret_market = closes_to_returns(closes_market)
    ret_mid = closes_to_returns(closes_mid)

    sf_market = _sf(ret_market)
    sf_mid = _sf(ret_mid)

    print(f"\n[yh007/mid-diag] seed={args.seed} warmup={args.warmup_steps} "
          f"main={args.main_steps} bar={args.bar_size} N_adaptive={args.n_adaptive} "
          f"dt={dt:.1f}s  bars={len(closes_market)}")
    _print_sf("market", sf_market)
    _print_sf("mid   ", sf_mid)

    # ---- plot ----
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(f"YH007 diagnostic: market vs mid (seed={args.seed}, "
                 f"N_adaptive={args.n_adaptive}, bars={len(closes_market)})\n"
                 f"Roll 1984 bid-ask bounce check — mid should kill ret_acf τ=1",
                 fontsize=11)

    # close 系列の重ね描き
    ax = axes[0, 0]
    ax.plot(closes_market, label="market (last executed)", color="tab:gray", alpha=0.85)
    ax.plot(closes_mid, label="mid ((bb+ba)/2)", color="tab:blue", alpha=0.85)
    ax.set_xlabel("bar index"); ax.set_ylabel("close price")
    ax.set_title("close series")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # log returns hist
    ax = axes[0, 1]
    bins = 60
    ax.hist(ret_market, bins=bins, alpha=0.5, label="market", color="tab:gray")
    ax.hist(ret_mid, bins=bins, alpha=0.5, label="mid", color="tab:blue")
    ax.set_xlabel("log return"); ax.set_ylabel("count")
    ax.set_title("return distribution")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # ret_acf を τ=1..max まで
    ax = axes[1, 0]
    if sf_market is not None and sf_mid is not None:
        lags = sorted(set(sf_market["ret_acf"]) | set(sf_mid["ret_acf"]))
        m_v = [sf_market["ret_acf"].get(l, float("nan")) for l in lags]
        d_v = [sf_mid["ret_acf"].get(l, float("nan")) for l in lags]
        w = 0.4
        x = np.arange(len(lags))
        ax.bar(x - w/2, m_v, w, color="tab:gray", label="market")
        ax.bar(x + w/2, d_v, w, color="tab:blue", label="mid")
        ax.axhspan(-0.1, 0.1, color="tab:green", alpha=0.15, label="|.|<0.1 = uncorr")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_xticks(x); ax.set_xticklabels([str(l) for l in lags])
        ax.set_xlabel("lag τ"); ax.set_ylabel("ret_acf")
        ax.set_title("ret autocorrelation (Roll bounce diagnostic at τ=1)")
        ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)

    # vol_acf
    ax = axes[1, 1]
    if sf_market is not None and sf_mid is not None:
        lags = sorted(set(sf_market["vol_acf"]) | set(sf_mid["vol_acf"]))
        m_v = [sf_market["vol_acf"].get(l, float("nan")) for l in lags]
        d_v = [sf_mid["vol_acf"].get(l, float("nan")) for l in lags]
        w = 0.4
        x = np.arange(len(lags))
        ax.bar(x - w/2, m_v, w, color="tab:gray", label="market")
        ax.bar(x + w/2, d_v, w, color="tab:blue", label="mid")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_xticks(x); ax.set_xticklabels([str(l) for l in lags])
        ax.set_xlabel("lag τ"); ax.set_ylabel("vol_acf")
        ax.set_title("|return| autocorrelation (vol clustering)")
        ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out = Path(args.out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"saved figure: {out}")


if __name__ == "__main__":
    main()
