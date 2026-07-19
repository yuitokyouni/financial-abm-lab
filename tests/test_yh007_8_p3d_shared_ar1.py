"""YH007-8 P3-D: SharedAR1Hub (共有 AR(1) 共通因子 ZI 対照) の unit test。

D 対照の設計要件:
  - S2: 全 shared_ar1 agent が同一 bar で同一 center を読む (rank offset のみ差)
  - cadence: AR(1) は bar ごとに 1 回だけ進む (bar 内固定 = Kronos hub と同じ)
  - 決定性: 同 seed → 同 center 系列
  - 安定性: φ<1 で発散しない
"""
from __future__ import annotations

import numpy as np

from abm_models.self_organized_book import SelfOrganizedBookMarket, SharedAR1Hub


def _run_shared(seed=5, band=0.0, anchor_bars=0, main_steps=500):
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=main_steps,
        n_zi=8, zi_mode="naive",
        n_zi_strategy=6,
        zi_strategy_mode="shared_ar1",
        zi_strategy_phi_ar1=0.418, zi_strategy_sigma_ar1_abs=6e-3, zi_strategy_mu_ar1=0.0,
        zi_strategy_margin_min=2.5e-5, zi_strategy_margin_max=1.2e-4,
        zi_strategy_band_halfwidth=band,
        zi_strategy_anchor_smooth_bars=anchor_bars,
        bar_size=10, order_ttl=10,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    return m.run(seed=seed)


def _v_per_bar_per_agent(res):
    """{bar: {agent_id: v}} を strategy agent の action_log から復元。"""
    bar_size = res["bar_size"]
    out: dict[int, dict[int, float]] = {}
    for a in res["zi_agents"]:
        if getattr(a, "zi_mode", "") != "shared_ar1":
            continue
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload:
                continue
            out.setdefault(t // bar_size, {})[a.agent_id] = float(payload["v"])
    return out


def test_shared_ar1_same_center_within_bar_when_band_zero():
    """W=0 なら同一 bar の全 strategy agent の v が完全一致 (S2 の実装確認)。"""
    res = _run_shared(band=0.0)
    per_bar = _v_per_bar_per_agent(res)
    checked = 0
    for bar, vmap in per_bar.items():
        if len(vmap) >= 2:
            vs = list(vmap.values())
            assert max(vs) - min(vs) < 1e-12, f"bar {bar}: v not shared: {vs}"
            checked += 1
    assert checked >= 10, f"共有確認できた bar が少なすぎる: {checked}"


def test_shared_ar1_band_spread_matches_ranks():
    """W>0 なら bar 内の v の広がりが W·(rank_max−rank_min)·2 に一致。"""
    band = 0.02
    res = _run_shared(band=band)
    # n=6 → rank = (i+0.5)/6 → 幅 = 2W(0.9167−0.0833) = 2W·(5/6)
    expect = 2.0 * band * (5.0 / 6.0)
    per_bar = _v_per_bar_per_agent(res)
    spreads = [max(v.values()) - min(v.values())
               for v in per_bar.values() if len(v) == 6]
    assert len(spreads) >= 5, "全 6 agent が同 bar に揃った bar が少なすぎる"
    for s in spreads:
        assert abs(s - expect) < 1e-9, f"spread={s}, expect={expect}"


def test_shared_ar1_hub_advances_once_per_bar_and_deterministic():
    """hub log: bar ごとに 1 entry、bar index は狭義単調増加。同 seed で再現。"""
    res1 = _run_shared(seed=7)
    res2 = _run_shared(seed=7)
    log1, log2 = res1["zi_shared_hub_log"], res2["zi_shared_hub_log"]
    assert len(log1) >= 30
    bars = [e[0] for e in log1]
    assert all(b2 > b1 for b1, b2 in zip(bars, bars[1:])), "bar index が単調でない"
    assert log1 == log2, "同 seed で hub 系列が再現しない"
    res3 = _run_shared(seed=8)
    assert res3["zi_shared_hub_log"] != log1, "異 seed で同一系列 (RNG 独立性が疑わしい)"


def test_shared_ar1_does_not_diverge():
    """φ<1 + mid/SMA 係留で価格が発散しない (matched_ar1 と同じ健全性)。"""
    for anchor_bars in (0, 8):
        res = _run_shared(seed=3, anchor_bars=anchor_bars, main_steps=800)
        closes = res["history_mid"]["close"].to_numpy()
        drift_abs = abs(float(closes[-1]) - 300.0)
        assert drift_abs < 1.0, f"anchor_bars={anchor_bars}: drifted {drift_abs}"


def test_per_agent_hub_scope_gives_independent_v():
    """hub_scope='per_agent' (P3-E): W=0 でも bar 内の v が agent 間で一致しない。"""
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=500,
        n_zi=8, zi_mode="naive",
        n_zi_strategy=6,
        zi_strategy_mode="shared_ar1",
        zi_strategy_phi_ar1=0.418, zi_strategy_sigma_ar1_abs=6e-3,
        zi_strategy_margin_min=2.5e-5, zi_strategy_margin_max=1.2e-4,
        zi_strategy_band_halfwidth=0.0,
        zi_strategy_anchor_smooth_bars=8,
        zi_strategy_hub_scope="per_agent",
        bar_size=10, order_ttl=10,
        sigma_eval=5e-5, margin_min=2.0e-5, margin_max=6.0e-5,
        tick_size=0.001, initial_market_price=300.0,
    )
    res = m.run(seed=5)
    per_bar = _v_per_bar_per_agent(res)
    distinct_bars = sum(
        1 for v in per_bar.values()
        if len(v) >= 2 and max(v.values()) - min(v.values()) > 1e-9
    )
    assert distinct_bars >= 10, f"per_agent なのに v が共有されている (distinct={distinct_bars})"


def test_shared_hub_sma_anchor_unit():
    """SMA anchor の単体挙動: stub market で bar 更新と anchor 平均を確認。"""

    class _StubMarket:
        def __init__(self):
            self.t = 0
            self.prices = {}

        def get_time(self):
            return self.t

        def get_market_price(self, t=None):
            return self.prices.get(t)

    hub = SharedAR1Hub(phi=0.5, sigma=0.0, mu=0.0, band_halfwidth=0.0,
                       bar_size=10, anchor_smooth_bars=2, seed=1)
    mkt = _StubMarket()
    # bar0-1 の close (t=9, 19) を仕込み、bar2 で SMA(2) が読まれる
    mkt.prices[9] = 100.0
    mkt.prices[19] = 110.0
    mkt.t = 25  # bar_index = 2
    c = hub.ensure_current(mkt, mid=999.0)  # sigma=0 → center = anchor
    assert abs(c - 105.0) < 1e-12, f"SMA anchor expected 105, got {c}"
    # 同 bar 内は固定 (mid が変わっても再計算しない)
    c2 = hub.ensure_current(mkt, mid=500.0)
    assert c2 == c
    # SMA が取れない初期 bar は mid fallback
    hub2 = SharedAR1Hub(phi=0.5, sigma=0.0, bar_size=10, anchor_smooth_bars=2, seed=1)
    mkt2 = _StubMarket()
    mkt2.t = 3
    c3 = hub2.ensure_current(mkt2, mid=42.0)
    assert abs(c3 - 42.0) < 1e-12
