"""Phase 8 — online causal F monitor + state machine + strategy + backtest.

This package is the operational side of state_atlas: given a frozen F
topography fit on past data, classify the current bar into CALM/ELEVATED/STRESS
and (optionally) map the state to a paper-trade target position. The whole
pipeline is causal — every value visible at time t depends only on data
≤ t. See DECISIONS.md "Phase 8" entry for the design rationale.
"""

from state_atlas.online.monitor import TrainedAtlas, fit_train_window, project_new
from state_atlas.online.state_machine import (
    State,
    StateConfig,
    StateLabel,
    classify,
)
from state_atlas.online.strategy import (
    StrategyConfig,
    target_weights_risk_overlay,
    target_weights_vol_carry,
)

__all__ = [
    "State",
    "StateConfig",
    "StateLabel",
    "StrategyConfig",
    "TrainedAtlas",
    "classify",
    "fit_train_window",
    "project_new",
    "target_weights_risk_overlay",
    "target_weights_vol_carry",
]
