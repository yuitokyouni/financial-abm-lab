"""Baseline parameters for the ABM skeleton.

All numbers here are PROVISIONAL placeholders chosen so the closed loop runs and
produces sane, monotone behaviour. They are NOT calibrated to the unwind-tape
empirical moments yet. Everything marked ``TODO(calibration)`` must later be
fitted to real data (see abm/README.md and unwind-tape/MEASUREMENT_SPEC.md):

  - s3 (execution discount) target ~ -3% on real offerings,
  - s2 dispersion in the no-buyback group,
  - realistic FCN g1/g2/g3 mix, ZI share, warmup length, window W.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    """Baseline model configuration (a plain dataclass, easy to override)."""

    # ---- market / price grid ---------------------------------------------
    initial_price: float = 100.0          # reference price level
    fundamental_v: float = 100.0          # constant fundamental v (log v = ln 100)
    tick_size: float = 0.05               # minimum price increment
    seed_depth: int = 30                  # ladder levels seeded on each side at t=0
    seed_qty: int = 5                     # resting qty per seeded level

    # ---- population -------------------------------------------------------
    n_agents: int = 1000
    zi_fraction: float = 0.6              # ZI:FCN = 6:4          TODO(calibration)
    warmup_steps: int = 4000              # steps to reach steady state  TODO(calibration)

    # ---- ZI (zero-intelligence) agent ------------------------------------
    zi_offset_ticks: int = 20             # limit posted mid +/- U(1..offset) ticks
    zi_min_qty: int = 1
    zi_max_qty: int = 4
    zi_market_prob: float = 0.12          # prob of taking liquidity (market order)
    zi_cancel_prob: float = 0.05          # prob of cancelling own resting quotes

    # ---- FCN (fundamentalist / chartist / noise) agent -------------------
    # r = g1*(log v - log p) + g2*MA(recent returns) + g3*eps
    #   g1>0 fundamental: price down -> buy (absorbing / stabilising)
    #   g2>0 chartist:    down-momentum -> sell (amplifying)
    fcn_g1_mean: float = 1.0
    fcn_g1_std: float = 0.4
    fcn_g2_mean: float = 0.8
    fcn_g2_std: float = 0.3
    fcn_g3_mean: float = 1.0
    fcn_g3_std: float = 0.5
    fcn_tau_min: int = 5                  # forecast horizon (steps)
    fcn_tau_max: int = 30
    fcn_ma_window: int = 20               # window for MA(recent returns)
    fcn_noise_sigma: float = 0.002        # sd of eps
    fcn_price_band: float = 0.015         # clamp target price to mid*(1 +/- band)
    fcn_passive: bool = True              # rest on own side of mid (gradual reversion)
    fcn_aggression_ticks: int = 1        # how far past mid a passive quote may sit
    fcn_passive_spread_ticks: int = 15   # graded ladder depth for passive quotes
    fcn_min_qty: int = 1
    fcn_max_qty: int = 4
    fcn_cancel_prob: float = 0.03

    # ---- event / announcement --------------------------------------------
    announce_day_steps: int = 300         # "day 0": public reprice to lower v -> s1
    drift_steps: int = 300                # day0end -> exec ref (front-running) -> s2
    exec_inter_steps: int = 4             # normal reaction steps between seller slices
    announce_fundamental_drop: float = 0.006  # permanent v drop on news -> s1  TODO(calibration)
    frontrun_fraction: float = 0.3        # fraction of Q sold ahead by front-runners (drift) -> s2  TODO(calibration)

    # ---- default treatment (overridden by experiments) -------------------
    default_Qover_V: float = 15.0
    default_W: int = 60
    default_buyback_ratio: float = 0.0
    default_mkt_drift: float = 0.0
    default_announce_info: bool = False


def baseline() -> Config:
    """Return a fresh baseline configuration."""
    return Config()
