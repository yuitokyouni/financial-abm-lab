"""Stylized Facts 検証まとめ

Cont (2001) "Empirical properties of asset returns" の主要項目:
1. Fat tails (tail exponent)
2. Volatility clustering (|r| の自己相関)
3. リターンの自己相関ほぼゼロ
4. Gain/loss asymmetry
5. Aggregational Gaussianity
"""

from __future__ import annotations

import numpy as np
from .tail_exponent import hill_estimator
from .volatility_clustering import abs_return_autocorrelation


def summarize(returns: np.ndarray) -> dict:
    """リターン系列から主要 Stylized Facts をまとめて計算。"""
    acf_abs = abs_return_autocorrelation(returns, max_lag=50)

    # リターン自己相関 (lag=1)
    r = returns
    mean_r = r.mean()
    var_r = r.var()
    if var_r > 0 and len(r) > 1:
        return_acf1 = float(
            np.mean((r[:-1] - mean_r) * (r[1:] - mean_r)) / var_r
        )
    else:
        return_acf1 = 0.0

    return {
        "tail_exponent": hill_estimator(returns),
        "vol_cluster_acf1": float(acf_abs[0]) if len(acf_abs) > 0 else 0.0,
        "vol_cluster_acf10": float(acf_abs[9]) if len(acf_abs) > 9 else 0.0,
        "return_acf1": return_acf1,
        "skewness": float(
            np.mean(((r - mean_r) / np.sqrt(var_r)) ** 3) if var_r > 0 else 0.0
        ),
        "kurtosis": float(
            np.mean(((r - mean_r) / np.sqrt(var_r)) ** 4) if var_r > 0 else 0.0
        ),
    }
