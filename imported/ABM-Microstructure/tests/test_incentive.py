"""SC-006 / US3: participation margin（competitive frame で vacuous を回避）。

margin = fee·(noise 約定量) − sniping 損(extraction) − 機会コスト·T（AMM の
「swap fee − LVR − 機会コスト」と同型）。MM は固定 spread で流動性提供し、fee が
逆選択を補償できるかを問う。連続 vs batch が退出判定を反転させるか＝US3 の核。
batch が sniping を減らす tight-spread 領域（h≪J）で評価する。
"""
from dataclasses import replace

from microstructure import SimConfig, run


def _base(**kw):
    base = dict(n_periods=300000, seed=4, dt=1e-2, alpha=0.4, lambda_jump=10.0,
                jump_size=1.0, half_spread=0.1, noise_rate=1.0,
                fee=5.0, opp_cost=0.0)
    base.update(kw)
    return SimConfig(**base)


def test_fee_increases_margin():
    lo = run(_base(fee=0.0)).metrics.participation_margin
    hi = run(_base(fee=5.0)).metrics.participation_margin
    assert hi > lo


def test_opp_cost_can_force_exit():
    stay = run(_base(fee=5.0, opp_cost=0.0)).metrics.mm_exits
    exit_ = run(_base(fee=5.0, opp_cost=10.0)).metrics.mm_exits
    assert stay is False     # fee が sniping を補償 → 残留
    assert exit_ is True      # 機会コスト過大 → 退出


def test_batch_improves_participation():
    """batch は sniping を減らす → participation margin が上がる。"""
    cont = run(_base()).metrics.participation_margin
    batch = run(_base(mechanism="batch", batch_interval=20)).metrics.participation_margin
    assert batch > cont


def test_design_can_flip_exit_decision():
    """同一 (f,c) で連続=退出・batch=残留 となる領域を同定（US3 の核）。"""
    found = False
    for c in (1.0, 1.5, 2.0, 2.5, 3.0):
        cfg = _base(fee=5.0, opp_cost=c)
        cont_exit = run(cfg).metrics.mm_exits
        batch_exit = run(replace(cfg, mechanism="batch", batch_interval=20)).metrics.mm_exits
        if cont_exit and not batch_exit:
            found = True
            break
    assert found, "連続=退出 かつ batch=残留 の領域が見つからない"
