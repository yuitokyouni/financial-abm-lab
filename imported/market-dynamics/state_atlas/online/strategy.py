"""Strategy modules — target weights from (state, atlas).

Two modes, both monotone in F (no prediction, only reaction):

A. ``risk_overlay`` (responsible default):
   target = base × g(F).  CALM = full base, ELEVATED ramps to 0.5, STRESS
   ramps to 0; persistent_stress forces flat. Predict-nothing de-risker.

B. ``vol_carry_meanrev`` (demo-only, paper-only):
   CALM/ELEVATED+contango ⇒ SVXY long (harvest the negative roll yield).
   STRESS                 ⇒ VXX long (small hedge) or cash.
   persistent_stress      ⇒ kill-switch FLAT cash (so we sit out GFC/COVID-
                           type sustained excursions instead of being grinded).
"""

from __future__ import annotations

from dataclasses import dataclass

from state_atlas.online.monitor import TrainedAtlas
from state_atlas.online.state_machine import State


@dataclass(frozen=True)
class StrategyConfig:
    base_weight: float = 1.0
    elevated_scale: float = 0.5
    stress_floor: float = 0.0
    # vol_carry mode: how much VXX to hold during STRESS (negative = short, 0 = cash)
    stress_vxx_weight: float = 0.0
    # Whether to also flatten in ELEVATED (more conservative)
    flatten_in_elevated: bool = False


_DEFAULT_STRATEGY_CFG = StrategyConfig()


def _g_of_F(F: float, atlas: TrainedAtlas, cfg: StrategyConfig) -> float:
    """Monotonically decreasing scale in F, in [0, 1]."""
    if F < atlas.F_p50:
        return 1.0
    if F < atlas.F_p90:
        # 1.0 → cfg.elevated_scale linearly
        t = (F - atlas.F_p50) / max(atlas.F_p90 - atlas.F_p50, 1e-9)
        return 1.0 + t * (cfg.elevated_scale - 1.0)
    # F ≥ p90: cfg.elevated_scale → cfg.stress_floor linearly until p99, then floor.
    t = (F - atlas.F_p90) / max(atlas.F_p99 - atlas.F_p90, 1e-9)
    t = min(max(t, 0.0), 1.0)
    return cfg.elevated_scale + t * (cfg.stress_floor - cfg.elevated_scale)


def target_weights_risk_overlay(
    state: State, atlas: TrainedAtlas, cfg: StrategyConfig = _DEFAULT_STRATEGY_CFG
) -> dict[str, float]:
    """Smooth g(F) scaling of a single base asset weight."""
    if state.persistent_stress:
        scale = 0.0
    else:
        scale = _g_of_F(state.F, atlas, cfg)
    base = cfg.base_weight * scale
    return {"base_asset": base, "cash": cfg.base_weight - base}


def target_weights_vol_carry(
    state: State, atlas: TrainedAtlas, cfg: StrategyConfig = _DEFAULT_STRATEGY_CFG
) -> dict[str, float]:
    """SVXY long in contango+calm, VXX/cash in stress, FLAT in persistent stress."""
    if state.persistent_stress:
        return {"SVXY": 0.0, "VXX": 0.0, "cash": cfg.base_weight}
    if state.label == "STRESS":
        vxx = cfg.stress_vxx_weight * cfg.base_weight
        return {"SVXY": 0.0, "VXX": vxx, "cash": cfg.base_weight - vxx}
    if state.label == "ELEVATED":
        if cfg.flatten_in_elevated:
            return {"SVXY": 0.0, "VXX": 0.0, "cash": cfg.base_weight}
        svxy = cfg.elevated_scale * cfg.base_weight
        return {"SVXY": svxy, "VXX": 0.0, "cash": cfg.base_weight - svxy}
    # CALM
    return {"SVXY": cfg.base_weight, "VXX": 0.0, "cash": 0.0}
