"""T010: IR gate 分類器の独立検証 — 本 feature 検証の本丸（research D-B7）。

gate が壊れていたら全認定が無意味になる。学習コードと独立な合成 policy で検出力を pin:
  - grim-trigger（2 相: 逸脱検知 → 1 期 below-break-even 懲罰 → 復帰）⇒ certified
  - 固定高止まり（逸脱に無反応）⇒ 懲罰なし & 逸脱有利 ⇒ ¬certified
IR rollout は決定論（frozen policy・解析収支）なので判定は bit 再現する。
"""
import numpy as np
import pytest

from microstructure import benchmarks
from microstructure.learnconfig import LearnConfig
from microstructure.qlearn import FixedPolicy, TrainResult
from microstructure.verdict import (CellMeasurement, certify, impulse_response,
                                    measure)

BASE = dict(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=1.0)
HI = 12   # 協調 spread（grid 上限の 2 つ下: undercut 余地を残す）
LOW = 0   # 懲罰 action = grid 下限（break-even 未満 → 懲罰は自傷的に高価 = 信憑性）


def _cfg(seed=0):
    return LearnConfig(n_mm=2, memory=1, seed=seed, **BASE)


def _grim_table(cfg) -> np.ndarray:
    """2 相 grim: (HI,HI)→HI 維持 / (LOW,LOW)→HI 復帰 / その他（逸脱検知）→LOW 懲罰。"""
    K = cfg.n_actions
    t = np.full(K * K, LOW)
    t[HI * K + HI] = HI
    t[LOW * K + LOW] = HI
    return t


def _flat_table(cfg) -> np.ndarray:
    """固定高止まり: 無条件 HI（懲罰構造なし）。"""
    return np.full(cfg.n_actions ** 2, HI)


def _tr(cfg, table) -> TrainResult:
    return TrainResult([FixedPolicy(table), FixedPolicy(table)], True, 0, 0)


def _cells(cfg, markup, n=5):
    nash = benchmarks.myopic_nash_spread(cfg)
    return [CellMeasurement(seed=s, realized_spread=nash * (1 + markup), markup=markup,
                            extraction_rate=0.0, mm_pnl=0.0,
                            floors={"zi": 0.0, "nash": nash, "monopoly": 0.0},
                            exited=False, converged=True)
            for s in range(n)]


def test_grim_trigger_certified():
    cfg = _cfg()
    ir = impulse_response(cfg, _tr(cfg, _grim_table(cfg)))
    assert ir.baseline_profile == (HI, HI)        # pre 窓で協調に到達
    assert ir.deviation_action == HI - 1          # myopic BR = 1 tick undercut
    assert ir.punished and ir.punish_lag == 1     # 相手が即タイト化
    assert not ir.deviation_profitable            # 懲罰込みで逸脱は割に合わない
    assert ir.restored                            # 協調が再確立
    verdict = certify(_cells(cfg, markup=0.5), [ir] * 5)
    assert verdict.certified


def test_flat_high_not_certified():
    """高止まり: markup は高くても懲罰構造が無い → gate が落とす（A3 の核心）。"""
    cfg = _cfg()
    ir = impulse_response(cfg, _tr(cfg, _flat_table(cfg)))
    assert not ir.punished
    assert ir.deviation_profitable                # 無反応なら undercut し得
    verdict = certify(_cells(cfg, markup=0.5), [ir] * 5)
    assert not verdict.certified


def test_markup_floor_blocks_tiny_markup():
    """微小 markup は懲罰構造があっても collusion と呼ばない（5% floor）。"""
    cfg = _cfg()
    ir = impulse_response(cfg, _tr(cfg, _grim_table(cfg)))
    verdict = certify(_cells(cfg, markup=0.01), [ir] * 5)
    assert not verdict.certified


def test_nonconverged_blocks_certification():
    cfg = _cfg()
    ir = impulse_response(cfg, _tr(cfg, _grim_table(cfg)))
    cells = _cells(cfg, markup=0.5)
    cells[0].converged = False
    assert not certify(cells, [ir] * 5).certified


def test_ir_deterministic():
    """決定論: 同一入力 → 同一 IRResult（探索ノイズの混入が構造的に無い）。"""
    cfg = _cfg()
    tr = _tr(cfg, _grim_table(cfg))
    a, b = impulse_response(cfg, tr), impulse_response(cfg, tr)
    assert (a.punished, a.punish_lag, a.deviation_profitable, a.restored,
            a.baseline_profile, a.deviation_action, a.profiles) == \
           (b.punished, b.punish_lag, b.deviation_profitable, b.restored,
            b.baseline_profile, b.deviation_action, b.profiles)


def test_measure_deterministic_with_fixed_policies():
    cfg = _cfg(seed=11)
    tr = _tr(cfg, _grim_table(cfg))
    m1, m2 = measure(cfg, tr), measure(cfg, tr)
    assert m1 == m2
    assert m1.realized_spread == pytest.approx(cfg.action_grid[HI])  # 協調 spread で安定
