"""stylized_facts の推定器を **解析的 ground truth** に対して検証する単体テスト。

監査 (2026-07-02) #8/#15: 全パリティ・全 findings の測定器 (stylized_facts) に
解析的 ground truth の単体テストがゼロだった。既存テストは同一実装同士の循環比較
のみで、YH005 から継承した推定器バグが 0.00% 誤差で永久に再現する構造だった。

ここでは分布の理論値が既知のケースだけを使い、ミリ秒で走る:
  - AR(1):        ρ(k) = φ^k
  - 白色雑音:      ACF は Bartlett 帯 ±z/√n にほぼ収まる
  - Pareto(α):    Hill tail index ≈ α
  - Gaussian:     excess kurtosis ≈ 0
  - fat tail:     excess kurtosis > 0
  - log-return:   既知価格列 → 既知 log-return、p<=0 は NaN
  - N 推定 (#7):  plot_hold_ratio は final_wealth 長 = 真の N を使う
"""

from __future__ import annotations

import numpy as np
import pytest

from stylized_facts.core import (
    bartlett_conf_band,
    hill_mle_tail_index,
    kurtosis_windowed,
    log_returns_from_prices,
    return_acf,
    volatility_acf,
)


def test_ar1_acf_matches_phi_power_k():
    """AR(1): r_t = φ r_{t-1} + ε → ρ(k) = φ^k。"""
    for phi in (0.5, 0.7):
        rng = np.random.default_rng(12345)
        n = 60_000
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + rng.standard_normal()
        acf = return_acf(x, max_lag=6)
        for k in range(1, 7):
            expected = phi ** k
            assert abs(acf[k - 1] - expected) < 0.03, (
                f"AR(1) φ={phi} lag {k}: got {acf[k - 1]:.4f}, expected {expected:.4f}"
            )


def test_white_noise_acf_within_bartlett_band():
    """iid 白色雑音: ACF は ±z/√n の外に出るのが ~5% 以下、|ρ| <= 1。"""
    rng = np.random.default_rng(7)
    n = 20_000
    wn = rng.standard_normal(n)
    acf = return_acf(wn, max_lag=100)
    band = bartlett_conf_band(n)
    assert np.all(np.abs(acf) <= 1.0 + 1e-9), "biased ACF は |ρ| <= 1 のはず"
    frac_outside = float(np.mean(np.abs(acf) > band))
    assert frac_outside < 0.10, f"白色雑音で {frac_outside:.1%} が Bartlett 帯外 (>10%)"


def test_hill_recovers_pareto_alpha():
    """Pareto(α) の tail index を Hill MLE が復元する (単調性含む)。"""
    rng = np.random.default_rng(99)
    p2 = rng.pareto(2.0, 200_000) + 1.0
    p3 = rng.pareto(3.0, 200_000) + 1.0
    h2 = hill_mle_tail_index(p2)
    h3 = hill_mle_tail_index(p3)
    assert abs(h2 - 2.0) < 0.2, f"Pareto(2.0): Hill={h2:.3f}"
    # 薄い尾ほど tail index は大きい (単調性)
    assert h3 > h2, f"Hill 単調性違反: Pareto(3.0)={h3:.3f} <= Pareto(2.0)={h2:.3f}"


def test_gaussian_excess_kurtosis_near_zero():
    """Gaussian: excess kurtosis ≈ 0。"""
    rng = np.random.default_rng(3)
    g = rng.standard_normal(200_000)
    k = kurtosis_windowed(g, window=1)
    assert abs(k) < 0.1, f"Gaussian excess kurtosis={k:.4f} (≈0 を期待)"


def test_fat_tail_positive_excess_kurtosis():
    """Student-t(5) など fat tail: excess kurtosis > 0。"""
    rng = np.random.default_rng(4)
    t = rng.standard_t(5, 200_000)
    k = kurtosis_windowed(t, window=1)
    assert k > 1.0, f"t(5) excess kurtosis={k:.3f} (>0 を期待)"


def test_log_returns_known_values_and_nan_mask():
    """既知価格列 → 既知 log-return、p<=0 は NaN。"""
    prices = np.array([100.0, 110.0, 121.0])
    r = log_returns_from_prices(prices)
    assert np.allclose(r, [np.log(1.1), np.log(1.1)]), f"log-return 不一致: {r}"
    # 非正価格は NaN マスク
    prices2 = np.array([100.0, 0.0, 50.0])
    r2 = log_returns_from_prices(prices2)
    assert np.isnan(r2).any(), "p<=0 を含む log-return は NaN を含むべき"


def test_volatility_acf_positive_for_garch_like():
    """|r| の ACF は volatility clustering があれば正 (符号の健全性チェック)。"""
    rng = np.random.default_rng(11)
    n = 40_000
    # 単純な確率的ボラティリティ: σ_t が AR(1) で持続 → |r| に正の自己相関
    log_sig = np.zeros(n)
    for t in range(1, n):
        log_sig[t] = 0.95 * log_sig[t - 1] + 0.1 * rng.standard_normal()
    r = np.exp(log_sig) * rng.standard_normal(n)
    vacf = volatility_acf(r, max_lag=20)
    assert vacf[0] > bartlett_conf_band(n), f"|r| ACF(lag=1)={vacf[0]:.4f} が有意でない"


def test_plot_hold_ratio_uses_true_agent_count():
    """#7: plot_hold_ratio は final_wealth 長を真の N として使う (max 和推定でない)。"""
    pytest.importorskip("matplotlib")
    import os
    import tempfile

    import matplotlib
    matplotlib.use("Agg")

    from stylized_facts.core import plot_hold_ratio

    N, T = 1000, 200
    rng = np.random.default_rng(0)
    nb = rng.integers(50, 150, T).astype(float)
    ns = rng.integers(50, 150, T).astype(float)
    na = rng.integers(100, 200, T).astype(float)
    npas = rng.integers(100, 200, T).astype(float)
    # どの step でも buy+sell+act+pas < N (idle が常に存在) → max 和は N を下回る
    res = {
        "num_buy": nb, "num_sell": ns,
        "num_active_hold": na, "num_passive_hold": npas,
        "final_wealth": np.ones(N),
    }
    tmp = tempfile.mktemp(suffix=".png")
    try:
        out = plot_hold_ratio(res, tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    assert out["N_est"] == N, f"N_est={out['N_est']} != 真値 {N}"
    ratio_sum = out["idle"] + out["active_hold"] + out["passive_hold"] + out["buy"] + out["sell"]
    assert abs(ratio_sum - 1.0) < 1e-9, f"action ratio の和が 1 でない: {ratio_sum}"
    # idle 率は真の N 基準で ~0.5、旧 max 和推定なら 0 付近に潰れていた
    assert out["idle"] > 0.3, f"idle 率が過小 ({out['idle']:.3f}) — N 推定が誤り"


if __name__ == "__main__":
    import sys as _sys

    mod = _sys.modules[__name__]
    for _name in sorted(dir(mod)):
        if _name.startswith("test_"):
            getattr(mod, _name)()
    print("[analytic-ground-truth] ✓ all pass")
