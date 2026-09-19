"""YH007-6/7: Predator (機構 4) と Spoofer (機構 5) の最小疎通。

両 agent は Kronos 信号と無関係 (板情報のみ)。on/off で SF が動くか後段 experiment で
ablation する。本テストは agent が起動・記録・order 送信を行うことの確認まで。
"""
from __future__ import annotations

import pytest

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket


def test_predator_smoke():
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=40, main_steps=120,
        n_trend=4, n_fade=4, n_fcn=10, n_predator=5,
        bar_size=10, lookback_bars=3,
    )
    res = m.run(seed=7)
    assert "predation_logs" in res
    assert len(res["predation_logs"]) == 5
    # 5 体の予測 agent それぞれ predation_log を持つ (空配列でも OK = 板改善が一度も無かったケース)
    for log in res["predation_logs"]:
        assert isinstance(log, list)
        for entry in log:
            t, side, price = entry
            assert isinstance(t, int)
            assert side in ("sell_into_bid_improvement", "buy_into_ask_improvement")
            assert price > 0
    # 少なくとも 1 件は捕食記録があるはず (200 step で MMFCN 30 体が動けば改善は起きる)
    total = sum(len(log) for log in res["predation_logs"])
    assert total > 0, f"全 step で板改善が無かった (期待外): total={total}"


def test_spoofer_smoke():
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=40, main_steps=120,
        n_trend=4, n_fade=4, n_fcn=10, n_spoofer=3,
        bar_size=10, lookback_bars=3,
        spoof_volume=200, spoof_offset_ticks=5, spoof_side="both", spoof_ttl=1,
    )
    res = m.run(seed=7)
    assert "spoof_logs" in res
    assert len(res["spoof_logs"]) == 3
    total = sum(len(log) for log in res["spoof_logs"])
    # both で毎 step 2 つ (buy_layer + sell_layer) × 3 spoofer × N step だけ出る
    assert total > 0, f"spoofer は毎 step LIMIT を出すはず (見せ板)"
    for log in res["spoof_logs"]:
        for t, side, price, vol in log:
            assert side in ("buy_layer", "sell_layer")
            assert price > 0
            assert vol == 200


def test_spoofer_one_sided():
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=20, main_steps=40,
        n_trend=2, n_fade=2, n_fcn=8, n_spoofer=2,
        bar_size=10, lookback_bars=2,
        spoof_volume=50, spoof_offset_ticks=3, spoof_side="buy",
    )
    res = m.run(seed=3)
    for log in res["spoof_logs"]:
        for _, side, _, _ in log:
            assert side == "buy_layer", f"spoofSide=buy なのに {side} が出た"


def test_predator_and_spoofer_coexist():
    """両 agent を同時に有効化しても完走。"""
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=20, main_steps=60,
        n_trend=2, n_fade=2, n_fcn=8, n_adaptive=4,
        n_predator=2, n_spoofer=2,
        bar_size=10, lookback_bars=2,
        spoof_volume=50, spoof_offset_ticks=3,
    )
    res = m.run(seed=11)
    assert res["prices"].size > 0


def test_spoof_side_validation():
    """spoofSide='invalid' は ValueError を上げる (PAMS の agent 構築時 or setup 時)。

    注: pams は agent 生成時に setup を呼ぶ。invalid value で ValueError が伝播する。
    """
    with pytest.raises(Exception):
        m = KronosLOBMarket(
            signal_provider=constant_signal_provider(pred_close_mean=300.5),
            warmup_steps=20, main_steps=30,
            n_trend=0, n_fade=0, n_fcn=5, n_spoofer=1,
            bar_size=10, lookback_bars=2,
            spoof_side="invalid",
        )
        m.run(seed=1)
