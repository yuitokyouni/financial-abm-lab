"""Ignition gate: external infra is locked until P1 GO + diagnostic case (task 6)."""

from __future__ import annotations

import pytest

from atlas.ignition import (
    DEFAULT_STATE,
    GATED_FEATURES,
    IgnitionLocked,
    IgnitionState,
    ignition_unlocked,
    require_ignition,
)


def test_default_state_is_locked() -> None:
    assert not ignition_unlocked(DEFAULT_STATE)
    assert DEFAULT_STATE.reasons_locked()


@pytest.mark.parametrize("feature", GATED_FEATURES)
def test_gated_features_raise_when_locked(feature: str) -> None:
    with pytest.raises(IgnitionLocked):
        require_ignition(feature)


def test_unknown_feature_rejected() -> None:
    with pytest.raises(ValueError):
        require_ignition("totally_made_up_feature")


def test_all_conditions_unlock() -> None:
    state = IgnitionState(
        p1_status="GO", diagnostic_case_present=True, canonical_rows=8
    )
    assert ignition_unlocked(state)
    require_ignition("leaderboard_or_profile_browser_ui", state)  # no raise


def test_partial_publishable_unlocks() -> None:
    state = IgnitionState(
        p1_status="PARTIAL_PUBLISHABLE", diagnostic_case_present=True, canonical_rows=10
    )
    assert ignition_unlocked(state)


def test_missing_diagnostic_keeps_locked() -> None:
    state = IgnitionState(p1_status="GO", diagnostic_case_present=False, canonical_rows=8)
    assert not ignition_unlocked(state)
    with pytest.raises(IgnitionLocked):
        require_ignition("versioned_public_releases", state)
