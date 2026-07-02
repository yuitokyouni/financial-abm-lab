"""YH007-8 P2 (spec 003 §3.6, §4): Kronos quantile-rank agent の smoke。

KRONOS_PATH 環境変数が無いとき or shiyu-coder/Kronos リポが置かれてないときは skip。
HF 接続 + Kronos weights のロードが必要なので、CI 環境では skip がデフォルト動作。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _kronos_available() -> bool:
    path = os.environ.get("KRONOS_PATH", "")
    return bool(path) and Path(path, "model", "kronos.py").exists()


pytestmark = pytest.mark.skipif(
    not _kronos_available(),
    reason="KRONOS_PATH not set or shiyu-coder/Kronos not present",
)


def test_kronos_ci_smoke_short_run():
    """KronosCIAgent (n_kronos=4) + ZI warmup の最小 smoke。"""
    from abm_models.self_organized_book import SelfOrganizedBookMarket
    m = SelfOrganizedBookMarket(
        warmup_steps=60, main_steps=120, n_zi=8, n_kronos=4,
        bar_size=10, order_ttl=10,
        sigma_eval=5e-5, margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=4, kronos_n_samples=8,
    )
    res = m.run(seed=7)
    # Kronos agent が action_log を持つ (lookback 経過後)
    assert len(res["kronos_agents"]) == 4
    n_kronos_acts = sum(len(a.action_log) for a in res["kronos_agents"])
    assert n_kronos_acts > 0, "Kronos agent が submit_orders を一度も呼んでない"
    # Kronos hub call log (bar 切替で 1 回 predict が走るはず)
    assert len(res["kronos_hub_calls"]) > 0, "Kronos hub の predict が呼ばれていない"
    # 各 call の dt が記録されている
    for bar_idx, dt, n_samples in res["kronos_hub_calls"]:
        assert dt > 0
        assert n_samples == 8
    # 約定が起きる
    assert res["n_executed"] > 0


def test_kronos_quantile_distinct_evaluations():
    """spec 003 §3.6: 各 agent が別 quantile を読み、評価値 v が agent 間で異なる。"""
    from abm_models.self_organized_book import SelfOrganizedBookMarket
    m = SelfOrganizedBookMarket(
        warmup_steps=40, main_steps=80, n_zi=8, n_kronos=6,
        bar_size=10, order_ttl=10,
        sigma_eval=5e-5, margin_min=3e-5, margin_max=1e-4,
        tick_size=0.001, initial_market_price=300.0,
        kronos_lookback_bars=3, kronos_n_samples=12,
    )
    res = m.run(seed=11)
    # agent_rank が 6 通り (0.083, 0.25, 0.417, 0.583, 0.75, 0.917) で割り当てられている
    ranks = sorted({a.agent_rank for a in res["kronos_agents"]})
    assert len(ranks) == 6, f"distinct ranks: {ranks}"
    # 同 bar で評価値 v_i が agent 間で異なる (action_log の payload["v"])
    bar_to_vs: dict[int, list[float]] = {}
    bar_size = res["bar_size"]
    for a in res["kronos_agents"]:
        for t, side, price, payload in a.action_log:
            if payload is None or "v" not in payload:
                continue
            bar_to_vs.setdefault(t // bar_size, []).append(float(payload["v"]))
    # ある bar で 2 つ以上の agent が評価していて、v が全部同じでないこと
    diverse_bars = 0
    for bar, vs in bar_to_vs.items():
        if len(vs) >= 2 and len(set(round(v, 6) for v in vs)) > 1:
            diverse_bars += 1
    assert diverse_bars > 0, "全 bar で全 agent の v が一致 = quantile-rank の分散注入が機能していない"
