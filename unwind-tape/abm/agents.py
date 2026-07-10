"""Trading agents: ZI (zero-intelligence) and FCN (fundamentalist/chartist/noise).

Each agent exposes ``decide(market, rng) -> Action``. The market picks one agent
per step (1 step = 1 order event) and applies its Action to the book. Agents
read the *live* market state (current mid + recent returns), which is what makes
the loop closed: FCN never sees an exogenous fixed price.
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

    Supplies baseline liquidity and noise. Posts a limit at ``mid +/- U(1..k)``
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


class FCNAgent:
    """Fundamentalist + Chartist + Noise agent (closed-loop expectation).

    Each step it reads the live mid ``p`` and the moving average of recent
    returns, forms an expected return::

        r = g1*(log v - log p) + g2*MA(recent returns) + g3*eps

    and a target ``p_target = p * exp(r * tau)``. It then posts a limit toward
    the target (clamped to a band around the mid), buying if ``p_target > p``
    else selling. ``g1/g2/g3`` and ``tau`` are drawn per agent at construction.

    Sign check: g1>0 makes it buy when price is below fundamental (absorbing);
    g2>0 makes it sell into down-momentum (amplifying).
    """

    is_fcn = True

    def __init__(self, agent_id, cfg, rng):
        self.agent_id = agent_id
        # per-agent coefficient draws (kept non-negative so signs are unambiguous)
        self.g1 = abs(rng.normal(cfg.fcn_g1_mean, cfg.fcn_g1_std))
        self.g2 = abs(rng.normal(cfg.fcn_g2_mean, cfg.fcn_g2_std))
        self.g3 = abs(rng.normal(cfg.fcn_g3_mean, cfg.fcn_g3_std))
        self.tau = int(rng.integers(cfg.fcn_tau_min, cfg.fcn_tau_max + 1))

    def decide(self, market, rng) -> Action:
        cfg = market.config
        if rng.random() < cfg.fcn_cancel_prob:
            return Action("cancel")
        p = market.mid
        log_p = math.log(p)
        ma = market.return_ma(cfg.fcn_ma_window)
        eps = rng.normal(0.0, cfg.fcn_noise_sigma)
        # Note the announcement channels handled outside this expression:
        #   - s1: a PERMANENT drop in the fundamental v at t=0 (the news that the
        #     stock is worth less). Every FCN reprices toward the new v via the
        #     g1 term above -- no extra code needed here.
        #   - s2: front-running, modelled as a scheduled sell flow during the
        #     drift window (see market.run_event), not decided here.
        r = self.g1 * (market.log_v - log_p) + self.g2 * ma + self.g3 * eps
        p_target = p * math.exp(r * self.tau)
        side = "buy" if p_target > p else "sell"
        # clamp target to a band around the mid so single orders stay bounded
        lo, hi = p * (1 - cfg.fcn_price_band), p * (1 + cfg.fcn_price_band)
        px = min(max(p_target, lo), hi)
        # Passive quoting (default): rest on our own side of the mid rather than
        # lifting/hitting the touch. This makes restoration *gradual* (it happens
        # via net order flow, not an instant re-quote), which is what lets a
        # larger block leave a larger, size-dependent execution discount instead
        # of every slice snapping back to the same price. A small aggression
        # allowance lets strong signals cross the spread for price discovery.
        if cfg.fcn_passive:
            tick = market.book.tick_size
            # spread quotes over a range of depths so support/resistance is a
            # graded ladder, not a spike at the touch -> larger blocks walk
            # proportionally deeper (extends the size effect's dynamic range).
            depth = int(rng.integers(0, cfg.fcn_passive_spread_ticks + 1))
            if side == "buy":
                edge = market.mid + cfg.fcn_aggression_ticks * tick - depth * tick
                px = min(px, edge)
            else:
                edge = market.mid - cfg.fcn_aggression_ticks * tick + depth * tick
                px = max(px, edge)
        qty = int(rng.integers(cfg.fcn_min_qty, cfg.fcn_max_qty + 1))
        return Action("limit", side=side, price=px, qty=qty)


def build_population(cfg, rng):
    """Build the agent list: first ``zi_fraction`` are ZI, the rest FCN."""
    n_zi = int(round(cfg.n_agents * cfg.zi_fraction))
    agents = []
    for i in range(cfg.n_agents):
        if i < n_zi:
            agents.append(ZIAgent(i, cfg, rng))
        else:
            agents.append(FCNAgent(i, cfg, rng))
    return agents
