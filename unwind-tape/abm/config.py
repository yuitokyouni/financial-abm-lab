"""Baseline parameters for the LOB ABM (research YH009).

All numbers here are PROVISIONAL placeholders chosen so the closed loop runs and
produces sane, monotone behaviour. They are NOT yet calibrated to the unwind-tape
empirical moments. Everything marked ``TODO(calibration)`` must later be fitted
to real data (see abm/README.md and unwind-tape/MEASUREMENT_SPEC.md).

Model structure (Brunnermeier--Pedersen 2005 ported to the LOB):
  * FCN agents are two-sided **market makers** (liquidity providers).
  * Anticipatory **predators** take liquidity (market orders) to front-run the
    announced block; s1/s2 emerge from that, they are not injected.
  * s3 (execution discount) is EXOGENOUS for an announced placement
    (``exec_discount``) and emergent (book-walk) for the unannounced exp1
    counterfactual. It is NOT an ABM calibration target.
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
    # THIN starter ladder: only scaffolding for warmup. The replenishing
    # liquidity is the FCN makers; a shallow seed is what lets a block move price
    # (the old deep seed made the market too liquid to show realistic vol).
    seed_depth: int = 6                   # ladder levels seeded on each side at t=0
    seed_qty: int = 2                     # resting qty per seeded level

    # ---- population -------------------------------------------------------
    n_agents: int = 1000
    zi_fraction: float = 0.5              # ZI:FCN-maker = 5:5     TODO(calibration)
    warmup_steps: int = 4000              # steps to reach steady state  TODO(calibration)

    # ---- ZI (zero-intelligence) agent ------------------------------------
    zi_offset_ticks: int = 20             # limit posted mid +/- U(1..offset) ticks
    zi_min_qty: int = 1
    zi_max_qty: int = 4
    zi_market_prob: float = 0.12          # prob of taking liquidity (market order)
    zi_cancel_prob: float = 0.05          # prob of cancelling own resting quotes

    # ---- FCN market maker (fundamentalist / chartist / noise) ------------
    # r = g1*(log v - log p) + g2*MA(recent returns) + g3*eps ; v_i = p*exp(r*tau)
    #   g1>0 fundamental: price down -> quote up -> absorbs / stabilises
    #   g2>0 chartist:    down-momentum -> quote down -> withdraws / amplifies
    # g1 is deliberately weaker than the old skeleton: a strong fundamentalist
    # pin held price at fundamental and made the market too liquid to move (s1
    # and sigma both saturated). A weaker anchor lets sustained predator selling
    # push a *persistent* gap, while g2 (trend) lets it run / overshoot.
    fcn_g1_mean: float = 0.4
    fcn_g1_std: float = 0.16
    fcn_g2_mean: float = 0.8
    fcn_g2_std: float = 0.3
    fcn_g3_mean: float = 1.0
    fcn_g3_std: float = 0.5
    fcn_tau_min: int = 5                  # forecast horizon (steps)
    fcn_tau_max: int = 30
    fcn_ma_window: int = 20               # window for MA(recent returns)
    fcn_noise_sigma: float = 0.002        # sd of eps
    fcn_price_band: float = 0.04          # clamp valuation to mid*(1 +/- band):
    #                                       how far a maker will let price roam
    #                                       from fundamental before defending it.
    #                                       Wider band -> bigger s1 and sigma.  -> sigma knob

    # maker quoting
    mm_half_spread_ticks: int = 2         # half-spread of the two-sided quotes
    mm_quote_qty: int = 3                 # qty posted per side
    mm_inv_skew_ticks: float = 0.12       # quote skew (ticks) per unit net inventory
    mm_max_inventory: int = 80            # soft cap: stop quoting the growing side
    mm_take_prob: float = 0.04            # prob of crossing to take on a strong signal
    mm_take_threshold: float = 0.006      # |r| above which the maker may take
    mm_take_qty: int = 2

    # ---- predators (Brunnermeier--Pedersen 2005, LOB port) ---------------
    # Aggregate anticipatory front-runner. Active only when the sale is announced.
    predator_lambda: float = 0.5          # fraction of block assumed to hit the lit book (impact est)
    predator_gate_drop: float = 0.002     # min book-walk drop to activate front-running
    predator_block_frac: float = 1.5      # aggregate short as a fraction of the block  -> s2 knob
    predator_announce_frac: float = 0.7   # fraction of the short sold in the announce window -> s1 knob
    predator_cover_frac: float = 0.6      # fraction covered in the post window (rebound diag.)

    # ---- event windows ----------------------------------------------------
    announce_day_steps: int = 300         # "day 0" reaction window (-> s1)
    drift_steps: int = 300                # day0end -> exec ref (front-running) (-> s2)
    exec_inter_steps: int = 4             # base steps between execution slices
    post_steps: int = 300                 # post-placement covering window (recovery diag.)
    exec_discount: float = 0.031          # EXOGENOUS placement haircut (announced) -> s3

    # ---- default treatment (overridden by experiments) -------------------
    default_Qover_V: float = 15.0
    default_W: int = 60
    default_buyback_ratio: float = 0.0
    default_mkt_drift: float = 0.0
    default_announce_info: bool = False


def baseline() -> Config:
    """Return a fresh baseline configuration."""
    return Config()
