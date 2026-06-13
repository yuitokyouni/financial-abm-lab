"""T015: US2 条件比較の機構検証。

核は finding 0001 クロスオーバーの B env 再現（学習なし・固定 quote）:
  h > J: 連続は抽出**恒等 0**（単発 jump が spread を超えない）/ batch は accumulated
         net 変位で抽出 > 0 —— 決定論の符号反転（collusive な広い spread を batch が
         sniping に晒す、という predation チャネルの前提条件そのもの）。
  h ≪ J: batch < 連続（netting、Budish 的）。
"""
import numpy as np
import pytest

from microstructure import anchors
from microstructure.designmap import (CONDITIONS, classify_modulation,
                                      compare_conditions, write_csv)
from microstructure.env import MarketEnv, derive_rngs
from microstructure.learnconfig import LearnConfig

BASE = dict(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, noise_rate=1.0)


def _extraction_rate(cfg, action_idx, periods):
    env = MarketEnv(cfg, derive_rngs(cfg)["env"])
    total = 0.0
    for _ in range(periods):
        _, info = env.step((action_idx,))
        total += info["extraction"]
    return total / (periods * cfg.period_steps * cfg.dt)


def test_crossover_high_h_batch_exposes_wide_spread():
    """h>J: 連続の抽出は恒等 0、batch は >0（finding 0001 高 h 側、決定論）。"""
    a = 6  # grid[6] ≈ 1.029 > J=1
    cont = LearnConfig(n_mm=1, seed=0, **BASE)
    bat = LearnConfig(n_mm=1, seed=0, mechanism="batch", batch_interval=20, **BASE)
    assert cont.action_grid[a] > cont.jump_size
    assert _extraction_rate(cont, a, 60000) == 0.0
    assert _extraction_rate(bat, a, 3000) > 0.0
    # 独立アンカーも同じ符号を出す（モデル性質であって env バグでないことの照合）
    h = cont.action_grid[a]
    assert anchors.budish_sniping_rent(5.0, 1.0, 0.3, 1e-2, h, 1) == 0.0
    assert anchors.budish_sniping_rent(5.0, 1.0, 0.3, 1e-2, h, 20) > 0.0


def test_crossover_low_h_batch_reduces_extraction():
    """h≪J: batch < 連続（netting）。アンカーの予言する比率と同方向（統計判定）。"""
    a = 0  # grid[0] = 0.3
    cont = LearnConfig(n_mm=1, seed=1, **BASE)
    bat = LearnConfig(n_mm=1, seed=1, mechanism="batch", batch_interval=20, **BASE)
    h = cont.action_grid[a]
    a_cont = anchors.budish_sniping_rent(5.0, 1.0, 0.3, 1e-2, h, 1)
    a_bat = anchors.budish_sniping_rent(5.0, 1.0, 0.3, 1e-2, h, 20)
    assert a_bat < a_cont  # アンカー側の符号（前提確認）
    r_cont = _extraction_rate(cont, a, 120000)
    r_bat = _extraction_rate(bat, a, 6000)
    assert r_bat < r_cont * 0.95
    assert r_cont == pytest.approx(a_cont, rel=0.10)
    assert r_bat == pytest.approx(a_bat, rel=0.15)


def test_classify_modulation_boundaries():
    assert classify_modulation(np.array([0.10, 0.12, 0.11, 0.09])) == "促進"
    assert classify_modulation(np.array([-0.10, -0.12, -0.11, -0.09])) == "抑制"
    assert classify_modulation(np.array([0.10, -0.12, 0.02, -0.05])) == "無影響"
    with pytest.raises(ValueError):
        classify_modulation(np.array([0.1]))


def test_compare_conditions_e2e_smoke(tmp_path):
    """4 条件 {cont, batch5} × {committed, revisable} の縮小 e2e:
    points/modulation/attribution が揃い、revisable の抽出は 0、CSV に書ける。"""
    base = LearnConfig(n_mm=2, memory=1, t_max=20_000, stable_window=5_000,
                       measure_periods=2_000, **BASE)
    conds = (("continuous", 1, "committed"), ("batch", 5, "committed"),
             ("continuous", 1, "revisable"), ("batch", 5, "revisable"))
    out = compare_conditions(base, seeds=[0, 1], conditions=conds)
    assert len(out["points"]) == 4
    for p in out["points"].values():
        if p.staleness == "revisable":
            assert p.extraction_mean == 0.0
        assert p.n_seeds == 2 and p.periods_total > 0
    mod = out["modulation"]
    assert (5, "committed") in mod and (5, "revisable") in mod
    assert mod[(5, "committed")]["class"] in ("促進", "抑制", "無影響")
    att = out["attribution"][5]
    assert att["delta_pred"] == pytest.approx(att["delta_total"] - att["delta_gp"])
    out_csv = tmp_path / "smoke_map.csv"
    write_csv(list(out["points"].values()), out_csv)
    import csv as _csv
    with open(out_csv, encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 4 and "markup_mean" in rows[0]
