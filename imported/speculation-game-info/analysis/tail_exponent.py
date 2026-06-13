"""Hill 推定量による tail exponent α の計算

fat-tail の検証に使用。
α < 3 なら分散が無限 (Mandelbrot 条件)。
α ≈ 3 が多くの金融市場で観測される (Stylized Fact)。
"""

from __future__ import annotations

import numpy as np


def hill_estimator(returns: np.ndarray, k: int | None = None) -> float:
    """Hill 推定量で tail index α を推定。

    Parameters
    ----------
    returns : array
        リターン系列
    k : int, optional
        上位 k 個を使用。None なら sqrt(len) を使用。

    Returns
    -------
    float : tail index α の推定値
    """
    abs_returns = np.abs(returns)
    abs_returns = abs_returns[abs_returns > 0]
    sorted_r = np.sort(abs_returns)[::-1]

    if k is None:
        k = int(np.sqrt(len(sorted_r)))
    k = min(k, len(sorted_r) - 1)
    if k < 2:
        return float("nan")

    log_ratios = np.log(sorted_r[:k]) - np.log(sorted_r[k])
    alpha = k / np.sum(log_ratios)
    return float(alpha)
