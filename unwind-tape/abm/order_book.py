"""Continuous double-auction limit order book (LOB) with price-time priority.

Prices are stored internally as integer tick indices to avoid float drift; the
public API accepts/returns real prices. The book supports resting limit orders,
marketable (crossing) limit orders, market orders that *walk the book*, best
quotes, and cancel-by-agent.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass
class Fill:
    """A single execution: aggressor lifts/hits one resting order."""

    price: float
    qty: int
    resting_agent_id: int


class OrderBook:
    """Price-level LOB. One symbol, continuous double auction."""

    def __init__(self, tick_size: float):
        assert tick_size > 0
        self.tick_size = tick_size
        # tick -> deque of resting orders, each order = [order_id, agent_id, qty]
        self.bids: dict[int, deque] = {}
        self.asks: dict[int, deque] = {}
        self._loc: dict[int, tuple] = {}       # order_id -> (side, tick)
        self._by_agent: dict[int, set] = {}    # agent_id -> {order_id, ...}
        self._next_id = 0
        self.total_volume = 0                  # cumulative filled qty

    # ---- tick helpers -----------------------------------------------------
    def to_tick(self, price: float) -> int:
        """Snap a real price to the nearest integer tick index."""
        return int(round(price / self.tick_size))

    def to_price(self, tick: float) -> float:
        """Convert a tick index back to a real price."""
        return tick * self.tick_size

    # ---- best quotes ------------------------------------------------------
    @property
    def best_bid_tick(self):
        return max(self.bids) if self.bids else None

    @property
    def best_ask_tick(self):
        return min(self.asks) if self.asks else None

    @property
    def best_bid(self):
        t = self.best_bid_tick
        return self.to_price(t) if t is not None else None

    @property
    def best_ask(self):
        t = self.best_ask_tick
        return self.to_price(t) if t is not None else None

    @property
    def mid(self):
        """Mid price, or None if either side is empty."""
        b, a = self.best_bid_tick, self.best_ask_tick
        if b is None or a is None:
            return None
        return 0.5 * (self.to_price(b) + self.to_price(a))

    # ---- internal bookkeeping --------------------------------------------
    def _register(self, order_id, side, tick, agent_id):
        self._loc[order_id] = (side, tick)
        self._by_agent.setdefault(agent_id, set()).add(order_id)

    def _unregister(self, order_id, agent_id):
        self._loc.pop(order_id, None)
        s = self._by_agent.get(agent_id)
        if s is not None:
            s.discard(order_id)

    def _rest(self, side, tick, qty, agent_id):
        """Insert a resting order at a price level (FIFO within the level)."""
        oid = self._next_id
        self._next_id += 1
        book = self.bids if side == "buy" else self.asks
        book.setdefault(tick, deque()).append([oid, agent_id, qty])
        self._register(oid, side, tick, agent_id)
        return oid

    # ---- matching ---------------------------------------------------------
    def _match(self, side, qty, limit_tick):
        """Aggress ``qty`` from ``side`` against the opposite book.

        ``limit_tick`` bounds how far the aggressor will trade (None = market
        order, no bound). Returns ``(filled, vwap, fills, remaining)``.
        """
        book = self.asks if side == "buy" else self.bids
        fills: list[Fill] = []
        filled = 0
        notional = 0.0

        def acceptable(t):
            if limit_tick is None:
                return True
            return t <= limit_tick if side == "buy" else t >= limit_tick

        while qty > 0 and book:
            best_t = min(book) if side == "buy" else max(book)
            if not acceptable(best_t):
                break
            level = book[best_t]
            price = self.to_price(best_t)
            while qty > 0 and level:
                order = level[0]  # [oid, agent_id, oqty]
                take = min(qty, order[2])
                order[2] -= take
                qty -= take
                filled += take
                notional += take * price
                fills.append(Fill(price, take, order[1]))
                if order[2] == 0:
                    level.popleft()
                    self._unregister(order[0], order[1])
            if not level:
                del book[best_t]

        self.total_volume += filled
        vwap = (notional / filled) if filled > 0 else math.nan
        return filled, vwap, fills, qty

    # ---- public order entry ----------------------------------------------
    def add_limit(self, side, price, qty, agent_id):
        """Submit a limit order.

        If the price crosses the opposite best quote, the marketable part is
        executed (walking the book up to ``price``) and any remainder rests.
        Returns ``(filled, vwap, fills, resting_order_id or None)``.
        """
        assert side in ("buy", "sell") and qty > 0
        tick = self.to_tick(price)
        filled, vwap, fills, remaining = self._match(side, qty, limit_tick=tick)
        oid = None
        if remaining > 0:
            oid = self._rest(side, tick, remaining, agent_id)
        return filled, vwap, fills, oid

    def market_order(self, side, qty):
        """Marketable order with no price bound (walk the book).

        Returns ``(filled, vwap, fills)``.
        """
        assert side in ("buy", "sell") and qty > 0
        filled, vwap, fills, _ = self._match(side, qty, limit_tick=None)
        return filled, vwap, fills

    def cancel(self, agent_id):
        """Cancel all resting orders of ``agent_id``. Returns count cancelled."""
        oids = list(self._by_agent.get(agent_id, ()))
        n = 0
        for oid in oids:
            loc = self._loc.get(oid)
            if loc is None:
                continue
            side, tick = loc
            book = self.bids if side == "buy" else self.asks
            level = book.get(tick)
            if level is not None:
                remaining = deque(o for o in level if o[0] != oid)
                if len(remaining) != len(level):
                    n += 1
                if remaining:
                    book[tick] = remaining
                else:
                    del book[tick]
            self._unregister(oid, agent_id)
        return n
