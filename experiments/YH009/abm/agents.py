"""Trading agents for the LOB market.

Two agent types populate the continuous double auction and form the *market*
that a block trade has to move through:

  * ``ZIAgent``          -- zero-intelligence noise (baseline flow / jitter).
  * ``FCNMarketMaker``   -- fundamentalist/chartist/noise agent recast as a
                            two-sided, inventory-aware **market maker**. It is
                            the liquidity *provider*: every step it (re)quotes a
                            bid and an ask around its own valuation, skews them
                            against its inventory, and only occasionally crosses
                            the spread to *take* liquidity when its signal is
                            strong.

The anticipatory / predatory traders (Brunnermeier--Pedersen 2005) are NOT here:
they are liquidity *takers* driven on a schedule by the event orchestrator
(see ``market.run_event``), because they act relative to the announced block and
the placement date, not once-per-random-step like the background population.

Each agent exposes ``decide(market, rng) -> Action | list[Action]``. The market
picks one agent per step, lets it read the *live* state (mid + recent returns +
its own inventory), and applies its order(s). That live read is what closes the
loop: an FCN maker never sees an exogenous fixed price -- it quotes around the
price the previous orders produced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    """An order intent produced by an agent; the market executes it."""

    kind: str                       # 'limit' | 'market' | 'cancel' | 'none'
    side: Optional[str] = None      # 'buy' | 'sell'
    price: Optional[float] = None   # for limit orders
    qty: Optional[int] = None       # for limit/market orders


class ZIAgent:
    """Zero-intelligence agent: random limit/market orders around the mid.

    Supplies baseline noise and jitter. Posts a limit at ``mid +/- U(1..k)``
    ticks with random size, occasionally takes liquidity via a market order, and
    occasionally cancels its own stale quotes.
    """

    is_fcn = False

    def __init__(self, agent_id, cfg, rng):
        self.agent_id = agent_id

    def decide(self, market, rng) -> Action:
        cfg = market.config
        if rng.random() < cfg.zi_cancel_prob:
            return Action("cancel")
        side = "buy" if rng.random() < 0.5 else "sell"
        qty = int(rng.integers(cfg.zi_min_qty, cfg.zi_max_qty + 1))
        if rng.random() < cfg.zi_market_prob:
            return Action("market", side=side, qty=qty)
        mid = market.mid
        base_tick = market.book.to_tick(mid)
        offset = int(rng.integers(1, cfg.zi_offset_ticks + 1))
        tick = base_tick - offset if side == "buy" else base_tick + offset
        return Action("limit", side=side, price=market.book.to_price(tick), qty=qty)


class FCNMarketMaker:
    """Fundamentalist + Chartist + Noise agent recast as a market maker.

    Each step it reads the live mid ``p``, the MA of recent returns, and its own
    net inventory, then forms a valuation::

        r   = g1*(log v - log p) + g2*MA(recent returns) + g3*eps
        v_i = p * exp(r * tau)                        (clamped to a band)

    and quotes **both sides** around an inventory-skewed reservation price::

        res = v_i - inventory * inv_skew              (long -> quote lower to shed)
        bid = res - half_spread,   ask = res + half_spread

    Signs / roles:
      * g1>0 (fundamentalist): p below v -> res above p -> richer bid -> it
        *absorbs* selling and pulls price back (stabilising / mean reversion).
      * g2>0 (chartist): down-momentum lowers v -> it lowers both quotes ->
        it *withdraws* bid support and chases the trend (amplifying).
      * inventory skew: as it fills the buy side into a falling market it gets
        long, skews quotes down, and eventually stops quoting the bid at all
        (``mm_max_inventory``). That is how liquidity *thins precisely when a
        predator is hitting it* -- the Brunnermeier--Pedersen channel.

    It usually only *provides* liquidity (rests limits). When |r| is large it
    may cross the spread and *take* (a market order) -- the "FCN takes liquidity"
    behaviour -- so the maker is not purely passive.
    """

    is_fcn = True

    def __init__(self, agent_id, cfg, rng):
        self.agent_id = agent_id
        # per-agent coefficient draws (kept non-negative so signs are unambiguous)
        self.g1 = abs(rng.normal(cfg.fcn_g1_mean, cfg.fcn_g1_std))
        self.g2 = abs(rng.normal(cfg.fcn_g2_mean, cfg.fcn_g2_std))
        self.g3 = abs(rng.normal(cfg.fcn_g3_mean, cfg.fcn_g3_std))
        self.tau = int(rng.integers(cfg.fcn_tau_min, cfg.fcn_tau_max + 1))

    def decide(self, market, rng):
        cfg = market.config
        p = market.mid
        log_p = math.log(p)
        ma = market.return_ma(cfg.fcn_ma_window)
        eps = rng.normal(0.0, cfg.fcn_noise_sigma)
        r = self.g1 * (market.log_v - log_p) + self.g2 * ma + self.g3 * eps
        v_i = p * math.exp(r * self.tau)
        # clamp valuation to a band around the mid so a single quote stays bounded
        lo, hi = p * (1 - cfg.fcn_price_band), p * (1 + cfg.fcn_price_band)
        v_i = min(max(v_i, lo), hi)

        tick = market.book.tick_size
        inv = market.inventory.get(self.agent_id, 0.0)
        res = v_i - inv * cfg.mm_inv_skew_ticks * tick        # inventory skew
        half = cfg.mm_half_spread_ticks * tick

        actions = [Action("cancel")]                           # refresh own quotes

        # occasional liquidity TAKE: a strong signal crosses the spread instead
        # of resting (this is the FCN "taking" flow the maker also produces).
        if abs(r) > cfg.mm_take_threshold and rng.random() < cfg.mm_take_prob:
            side = "buy" if r > 0.0 else "sell"
            actions.append(Action("market", side=side, qty=cfg.mm_take_qty))

        # two-sided quotes, each suppressed once inventory hits its soft cap on
        # the side that would grow the position further.
        if inv < cfg.mm_max_inventory:
            actions.append(Action("limit", side="buy",
                                   price=res - half, qty=cfg.mm_quote_qty))
        if inv > -cfg.mm_max_inventory:
            actions.append(Action("limit", side="sell",
                                   price=res + half, qty=cfg.mm_quote_qty))
        return actions


# Backwards-compatible alias: older code / notebooks referred to ``FCNAgent``.
FCNAgent = FCNMarketMaker


class MomentumTaker:
    """Trend-following liquidity TAKER -- the cascade / amplification channel.

    The FCN maker only re-quotes on momentum and brakes on inventory, so it is a
    stabiliser and nothing cascades. This agent is the missing amplifier: it
    CROSSES the spread -- market-BUYS into up-momentum, market-SELLS into
    down-momentum -- with size growing in |momentum|, **no inventory brake and no
    fundamental anchor**. That is the positive feedback a herding cascade needs.

    It is deliberately **symmetric**: in a live up-trend it keeps buying, so
    price *keeps rising* (the "absorbed, trend continues" outcome). A block only
    tips a cascade if its dip FLIPS the momentum sign; whether it does is set by
    the block-vs-trend balance = the state. Same rule, both outcomes, state
    decides -- which is the non-arbitrary bimodality the experiment must show.
    """

    is_fcn = False

    def __init__(self, agent_id, cfg, rng):
        self.agent_id = agent_id

    def decide(self, market, rng):
        cfg = market.config
        mom = market.return_ma(cfg.mt_window) * cfg.mt_window     # cumulative recent return
        if abs(mom) < cfg.mt_threshold:
            return Action("none")
        base = (market.V or 1.0) * cfg.mt_window                  # a window's worth of volume
        qty = int(cfg.mt_k * abs(mom) * base)
        if qty <= 0:
            return Action("none")
        return Action("market", side=("buy" if mom > 0.0 else "sell"), qty=qty)


def build_population(cfg, rng):
    """Agent list: ``zi_fraction`` ZI, then ``mt_fraction`` momentum takers, rest
    FCN makers. mt_fraction=0 -> no takers (calibrated model, unchanged)."""
    n = cfg.n_agents
    n_zi = int(round(n * cfg.zi_fraction))
    n_mt = min(int(round(n * cfg.mt_fraction)), max(n - n_zi, 0))
    agents = []
    for i in range(n):
        if i < n_zi:
            agents.append(ZIAgent(i, cfg, rng))
        elif i < n_zi + n_mt:
            agents.append(MomentumTaker(i, cfg, rng))
        else:
            agents.append(FCNMarketMaker(i, cfg, rng))
    return agents
