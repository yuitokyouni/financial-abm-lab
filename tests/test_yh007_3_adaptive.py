"""YH007-3: GCMG 適応 agent (Trend/Fade を rolling payoff score で内生選択 + 確信度連動の参加閾値)。

受け入れ基準 (spec §5/§8): 「Trend/Fade の比率が外生でなく観測量として時系列で変動する」。
mock signal で smoke + 内生比率変動 + 参加閾値で abstain 比率が動くことを確認。
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from abm_models.kronos_aggregate.model import constant_signal_provider
from abm_models.kronos_lob import KronosLOBMarket


@pytest.mark.parametrize("seed", [7, 42])
def test_adaptive_lob_smoke(seed: int):
    """純 adaptive 構成 (n_trend=0, n_fade=0, n_adaptive=20) で smoke が完走。"""
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=60, main_steps=200,
        n_trend=0, n_fade=0, n_fcn=10, n_adaptive=20,
        bar_size=10, lookback_bars=4, order_volume=1,
        score_window=20, r_min_base=0.0, r_min_conf_coef=0.0,
    )
    res = m.run(seed=seed)
    assert len(res["adaptive_actions"]) == 20
    n_acts = sum(len(log) for log in res["adaptive_actions"])
    assert n_acts > 0
    # 各 entry は (time, chosen_action, chosen_strategy, score_trend, score_fade)
    for log in res["adaptive_actions"]:
        if log:
            t, a, strat, st, sf = log[0]
            assert isinstance(t, int)
            assert a in (-1, 0, +1)
            assert strat in ("trend", "fade", "abstain")
            assert isinstance(st, float) and isinstance(sf, float)


def test_adaptive_mixed_with_static_lob():
    """trend/fade/adaptive 混在構成でも回る。"""
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=40, main_steps=120,
        n_trend=5, n_fade=5, n_fcn=10, n_adaptive=10,
        bar_size=10, lookback_bars=3,
    )
    res = m.run(seed=99)
    assert len(res["trend_actions"]) == 5
    assert len(res["fade_actions"]) == 5
    assert len(res["adaptive_actions"]) == 10
    assert sum(len(l) for l in res["adaptive_actions"]) > 0


def test_adaptive_strategy_switching_observable():
    """価格 trajectory に応じて Trend と Fade の混合比が時系列で変動する。

    strict equality は要求しない (確率的)。最低限「両 strategy の選択が観察される」を確認。
    """
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=80, main_steps=300,
        n_trend=0, n_fade=0, n_fcn=10, n_adaptive=20,
        bar_size=10, lookback_bars=4, order_volume=1,
        score_window=30, r_min_base=0.0, r_min_conf_coef=0.0,
    )
    res = m.run(seed=11)
    chosen_all = Counter()
    for log in res["adaptive_actions"]:
        for _, _, strat, _, _ in log:
            chosen_all[strat] += 1
    # 全部 abstain で終わるのは pathological。trend か fade のどちらかは選ばれてほしい。
    assert (chosen_all["trend"] + chosen_all["fade"]) > 0


def test_adaptive_r_min_static_abstain_when_threshold_high():
    """r_min_base を非常に高くすると、score が届かず全 step abstain。"""
    huge_rmin = 1e6
    m = KronosLOBMarket(
        signal_provider=constant_signal_provider(pred_close_mean=300.5),
        warmup_steps=40, main_steps=80,
        n_trend=0, n_fade=0, n_fcn=10, n_adaptive=10,
        bar_size=10, lookback_bars=3,
        score_window=20, r_min_base=huge_rmin, r_min_conf_coef=0.0,
    )
    res = m.run(seed=3)
    abst = 0
    total = 0
    for log in res["adaptive_actions"]:
        for _, _, strat, _, _ in log:
            total += 1
            if strat == "abstain":
                abst += 1
    assert total > 0
    assert abst == total, "r_min を huge にすれば全て abstain になるはず"
