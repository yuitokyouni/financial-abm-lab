"""Market orchestrator: warmup -> announcement -> execution -> s1/s2/s3 readout.

The Market owns the order book, the agent population and the fundamental value.
Its core loop is a single order event per step (`_base_step`), which is what
closes the loop: every FCN order reacts to the mid the previous orders produced.

``run_event`` runs the whole treatment (warmup + announce + drift + execution)
for one seed and returns the shortfall decomposition, matching the empirical
definitions in unwind-tape/MEASUREMENT_SPEC.md:

    s1 = ln(P_ref)      - ln(P_day0end)     announcement impact
    s2 = ln(P_day0end)  - ln(P_exec_ref)    drift / front-running
    s3 = ln(P_exec_ref) - ln(P_exec)        execution gap (seller VWAP)
    IS = s1 + s2 + s3 = ln(P_ref) - ln(P_exec)   (positive = cost to the seller)
"""

from __future__ import annotations

import math

import numpy as np

from .agents import build_population
from .order_book import OrderBook

SEED_AGENT_ID = -1      # phantom market maker that seeds initial liquidity
BUYBACK_AGENT_ID = -2   # company buyback bid support during execution
INFORMED_AGENT_ID = -3  # informed announcement flow that reprices to the news (s1)


class Market:
    """Single-symbol continuous double auction with ZI + FCN agents."""

    def __init__(self, config):
        self.config = config
        self.book: OrderBook | None = None
        self.agents: list = []
        self.rng = None
        self.log_v: float = 0.0
        self.V: float | None = None          # mean per-step warmup volume
        self.last_price: float = config.initial_price
        self._mid_hist: list[float] = []
        self._ret_hist: list[float] = []
        self.announce_active: bool = False
        self.phase: str = "none"           # 'announce' | 'drift' | 'exec' | 'none'

    # ---- live state read by agents ---------------------------------------
    @property
    def mid(self) -> float:
        """Current mid; falls back to the last traded price if a side is empty."""
        m = self.book.mid
        return m if m is not None else self.last_price

    def return_ma(self, window: int) -> float:
        """Moving average of the most recent ``window`` per-step log returns."""
        if not self._ret_hist:
            return 0.0
        w = self._ret_hist[-window:]
        return sum(w) / len(w)

    # ---- setup ------------------------------------------------------------
    def _reset(self, seed):
        cfg = self.config
        self.rng = np.random.default_rng(seed)
        self.book = OrderBook(cfg.tick_size)
        self.log_v = math.log(cfg.fundamental_v)
        self.last_price = cfg.initial_price
        self._mid_hist = []
        self._ret_hist = []
        self.announce_active = False
        self.phase = "none"
        self._seed_book()
        self.agents = build_population(cfg, self.rng)
        self._record_mid()

    def _seed_book(self):
        """Seed a symmetric ladder around the initial price for early liquidity."""
        cfg = self.config
        t0 = self.book.to_tick(cfg.initial_price)
        for i in range(1, cfg.seed_depth + 1):
            self.book._rest("buy", t0 - i, cfg.seed_qty, SEED_AGENT_ID)
            self.book._rest("sell", t0 + i, cfg.seed_qty, SEED_AGENT_ID)

    # ---- one order event --------------------------------------------------
    def _record_mid(self):
        m = self.book.mid
        if m is not None:
            self.last_price = m
        price = self.last_price
        if self._mid_hist:
            self._ret_hist.append(math.log(price / self._mid_hist[-1]))
        self._mid_hist.append(price)

    def _apply(self, agent_id, act):
        b = self.book
        if act.kind == "limit":
            b.add_limit(act.side, act.price, act.qty, agent_id)
        elif act.kind == "market":
            b.market_order(act.side, act.qty)
        elif act.kind == "cancel":
            b.cancel(agent_id)
        # 'none' -> do nothing

    def _base_step(self):
        """Pick one random agent, let it read the market, apply its order."""
        i = int(self.rng.integers(0, len(self.agents)))
        agent = self.agents[i]
        act = agent.decide(self, self.rng)
        self._apply(agent.agent_id, act)
        self._record_mid()

    def warmup(self):
        """Run to steady state and define V = mean traded volume per step."""
        cfg = self.config
        vol0 = self.book.total_volume
        for _ in range(cfg.warmup_steps):
            self._base_step()
        traded = self.book.total_volume - vol0
        self.V = max(traded / cfg.warmup_steps, 1e-9)
        return self.V

    # ---- treatment --------------------------------------------------------
    def run_event(self, Qover_V, W, announce_info, buyback_ratio, mkt_drift, seed):
        """Run one full treatment for one seed; return the metrics dict.

        Steps: reset -> warmup (defines V) -> announce (s1) -> drift (s2) ->
        execute Q over W slices while a buyback absorbs ``buyback_ratio*Q`` and
        the market drift ``mkt_drift`` is applied to the fundamental. The seller
        sells with market orders (walk the book); P_exec is its fill VWAP.
        """
        cfg = self.config
        self._reset(seed)
        self.warmup()
        # V is the *window* volume: mean per-step volume over one execution
        # window (W * exec_inter_steps steps). Q/V is then the participation
        # rate (multiples of a window's worth of average volume), which is what
        # gives a size-dependent impact.  TODO(calibration): tie to real ADV.
        exec_window_steps = W * cfg.exec_inter_steps
        V = self.V * exec_window_steps
        Q = Qover_V * V

        self.announce_active = announce_info

        total_event_steps = (
            cfg.announce_day_steps + cfg.drift_steps + W * cfg.exec_inter_steps
        )
        self._event_step = 0
        event_rets: list[float] = []

        def stepper(n, log_v0, pre=None):
            # ``pre(i)`` (optional) runs before each base step; used by the
            # informed announcement flow to post its descending sell wall.
            for i in range(n):
                if pre is not None:
                    pre(i)
                self._base_step()
                self._event_step += 1
                if mkt_drift != 0.0:
                    prog = self._event_step / max(total_event_steps, 1)
                    self.log_v = log_v0 + mkt_drift * prog
                event_rets.append(self._ret_hist[-1] if self._ret_hist else 0.0)

        # --- P_ref: mid just before the announcement -----------------------
        P_ref = self.mid

        # --- announcement "day 0": PERMANENT fundamental drop -> s1 --------
        # The news that a sale is coming permanently lowers the fundamental v;
        # every FCN reprices down toward it, and the level persists (unlike a
        # transient shock). This discrete day-0 impact is s1.
        self.phase = "announce"
        if announce_info:
            self.log_v -= cfg.announce_fundamental_drop
        log_v0 = self.log_v          # mkt_drift baseline (post-announcement)
        if (announce_info and getattr(cfg, "announce_impact_flow", False)
                and cfg.announce_fundamental_drop != 0.0):
            # Informed repricing (calibration channel): the passive book cannot
            # reprice the fundamental step within the window, so an informed
            # trader walks the mid down to the announced level via a descending
            # marketable sell wall. It cancels + re-posts one wall per step at
            # the current waypoint wp = P_ref * exp(-drop * frac); the marketable
            # part eats all bids above wp and the remainder rests at wp as the
            # new best ask, so the mid tracks the waypoint. By the end of the
            # window the mid sits at P_ref*exp(-drop) -> s1 ~ drop.
            n_ann = max(cfg.announce_day_steps, 1)
            drop = cfg.announce_fundamental_drop

            def _reprice(i):
                frac = (i + 1) / n_ann
                wp = P_ref * math.exp(-drop * frac)
                self.book.cancel(INFORMED_AGENT_ID)
                totbid = sum(sum(o[2] for o in dq) for dq in self.book.bids.values())
                if totbid > 0:
                    self.book.add_limit("sell", wp, totbid + 50, INFORMED_AGENT_ID)

            stepper(cfg.announce_day_steps, log_v0, pre=_reprice)
        else:
            stepper(cfg.announce_day_steps, log_v0)
        P_day0end = self.mid

        # --- drift window: front-running flow -> s2 ------------------------
        # Front-runners who know the block is coming sell ahead of it. We model
        # this as a scheduled sell of frontrun_fraction*Q spread over the drift
        # window (ramping up toward execution), active only when the sale was
        # announced. It pushes price below the new fundamental -> positive s2.
        self.phase = "drift"
        drift_n = max(cfg.drift_steps, 1)
        Q_fr = cfg.frontrun_fraction * Q if announce_info else 0.0
        # triangular ramp weights so more selling happens closer to execution
        w_sum = 0.5 * drift_n * (drift_n + 1)
        carry_fr = 0.0
        for k in range(cfg.drift_steps):
            if Q_fr > 0:
                carry_fr += Q_fr * (k + 1) / w_sum
                fr_qty = int(carry_fr)
                carry_fr -= fr_qty
                if fr_qty > 0:
                    self.book.market_order("sell", fr_qty)
            stepper(1, log_v0)
        P_exec_ref = self.mid

        # --- execution window: seller sells Q over W slices (-> s3) --------
        self.phase = "exec"
        seller_filled = 0
        seller_notional = 0.0
        q_slice = Q / W
        qb_slice = buyback_ratio * Q / W
        carry_s = 0.0
        carry_b = 0.0
        for _ in range(W):
            # Buyback posts aggressive bid support at the mid *before* the seller
            # sells, so the seller's flow is absorbed directly at a supported
            # price (a buyback provides a bid). Any unfilled part rests as a
            # standing wall of support.
            carry_b += qb_slice
            b_qty = int(carry_b)
            carry_b -= b_qty
            if b_qty > 0:
                self.book.add_limit("buy", self.mid, b_qty, BUYBACK_AGENT_ID)
            # Seller sells its slice with a market order (walk the book).
            carry_s += q_slice
            s_qty = int(carry_s)
            carry_s -= s_qty
            if s_qty > 0:
                _f, _v, fills = self.book.market_order("sell", s_qty)
                for fl in fills:
                    seller_filled += fl.qty
                    seller_notional += fl.qty * fl.price
            self._record_mid()
            stepper(cfg.exec_inter_steps, log_v0)

        P_exec = seller_notional / seller_filled if seller_filled > 0 else P_exec_ref

        s1 = math.log(P_ref) - math.log(P_day0end)
        s2 = math.log(P_day0end) - math.log(P_exec_ref)
        s3 = math.log(P_exec_ref) - math.log(P_exec)
        IS = s1 + s2 + s3
        sigma = float(np.std(event_rets)) if event_rets else 0.0

        return {
            "seed": seed,
            "Qover_V": Qover_V,
            "W": W,
            "announce_info": announce_info,
            "buyback_ratio": buyback_ratio,
            "mkt_drift": mkt_drift,
            "V": V,
            "Q": Q,
            "P_ref": P_ref,
            "P_day0end": P_day0end,
            "P_exec_ref": P_exec_ref,
            "P_exec": P_exec,
            "seller_filled": seller_filled,
            "s1": s1,
            "s2": s2,
            "s3": s3,
            "IS": IS,
            "sigma": sigma,
        }
