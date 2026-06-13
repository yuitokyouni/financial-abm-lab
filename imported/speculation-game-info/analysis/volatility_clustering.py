"""ボラティリティクラスタリングの検証

|r(t)| の自己相関が長期にわたって正 → クラスタリング存在。
Stylized Fact の一つ (Cont 2001)。
"""

from __future__ import annotations

import numpy as np


def abs_return_autocorrelation(
    returns: np.ndarray, max_lag: int = 100
) -> np.ndarray:
    """絶対リターンの自己相関関数を計算。

    Parameters
    ----------
    returns : array
        リターン系列
    max_lag : int
        最大ラグ

    Returns
    -------
    array : shape (max_lag,), ACF[1] 〜 ACF[max_lag]
    """
    abs_r = np.abs(returns)
    mean = abs_r.mean()
    var = abs_r.var()
    if var == 0:
        return np.zeros(max_lag)

    acf = np.empty(max_lag)
    for lag in range(1, max_lag + 1):
        cov = np.mean((abs_r[:-lag] - mean) * (abs_r[lag:] - mean))
        acf[lag - 1] = cov / var
    return acf
