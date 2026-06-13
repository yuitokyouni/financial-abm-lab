"""Indicator computations for Phase 2 reanalysis (S1 + S3+).

5 main indicators (SPEC §4.1, §4.2):
  - Pearson / Spearman / Kendall corr(|ΔG|, h)
  - bin variance slope (heteroscedasticity 直接指標)
  - quantile slope diff q90 − q10 (funnel 開き度)

Plan B preemptive (SPEC §4.5):
  - corr(w_init, h)
  - skewness(ΔG | h_high) − skewness(ΔG | h_low)
  - Hill exponent of |ΔG|

実装方針: 各関数は (h, dG) または (h, abs_dG) を numpy array で受け取り、
float (1 値) を返す。サンプル数が少ない場合は NaN を返す (caller でハンドル)。
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm


# ---------------------------------------------------------------------------
# 5 main indicators
# ---------------------------------------------------------------------------

def corr_pearson(h: np.ndarray, abs_dG: np.ndarray) -> float:
    if h.size < 2 or abs_dG.size < 2:
        return float("nan")
    if np.std(h) == 0 or np.std(abs_dG) == 0:
        return float("nan")
    r, _ = stats.pearsonr(h, abs_dG)
    return float(r)


def corr_spearman(h: np.ndarray, abs_dG: np.ndarray) -> float:
    if h.size < 2 or abs_dG.size < 2:
        return float("nan")
    res = stats.spearmanr(h, abs_dG)
    return float(res.correlation) if not np.isnan(res.correlation) else float("nan")


def corr_kendall(h: np.ndarray, abs_dG: np.ndarray) -> float:
    if h.size < 2 or abs_dG.size < 2:
        return float("nan")
    res = stats.kendalltau(h, abs_dG)
    return float(res.correlation) if not np.isnan(res.correlation) else float("nan")


def bin_variance_slope(h: np.ndarray, dG: np.ndarray, K: int = 15) -> float:
    """Spearman ρ between log-h-bin-center and Var(log|ΔG|) within bin.

    Brief §5.3 のレシピ準拠。h を log-equal な K bin に切り、各 bin で
    Var(log|ΔG|) を計算 (mincount = 5)、bin_center と bin_var の Spearman ρ を返す。
    """
    if h.size < K * 5:
        return float("nan")
    log_h = np.log(np.maximum(h, 1.0))
    if log_h.max() <= log_h.min():
        return float("nan")
    bin_edges = np.linspace(log_h.min(), log_h.max(), K + 1)
    bin_centers, bin_vars = [], []
    for i in range(K):
        if i == K - 1:
            mask = (log_h >= bin_edges[i]) & (log_h <= bin_edges[i + 1])
        else:
            mask = (log_h >= bin_edges[i]) & (log_h < bin_edges[i + 1])
        if mask.sum() < 5:
            continue
        bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2.0)
        bin_vars.append(float(np.var(np.log(np.maximum(np.abs(dG[mask]), 1e-9)))))
    if len(bin_centers) < 3:
        return float("nan")
    res = stats.spearmanr(bin_centers, bin_vars)
    return float(res.correlation) if not np.isnan(res.correlation) else float("nan")


def bin_variance_slope_pooled(rt_df: pd.DataFrame, K: int = 15) -> float:
    """100 trial 全 RT を pool した上で 1 回 bin variance slope を計算 (S2 plan v2 修正 1)。

    trial-level の `bin_variance_slope` を 100 個平均する代わりに、全 trial の RT を
    先に concat してから bin slicing + Var(log|ΔG|) を計算。
    bin 内 sample 数 ×100 → bin variance 推定の SE が √100 = 10 倍縮む。

    Args:
      rt_df: 全 trial concat 済の DataFrame (列: "horizon", "delta_g")
      K: 数の log-equal bin 数 (default 15)
    """
    if "horizon" not in rt_df.columns or "delta_g" not in rt_df.columns:
        return float("nan")
    h = rt_df["horizon"].to_numpy(dtype=np.float64)
    dG = rt_df["delta_g"].to_numpy(dtype=np.float64)
    return bin_variance_slope(h, dG, K=K)


def quantile_slopes(
    h: np.ndarray,
    dG: np.ndarray,
    taus: Tuple[float, ...] = (0.10, 0.50, 0.90),
) -> Dict[float, float]:
    """statsmodels.QuantReg で各 τ の slope を返す。Brief §5.4。"""
    if h.size < 50:
        return {tau: float("nan") for tau in taus}
    X = sm.add_constant(h.astype(np.float64))
    y = dG.astype(np.float64)
    out: Dict[float, float] = {}
    for tau in taus:
        try:
            model = sm.QuantReg(y, X).fit(q=tau, max_iter=5000)
            out[tau] = float(model.params[1])
        except Exception:
            out[tau] = float("nan")
    return out


def quantile_slope_diff(h: np.ndarray, dG: np.ndarray) -> float:
    """slope_{0.90} − slope_{0.10}: funnel 開き度の定量化。"""
    s = quantile_slopes(h, dG, taus=(0.10, 0.90))
    if any(np.isnan(v) for v in s.values()):
        return float("nan")
    return s[0.90] - s[0.10]


# ---------------------------------------------------------------------------
# Plan B preemptive indicators
# ---------------------------------------------------------------------------

def hill_estimator(values: np.ndarray, n_tail_frac: float = 0.10) -> float:
    """Hill 推定量 α (右裾)。Brief §5.5。"""
    abs_vals = np.abs(values[values != 0]).astype(np.float64)
    if abs_vals.size < 20:
        return float("nan")
    sorted_vals = np.sort(abs_vals)[::-1]
    k = max(int(len(sorted_vals) * n_tail_frac), 10)
    if k >= len(sorted_vals):
        return float("nan")
    if sorted_vals[k] <= 0:
        return float("nan")
    log_ratios = np.log(sorted_vals[:k] / sorted_vals[k])
    mean_lr = log_ratios.mean()
    if mean_lr <= 0 or not np.isfinite(mean_lr):
        return float("nan")
    return float(1.0 / mean_lr)


def skewness_high_low_diff(h: np.ndarray, dG: np.ndarray) -> float:
    """h を中央値で 2 分し、各 bin の skew(ΔG) の差。

    SPEC §4.5 「Skewness(ΔG | h_high) − Skewness(ΔG | h_low)」、
    funnel の左右非対称性。
    """
    if h.size < 20:
        return float("nan")
    h_med = float(np.median(h))
    high_mask = h > h_med
    low_mask = h <= h_med
    if high_mask.sum() < 10 or low_mask.sum() < 10:
        return float("nan")
    high = dG[high_mask].astype(np.float64)
    low = dG[low_mask].astype(np.float64)
    return float(stats.skew(high) - stats.skew(low))


def corr_winit_h_spearman(rt_df: pd.DataFrame, agents_df: pd.DataFrame) -> float:
    """agent-level w_init を RT に join、Spearman(w_init, horizon)。

    SPEC §4.5 「`corr(w_init, h)`」: agent 生涯初期 wealth と RT horizon の相関。
    rt_df が既に "w_init" 列を持つ場合 (adapter で agent-level w_init を merge 済) は
    それを使う。持たない場合は agents_df から merge する。
    どちらも全 NaN なら NaN を返す。
    """
    if "w_init" in rt_df.columns and not rt_df["w_init"].isna().all():
        valid = rt_df[["w_init", "horizon"]].dropna()
    else:
        if "w_init" not in agents_df.columns:
            return float("nan")
        if agents_df["w_init"].isna().all():
            return float("nan")
        merged = rt_df.merge(
            agents_df[["agent_id", "w_init"]].drop_duplicates(subset=["agent_id"]),
            on="agent_id",
            how="left",
            suffixes=("_rt", ""),
        )
        valid = merged[["w_init", "horizon"]].dropna()
    if len(valid) < 2:
        return float("nan")
    res = stats.spearmanr(valid["w_init"].to_numpy(dtype=np.float64),
                          valid["horizon"].to_numpy(dtype=np.float64))
    return float(res.correlation) if not np.isnan(res.correlation) else float("nan")
