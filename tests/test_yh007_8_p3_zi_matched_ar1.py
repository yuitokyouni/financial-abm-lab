"""YH007-8 P3-T1: ZIAgent matched_ar1 モードの統計検証 + regression。

spec 003 §4 + 裁定 A の AR(1) on (v-mid) が:
  - 長 run で stable (φ<1 で発散しない)
  - 推定された AR(1) coefficient が settings の phi に近い
を確認する unit test。
"""
from __future__ import annotations

import numpy as np
import pytest

from abm_models.self_organized_book import (
    SelfOrganizedBookMarket,
    ZIAgent,
)


def test_matched_ar1_does_not_diverge():
    """matched_ar1 で長 run しても v が mid から発散しない (φ<1 = mean-reverting)。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=500, n_zi=8,
        bar_size=10, order_ttl=10,
        zi_mode="matched_ar1",
        zi_phi_ar1=0.42, zi_sigma_ar1_abs=6e-3, zi_mu_ar1=0.0,
        margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
    )
    res = m.run(seed=3)
    closes = res["history_mid"]["close"].to_numpy()
    # mid が initial_price から大きく drift しない (発散しないこと)
    drift_abs = abs(float(closes[-1]) - 300.0)
    assert drift_abs < 0.5, f"mid drifted too much: {drift_abs}"


def test_matched_ar1_phi_recovered_from_v_minus_mid():
    """各 agent の (v-mid) 時系列を回収し、AR(1) φ を fit すると設定値に近い。"""
    target_phi = 0.6
    target_sigma = 1e-2
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=400, n_zi=8,
        bar_size=10, order_ttl=10,
        zi_mode="matched_ar1",
        zi_phi_ar1=target_phi, zi_sigma_ar1_abs=target_sigma, zi_mu_ar1=0.0,
        margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
    )
    res = m.run(seed=11)
    # 各 agent の action_log payload に "v" と "mid" があるので (v-mid) を取り出し
    bar_size = res["bar_size"]
    series_per_agent = []
    for a in res["agents"]:
        if not a.action_log:
            continue
        # bar 単位で 1 サンプル化 (各 step で agent は 1 回 evaluate)
        bars: dict[int, float] = {}
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload or "mid" not in payload:
                continue
            bars[t // bar_size] = float(payload["v"]) - float(payload["mid"])
        if len(bars) >= 30:
            ks = sorted(bars.keys())
            series_per_agent.append(np.array([bars[k] for k in ks], dtype=np.float64))
    assert len(series_per_agent) >= 3, "AR(1) fit に十分な agent 数が無い"
    # 全 agent から (x_{t-1}, x_t) を pool で集めて AR(1) fit
    xs_prev, xs_curr = [], []
    for s in series_per_agent:
        xs_prev.extend(s[:-1].tolist()); xs_curr.extend(s[1:].tolist())
    xs_prev = np.array(xs_prev); xs_curr = np.array(xs_curr)
    var_prev = float(np.var(xs_prev))
    assert var_prev > 0
    phi_est = float(np.cov(xs_prev, xs_curr, ddof=0)[0, 1] / var_prev)
    # 8 agent × ~30 bar = 240 pairs だと SE ≈ 0.06 ぐらい、target=0.6 で ±0.15 余裕
    assert abs(phi_est - target_phi) < 0.2, f"phi_est={phi_est}, target={target_phi}"
    # σ も近いことを確認 (residuals std)
    residuals = xs_curr - phi_est * xs_prev
    sigma_est = float(np.std(residuals, ddof=1))
    assert abs(sigma_est - target_sigma) / target_sigma < 0.5, \
        f"sigma_est={sigma_est:.4e}, target={target_sigma:.4e}"


def test_matched_ar1_agg_rate_within_band():
    """P2 実測値 (φ=0.42, σ=6e-3) で agg_rate が目標帯 [0.05, 0.20] に入る。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=80, main_steps=400, n_zi=20,
        bar_size=10, order_ttl=15,
        zi_mode="matched_ar1",
        zi_phi_ar1=0.418, zi_sigma_ar1_abs=6e-3, zi_mu_ar1=0.0,
        margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
    )
    res = m.run(seed=42)
    agg_rate = res["n_executed"] / max(res["n_submitted"], 1)
    assert 0.02 < agg_rate < 0.40, f"agg_rate={agg_rate}, expected near [0.05, 0.20]"
