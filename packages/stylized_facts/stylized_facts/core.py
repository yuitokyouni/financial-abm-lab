"""YH005: Stylized facts 計算関数.

Cont (2001) "Empirical properties of asset returns" のうち以下 5 項目を計算:
  1. log_returns_from_prices  — 価格 → log-return (p<=0 は NaN でマスク)
  2. return_acf               — Corr(r(t+τ), r(t))
  3. volatility_acf           — Corr(|r(t+τ)|, |r(t)|)
  4. ccdf + Hill MLE          — 補完累積分布 + tail index
  5. kurtosis_windowed        — aggregational Gaussianity 用の window-sum kurtosis
"""

from __future__ import annotations

import numpy as np


def log_returns_from_prices(prices: np.ndarray) -> np.ndarray:
    """Log-return。p<=0 の index は NaN。長さ len(prices)-1。"""
    p = np.asarray(prices, dtype=np.float64)
    safe = np.where(p > 0, p, np.nan)
    logp = np.log(safe)
    return np.diff(logp)


def _acf(series: np.ndarray, max_lag: int) -> np.ndarray:
    """NaN を除外した上での自己相関 ACF[1..max_lag]。"""
    x = np.asarray(series, dtype=np.float64)
    mask = ~np.isnan(x)
    if mask.sum() < 2:
        return np.full(max_lag, np.nan)
    xc = x[mask]
    xc = xc - xc.mean()
    var = (xc ** 2).mean()
    if var == 0:
        return np.zeros(max_lag)
    out = np.empty(max_lag, dtype=np.float64)
    # NaN を含む場合は lag ごとに pair-wise で再計算する必要があるが、
    # p>0 が圧倒的多数なら簡便化のため全体 demean → pair product → mean でよい。
    # ただし NaN があるとペアのうち 1 つでも NaN なら積も NaN、np.nanmean で scraping。
    x_demeaned = np.where(mask, x - x[mask].mean(), np.nan)
    for lag in range(1, max_lag + 1):
        prod = x_demeaned[:-lag] * x_demeaned[lag:]
        m = np.nanmean(prod)
        out[lag - 1] = m / var
    return out


def return_acf(returns: np.ndarray, max_lag: int = 50) -> np.ndarray:
    """r(t) 自己相関 ACF[1..max_lag]。"""
    return _acf(returns, max_lag)


def volatility_acf(returns: np.ndarray, max_lag: int = 500) -> np.ndarray:
    """|r(t)| 自己相関 ACF[1..max_lag]。"""
    return _acf(np.abs(returns), max_lag)


def ccdf(values: np.ndarray, normalize: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """補完累積分布 P(|X| >= x) を (x_sorted, ccdf_values) で返す。

    normalize=True のとき |r| を (|r| - mean) / std ではなく、絶対値を std で割った
    正規化（mean-0, std-1 ではなく scale-only）を使う。テール比較が目的なので。
    """
    x = np.asarray(values, dtype=np.float64)
    x = x[~np.isnan(x)]
    ax = np.abs(x)
    if normalize:
        s = ax.std()
        if s > 0:
            ax = ax / s
    ax = np.sort(ax)
    n = len(ax)
    ccdf_vals = 1.0 - np.arange(n) / n
    return ax, ccdf_vals


def hill_mle_tail_index(values: np.ndarray, k: int | None = None) -> float:
    """Hill MLE tail index α。上位 k 個を使う。None なら sqrt(len) を既定とする。"""
    x = np.asarray(values, dtype=np.float64)
    x = x[~np.isnan(x)]
    ax = np.abs(x)
    ax = ax[ax > 0]
    if ax.size < 4:
        return float("nan")
    sorted_desc = np.sort(ax)[::-1]
    if k is None:
        k = int(np.sqrt(sorted_desc.size))
    k = min(max(k, 2), sorted_desc.size - 1)
    log_ratios = np.log(sorted_desc[:k]) - np.log(sorted_desc[k])
    mean_log_ratio = log_ratios.mean()
    if mean_log_ratio <= 0:
        return float("nan")
    return float(1.0 / mean_log_ratio)


def kurtosis_windowed(returns: np.ndarray, window: int) -> float:
    """window 幅で集計した return の excess kurtosis。window=1 が生リターン。"""
    r = np.asarray(returns, dtype=np.float64)
    r = r[~np.isnan(r)]
    if window > 1:
        n = (len(r) // window) * window
        r = r[:n].reshape(-1, window).sum(axis=1)
    if r.size < 4:
        return float("nan")
    m = r.mean()
    s = r.std()
    if s == 0:
        return float("nan")
    z = (r - m) / s
    return float((z ** 4).mean() - 3.0)


def stylized_facts_summary(
    returns: np.ndarray,
    acf_lags: tuple[int, ...] = (1, 14, 50, 200),
    kurt_windows: tuple[int, ...] = (1, 16, 64, 256, 640),
) -> dict:
    """stylized facts の単一サマリ dict。"""
    max_ret_lag = max(acf_lags) + 1
    ret_acf_series = return_acf(returns, max_lag=max_ret_lag)
    vol_acf_series = volatility_acf(returns, max_lag=max_ret_lag)
    return {
        "n_valid": int((~np.isnan(returns)).sum()),
        "std": float(np.nanstd(returns)),
        "ret_acf": {lag: float(ret_acf_series[lag - 1]) for lag in acf_lags},
        "vol_acf": {lag: float(vol_acf_series[lag - 1]) for lag in acf_lags},
        "kurt": {w: kurtosis_windowed(returns, w) for w in kurt_windows},
        "hill_alpha": hill_mle_tail_index(returns),
    }


# ---------------------------------------------------------------------------
# Phase 1 mechanism figures (論文2 Fig. 2/3/4/7/8/10 相当)
#
# これらは Phase 1 (YH005-1) の機構実証で使う可視化関数群。
# 既存 stylized-facts 群とは別レイヤ: 各関数は PNG を 1 枚保存し、
# 図に載せた数値を dict で返す (metrics JSON への集約用)。
# ---------------------------------------------------------------------------


def _hill_alpha_xmin_percentile(values: np.ndarray, pct: float = 90.0) -> tuple[float, float, int]:
    """Hill MLE α with xmin = given percentile of the sample. Returns (alpha, xmin, n_tail)."""
    x = np.asarray(values, dtype=np.float64)
    x = x[~np.isnan(x)]
    x = x[x > 0]
    if x.size < 4:
        return float("nan"), float("nan"), 0
    xmin = float(np.percentile(x, pct))
    tail = x[x >= xmin]
    if tail.size < 2 or xmin <= 0:
        return float("nan"), xmin, int(tail.size)
    log_ratio = np.log(tail / xmin).mean()
    if log_ratio <= 0:
        return float("nan"), xmin, int(tail.size)
    return float(1.0 / log_ratio), xmin, int(tail.size)


def plot_wealth_distribution(
    final_wealth: np.ndarray,
    output_path: str,
    title: str = "Wealth distribution at t=T",
) -> dict:
    """Complementary CDF of final_wealth on log-log axes.

    Reproduces Katahira-Chen 2019 arXiv Fig. 4. Hill α は xmin=90th percentile で推定。
    """
    import matplotlib.pyplot as plt

    w = np.asarray(final_wealth, dtype=np.float64)
    w_pos = w[w > 0]
    sorted_w = np.sort(w_pos)
    n = sorted_w.size
    ccdf_vals = 1.0 - np.arange(n) / n  # P(W >= w_sorted[i])

    alpha, xmin, n_tail = _hill_alpha_xmin_percentile(w_pos, pct=90.0)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.loglog(sorted_w, ccdf_vals, marker=".", linestyle="none", markersize=3)
    # 参考直線 (Hill α で tail を fit)
    if np.isfinite(alpha) and xmin > 0:
        x_line = np.logspace(np.log10(xmin), np.log10(sorted_w.max()), 50)
        # CCDF(x) = C x^{-α}; normalize at x=xmin (where tail fraction = n_tail/n)
        y_line = (n_tail / n) * (x_line / xmin) ** (-alpha)
        ax.loglog(x_line, y_line, "r--", linewidth=1.2,
                  label=f"Hill α={alpha:.2f} (xmin=p90)")
        ax.legend(loc="upper right", fontsize=9)
    ax.set_xlabel("wealth  w")
    ax.set_ylabel("P[W ≥ w]  (complementary CDF)")
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return {
        "alpha_hill_xmin_p90": float(alpha),
        "xmin_p90": float(xmin),
        "n_tail": int(n_tail),
        "num_agents": int(n),
        "median_wealth": float(np.median(w_pos)) if n else float("nan"),
        "mean_wealth": float(w_pos.mean()) if n else float("nan"),
        "max_wealth": float(w_pos.max()) if n else float("nan"),
    }


def plot_roundtrip_horizon(
    round_trips: dict,
    output_path: str,
    title: str = "Round-trip horizon distribution",
) -> dict:
    """Log-log histogram of horizon = close_t - open_t (論文2 Fig. 8 相当)."""
    import matplotlib.pyplot as plt

    horizon = (round_trips["close_t"] - round_trips["open_t"]).astype(np.int64)
    horizon = horizon[horizon > 0]
    k = horizon.size
    if k == 0:
        # 空の round-trip — 空図だけ出して返す
        fig, ax = plt.subplots(figsize=(6.5, 5))
        ax.set_title(title + " (no round-trips)")
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return {"num_round_trips": 0}

    h_min = max(1, int(horizon.min()))
    h_max = int(horizon.max())
    if h_max <= h_min:
        bins = np.array([h_min, h_min + 1])
    else:
        bins = np.logspace(np.log10(h_min), np.log10(h_max + 1), 40)
    counts, edges = np.histogram(horizon, bins=bins)
    centers = 0.5 * (edges[:-1] + edges[1:])
    nz = counts > 0

    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.loglog(centers[nz], counts[nz], marker="o", linestyle="-", markersize=4)
    ax.set_xlabel("horizon τ = close_t − open_t  (steps)")
    ax.set_ylabel("count")
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    return {
        "num_round_trips": int(k),
        "median_horizon": float(np.median(horizon)),
        "mean_horizon": float(horizon.mean()),
        "max_horizon": int(horizon.max()),
        "min_horizon": int(horizon.min()),
        "p90_horizon": float(np.percentile(horizon, 90)),
    }


def plot_deltaG_vs_horizon(
    round_trips: dict,
    output_path: str,
    title: str = "ΔG vs horizon",
) -> dict:
    """2D histogram: x = horizon, y = ΔG, color = log10(count). 論文2 Fig. 7 相当."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    horizon = (round_trips["close_t"] - round_trips["open_t"]).astype(np.int64)
    dG = round_trips["delta_G"].astype(np.float64)
    mask = horizon > 0
    horizon = horizon[mask]
    dG = dG[mask]
    k = horizon.size
    if k == 0:
        fig, ax = plt.subplots(figsize=(7, 5.5))
        ax.set_title(title + " (no round-trips)")
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        return {"num_round_trips": 0}

    fig, ax = plt.subplots(figsize=(7, 5.5))
    hb = ax.hexbin(horizon, dG, gridsize=40, bins="log", cmap="viridis", mincnt=1)
    ax.axhline(0, color="red", linewidth=0.6, alpha=0.6)
    ax.set_xlabel("horizon τ  (steps)")
    ax.set_ylabel("ΔG  (cognitive P&L)")
    ax.set_title(title)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("log10(count)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    abs_dG = np.abs(dG)
    corr = float(np.corrcoef(horizon.astype(np.float64), abs_dG)[0, 1]) if k > 1 else float("nan")

    return {
        "num_round_trips": int(k),
        "corr_horizon_abs_dG": corr,
        "mean_abs_dG": float(abs_dG.mean()),
        "frac_positive_dG": float((dG > 0).mean()),
        "frac_negative_dG": float((dG < 0).mean()),
    }


def plot_hold_ratio(
    sim_result: dict,
    output_path: str,
    title: str = "Action ratio (single parameter)",
) -> dict:
    """Single stacked bar: idle / active_hold / passive_hold / buy / sell の割合 (time-averaged)。

    論文2 Fig. 10 の M-sweep ではなく、単一 M の 1 本棒。
    """
    import matplotlib.pyplot as plt

    num_buy = sim_result["num_buy"].astype(np.float64)
    num_sell = sim_result["num_sell"].astype(np.float64)
    num_act = sim_result["num_active_hold"].astype(np.float64)
    num_pas = sim_result["num_passive_hold"].astype(np.float64)
    T = len(num_buy)
    # N はログからは直接取れないが、num_buy+sell+act+pas+idle = N なので
    # max 値の和が N、あるいは任意 step での和。ここでは step 毎の合算の最大値を使う。
    N_est = int((num_buy + num_sell + num_act + num_pas).max())
    # idle は N - (他 4 つ)
    num_idle = np.clip(N_est - (num_buy + num_sell + num_act + num_pas), 0.0, None)
    # time-average (正規化は N で割る)
    if N_est == 0:
        ratios = {k: float("nan") for k in ("idle", "active_hold", "passive_hold", "buy", "sell")}
    else:
        ratios = {
            "idle": float(num_idle.mean() / N_est),
            "active_hold": float(num_act.mean() / N_est),
            "passive_hold": float(num_pas.mean() / N_est),
            "buy": float(num_buy.mean() / N_est),
            "sell": float(num_sell.mean() / N_est),
        }

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    labels = ["idle", "active_hold", "passive_hold", "buy", "sell"]
    colors = ["#cccccc", "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    bottom = 0.0
    for lab, col in zip(labels, colors):
        v = ratios[lab]
        ax.bar(0, v, bottom=bottom, color=col, label=f"{lab} ({v:.3f})", width=0.5)
        bottom += v
    ax.set_xticks([])
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, 1)
    ax.set_ylabel("fraction (time-averaged over T steps)")
    ax.set_title(title)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return {"T": int(T), "N_est": int(N_est), **ratios}


def plot_order_size_time_series(
    sim_result: dict,
    output_path: str,
    xlim: tuple[int, int] = (0, 50000),
    title: str = "Order size decomposition",
    return_mode: str = "log_return",  # "log_return" | "dp"
    p0: float = 100.0,
) -> dict:
    """4-panel time series: r(t), big orders, medium orders, small orders (論文2 Fig. 2 相当)."""
    import matplotlib.pyplot as plt

    prices = sim_result["prices"]
    size_hist = sim_result["num_orders_by_size"]  # (T, 3): small, medium, large
    T = size_hist.shape[0]
    x0, x1 = int(xlim[0]), int(min(xlim[1], T))

    # (a) return series
    if return_mode == "log_return":
        p = np.asarray(prices, dtype=np.float64)
        p_safe = np.where(p > 0, p, np.nan)
        r = np.diff(np.log(p_safe))  # length T-1
        ret_label = "r(t) = ln p(t) − ln p(t−1)"
    else:
        # Δp = p(t) - p(t-1)  (初期は p(0) = p0 として back-diff)
        p = np.asarray(prices, dtype=np.float64)
        p_prev = np.concatenate([[p0], p[:-1]])
        r = p - p_prev  # length T
        ret_label = "Δp(t) = p(t) − p(t−1)"

    r_slice_start = x0
    r_slice_end = min(x1, r.size)
    t_r = np.arange(r_slice_start, r_slice_end)
    r_win = r[r_slice_start:r_slice_end]

    t_bucket = np.arange(x0, x1)
    small = size_hist[x0:x1, 0]
    medium = size_hist[x0:x1, 1]
    large = size_hist[x0:x1, 2]

    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(t_r, r_win, linewidth=0.5, color="black")
    axes[0].set_ylabel(ret_label)
    axes[0].set_title(title)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t_bucket, large, linewidth=0.4, color="#d62728")
    axes[1].set_ylabel("large orders\n(q > medium_max)")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(t_bucket, medium, linewidth=0.4, color="#ff7f0e")
    axes[2].set_ylabel("medium orders\n(small_max < q ≤ medium_max)")
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(t_bucket, small, linewidth=0.4, color="#1f77b4")
    axes[3].set_ylabel("small orders\n(q ≤ small_max)")
    axes[3].set_xlabel("step t")
    axes[3].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    # 全期間での集計値
    full_small = size_hist[:, 0]
    full_medium = size_hist[:, 1]
    full_large = size_hist[:, 2]
    # NaN (extreme state) の件数も報告
    n_return_nan = int(np.isnan(r).sum()) if return_mode == "log_return" else 0

    return {
        "return_mode": return_mode,
        "xlim": [x0, x1],
        "n_return_nan": n_return_nan,
        "mean_small": float(full_small.mean()),
        "mean_medium": float(full_medium.mean()),
        "mean_large": float(full_large.mean()),
        "peak_small": int(full_small.max()),
        "peak_medium": int(full_medium.max()),
        "peak_large": int(full_large.max()),
    }
