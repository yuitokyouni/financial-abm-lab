"""② headline finding の検証: batch 抽出が厳密アンカーと一致し、
クロスオーバー（h≪J で batch 減・h~J で batch 増）が coding artifact でなく
モデルの抽出曲面の性質であることを確定する（finding 0001）。
"""
from dataclasses import replace

import numpy as np
import pytest

from microstructure import SimConfig, run
from microstructure import anchors

P = dict(lambda_jump=10.0, jump_size=1.0, alpha=0.4, dt=1e-2)


def _cfg(h, N, seed=0):
    return SimConfig(n_periods=400000, seed=seed, dt=P["dt"], alpha=P["alpha"],
                     lambda_jump=P["lambda_jump"], jump_size=P["jump_size"],
                     half_spread=h, noise_rate=1.0,
                     mechanism="batch" if N > 1 else "continuous", batch_interval=N)


def _sim_rate(h, N, seeds=6):
    r = np.array([run(_cfg(h, N, s)).extraction_rate for s in range(seeds)])
    return r.mean(), r.std(ddof=1) / np.sqrt(len(r))


@pytest.mark.parametrize("h,N", [(0.1, 1), (0.1, 10), (0.1, 20),
                                 (0.5, 5), (0.8, 1), (0.8, 10), (0.8, 20)])
def test_sim_matches_budish_anchor(h, N):
    anchor = anchors.budish_sniping_rent(P["lambda_jump"], P["jump_size"],
                                         P["alpha"], P["dt"], h, N)
    mean, se = _sim_rate(h, N)
    tol = max(4.0 * se, 0.03 * anchor + 1e-9)
    assert abs(mean - anchor) <= tol, f"sim {mean:.4f} vs anchor {anchor:.4f} (tol {tol:.4f})"


def test_crossover_is_real_in_anchor():
    """独立アンカー自身がクロスオーバーを示す（artifact でなくモデルの性質）。"""
    lo_c = anchors.budish_sniping_rent(**P, half_spread=0.1, batch_interval=1)
    lo_b = anchors.budish_sniping_rent(**P, half_spread=0.1, batch_interval=20)
    hi_c = anchors.budish_sniping_rent(**P, half_spread=0.8, batch_interval=1)
    hi_b = anchors.budish_sniping_rent(**P, half_spread=0.8, batch_interval=20)
    assert lo_b < lo_c      # 低 h（tight spread）: batch は抽出を減らす
    assert hi_b > hi_c      # 高 h（広い spread）: batch は抽出を増やす ← CROSSOVER


def test_crossover_reproduced_by_sim():
    """sim が両レジームの符号を再現 → クロスオーバーは本物。"""
    lo_c, _ = _sim_rate(0.1, 1)
    lo_b, _ = _sim_rate(0.1, 20)
    hi_c, _ = _sim_rate(0.8, 1)
    hi_b, _ = _sim_rate(0.8, 20)
    assert lo_b < lo_c
    assert hi_b > hi_c
