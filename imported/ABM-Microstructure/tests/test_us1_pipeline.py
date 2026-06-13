"""T012: US1 e2e スモーク — train→measure→impulse_response→certify が縮小スケールで
決定論完走する（quickstart §単一セルの手順）。certified の真偽は問わない（null も結論）。
実スケール（t_max=2e6）の研究実行は harness 完成後・予算 ledger 管理下（tasks.md 方針）。
"""
import math

from microstructure.learnconfig import LearnConfig
from microstructure.qlearn import train
from microstructure.verdict import certify, impulse_response, measure

CFG = LearnConfig(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=1.0,
                  n_mm=2, memory=1, t_max=60_000, stable_window=15_000,
                  measure_periods=3_000, seed=0)


def test_us1_pipeline_end_to_end():
    cells, irs = [], []
    for s in (0, 1):
        cfg = CFG.replace(seed=s)
        tr = train(cfg)
        assert tr.periods_run > 0
        m = measure(cfg, tr)
        ir = impulse_response(cfg, tr)
        assert math.isfinite(m.markup) and math.isfinite(m.realized_spread)
        assert m.floors["nash"] > 0 and m.floors["zi"] > 0
        assert len(ir.profiles) == cfg.ir_pre + cfg.ir_horizon
        assert isinstance(ir.punished, bool) and isinstance(ir.restored, bool)
        cells.append(m)
        irs.append(ir)
    verdict = certify(cells, irs)
    assert isinstance(verdict.certified, bool)
    assert verdict.n_seeds == 2


def test_us1_pipeline_deterministic():
    tr1, tr2 = train(CFG), train(CFG)
    m1, m2 = measure(CFG, tr1), measure(CFG, tr2)
    assert m1.markup == m2.markup
    ir1, ir2 = impulse_response(CFG, tr1), impulse_response(CFG, tr2)
    assert ir1.profiles == ir2.profiles
