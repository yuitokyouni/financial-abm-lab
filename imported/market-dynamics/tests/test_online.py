"""Phase 8 — online causal F monitor / state machine / strategy tests.

The big invariant is the LEAKAGE CANARY: corrupting all post-train data must
not change the trained atlas (grid, percentiles).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from state_atlas.online.monitor import (
    fit_train_window,
    project_new,
)
from state_atlas.online.state_machine import (
    StateConfig,
    classify,
    classify_series,
)
from state_atlas.online.strategy import (
    StrategyConfig,
    target_weights_risk_overlay,
    target_weights_vol_carry,
)


def _synth_op(n: int = 800, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-02", periods=n)
    log_vix = 2.7 + 0.6 * rng.standard_normal(n).cumsum() * 0.05
    term_slope = 0.10 - 0.15 * (log_vix - 2.7)  # negative correlation
    term_slope += 0.03 * rng.standard_normal(n)
    return pd.DataFrame({"log_vix": log_vix, "term_slope": term_slope}, index=idx)


# ---------------------------------------------------------------------------
# Leakage canary — train fit must not change when post-train is corrupted
# ---------------------------------------------------------------------------


def test_leakage_canary_train_fit_invariant_under_future_corruption() -> None:
    op = _synth_op(n=600, seed=1)
    train = op.iloc[:400]
    a1 = fit_train_window(train)

    rng = np.random.default_rng(99)
    op_corrupt = op.copy()
    op_corrupt.iloc[400:] = rng.standard_normal((200, 2)) * 100 + np.array([50.0, 50.0])
    train_corrupt = op_corrupt.iloc[:400]
    a2 = fit_train_window(train_corrupt)

    np.testing.assert_array_equal(a1.grid.z1, a2.grid.z1)
    np.testing.assert_array_equal(a1.grid.z2, a2.grid.z2)
    np.testing.assert_allclose(a1.grid.F, a2.grid.F)
    assert a1.F_p50 == a2.F_p50
    assert a1.F_p90 == a2.F_p90
    assert a1.F_p99 == a2.F_p99


# ---------------------------------------------------------------------------
# Monitor / projection invariants
# ---------------------------------------------------------------------------


def test_project_new_returns_one_value_per_query_point() -> None:
    op = _synth_op(n=400)
    atlas = fit_train_window(op.iloc[:300])
    F = project_new(atlas, op.iloc[300:]["log_vix"], op.iloc[300:]["term_slope"])
    assert F.shape == (100,)
    assert (F >= 0).all()


def test_percentile_ordering() -> None:
    op = _synth_op(n=500)
    atlas = fit_train_window(op)
    assert atlas.F_p50 <= atlas.F_p90 <= atlas.F_p99


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_state_label_responds_to_F_thresholds() -> None:
    op = _synth_op(n=500)
    atlas = fit_train_window(op)
    s_low = classify(F=atlas.F_p50 - 0.5, term_slope=0.1, backw_run=0, F_p99_run=0, atlas=atlas)
    s_mid = classify(
        F=(atlas.F_p50 + atlas.F_p90) / 2, term_slope=0.1, backw_run=0, F_p99_run=0, atlas=atlas
    )
    s_high = classify(F=atlas.F_p90 + 0.5, term_slope=0.1, backw_run=0, F_p99_run=0, atlas=atlas)
    assert s_low.label == "CALM"
    assert s_mid.label == "ELEVATED"
    assert s_high.label == "STRESS"


def test_backwardation_triggers_stress_or_elevated() -> None:
    op = _synth_op(n=500)
    atlas = fit_train_window(op)
    s = classify(F=atlas.F_p50 - 0.5, term_slope=-0.1, backw_run=0, F_p99_run=0, atlas=atlas)
    # Mild F but inverted curve: per design, ELEVATED early-warning.
    assert s.label == "ELEVATED"
    s2 = classify(F=atlas.F_p90 + 0.5, term_slope=-0.1, backw_run=0, F_p99_run=0, atlas=atlas)
    assert s2.label == "STRESS"


def test_persistent_stress_requires_run_threshold() -> None:
    op = _synth_op(n=500)
    atlas = fit_train_window(op)
    cfg = StateConfig(backw_persist_days=10, F_p99_persist_days=5)
    # 9 days of backwardation: not persistent yet
    s = classify(
        F=atlas.F_p50 - 0.5, term_slope=-0.1, backw_run=9, F_p99_run=0, atlas=atlas, cfg=cfg
    )
    assert not s.persistent_stress
    # 10 days: persistent
    s = classify(
        F=atlas.F_p50 - 0.5, term_slope=-0.1, backw_run=10, F_p99_run=0, atlas=atlas, cfg=cfg
    )
    assert s.persistent_stress


def test_classify_series_counters_are_causal() -> None:
    """If we truncate the input, the surviving rows keep the same state."""
    op = _synth_op(n=300)
    atlas = fit_train_window(op.iloc[:200])
    F_full = pd.Series(project_new(atlas, op["log_vix"], op["term_slope"]), index=op.index)
    states_full = classify_series(F_full, op["term_slope"], atlas)
    states_trunc = classify_series(F_full.iloc[:250], op["term_slope"].iloc[:250], atlas)
    pd.testing.assert_frame_equal(
        states_full.iloc[:250].reset_index(drop=True),
        states_trunc.reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


def test_risk_overlay_is_monotone_in_F() -> None:
    op = _synth_op()
    atlas = fit_train_window(op)
    cfg = StrategyConfig()
    Fs = [atlas.F_p50 - 1, atlas.F_p50, (atlas.F_p50 + atlas.F_p90) / 2, atlas.F_p90, atlas.F_p99]
    weights = []
    for F in Fs:
        s = classify(F, 0.1, 0, 0, atlas)
        w = target_weights_risk_overlay(s, atlas, cfg)
        weights.append(w["base_asset"])
    # Monotonically non-increasing.
    for a, b in zip(weights[:-1], weights[1:], strict=True):
        assert a >= b - 1e-9


def test_persistent_stress_kills_position_in_both_modes() -> None:
    op = _synth_op()
    atlas = fit_train_window(op)
    s = classify(F=0.0, term_slope=-0.1, backw_run=20, F_p99_run=0, atlas=atlas)
    assert s.persistent_stress
    w_ro = target_weights_risk_overlay(s, atlas)
    w_vc = target_weights_vol_carry(s, atlas)
    assert w_ro["base_asset"] == 0.0
    assert w_vc["SVXY"] == 0.0
    assert w_vc["VXX"] == 0.0


def test_vol_carry_full_long_in_calm_contango() -> None:
    op = _synth_op()
    atlas = fit_train_window(op)
    s = classify(F=atlas.F_p50 - 1.0, term_slope=0.15, backw_run=0, F_p99_run=0, atlas=atlas)
    assert s.label == "CALM"
    w = target_weights_vol_carry(s, atlas)
    assert w["SVXY"] == 1.0
    assert w["VXX"] == 0.0
