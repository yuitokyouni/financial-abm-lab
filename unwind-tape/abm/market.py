"""Market orchestrator: warmup -> announcement -> execution -> s1/s2/s3 readout.

The Market owns the order book, the agent population, the fundamental value and
every agent's running **inventory**. Its core loop is one order event per step
(``_base_step``): a random background agent (ZI or FCN market maker) reads the
live mid and (re)quotes. That is what closes the loop -- every FCN maker reacts
to the price the previous orders produced.

Structure of an announced unwind (Brunnermeier--Pedersen 2005, LOB port):

    warmup            ZI + FCN makers build a book; defines V (per-step volume)
    P_ref             mid just before the news
    announce (s1)     the block (Q = (Q/V)*V) is revealed. Anticipatory
                      *predators* size an aggregate short from a book-walk of the
                      block and dump a front-loaded chunk with MARKET orders ->
                      the announcement gap.  s1 = ln P_ref - ln P_day0end.
    drift    (s2)     predators work the rest of their short over the window
                      (ramped toward the placement); FCN makers absorb, get long
                      and skew down.  s2 = ln P_day0end - ln P_exec_ref.
    exec     (s3)     the placement. For an *announced* offering it is placed off
                      the lit book at the exogenous underwriter haircut
                      (``exec_discount``); the lit footprint was the anticipation
                      above. For the *unannounced counterfactual* (exp1) the block
                      instead walks the lit book slice by slice, so s3 is the
                      emergent, size-dependent execution impact.
                      s3 = ln P_exec_ref - ln P_exec.
    post              predators cover (buy back) -> price recovers. Diagnostic
                      only (rebound vs drift archetype); NOT part of s1/s2/s3.

    IS = s1 + s2 + s3 = ln(P_ref) - ln(P_exec)   (positive = cost to the seller)

The cost is thus *emergent*: nothing here injects a fundamental drop or a scripted
s1. s1 and s2 come out of predators taking liquidity from FCN makers; the
maker g1/g2 balance and how fast predators cover decide whether price has
recovered by the placement (rebound) or is still sliding (drift-down).
"""

from __future__ import annotations

import math

import numpy as np

from .agents import build_population
from .order_book import OrderBook

SEED_AGENT_ID = -1       # phantom maker that seeds a thin starter ladder
BUYBACK_AGENT_ID = -2    # company buyback: standing bid support during the event
PREDATOR_AGENT_ID = -4   # aggregate anticipatory (BP2005) front-runner / coverer
SELLER_AGENT_ID = -5     # unannounced-counterfactual block seller (walks the book)


class Market:
    """Single-symbol continuous double auction with ZI + FCN-maker agents."""

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
        self.inventory: dict[int, float] = {}   # agent_id -> net position
        self.phase: str = "none"           # 'announce'|'drift'|'exec'|'post'|'none'

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
        self.inventory = {}
        self.phase = "none"
        self._seed_book()
        self.agents = build_population(cfg, self.rng)
        self._record_mid()

    def _seed_book(self):
        """Seed a *thin* symmetric starter ladder so warmup has something to
        trade against. The real, replenishing liquidity comes from the FCN
        makers -- the seed is only scaffolding, kept deliberately shallow so a
        block actually moves price (the previous deep seed was the reason the
        market was too liquid to produce realistic volatility)."""
        cfg = self.config
        t0 = self.book.to_tick(cfg.initial_price)
        for i in range(1, cfg.seed_depth + 1):
            self.book._rest("buy", t0 - i, cfg.seed_qty, SEED_AGENT_ID)
            self.book._rest("sell", t0 + i, cfg.seed_qty, SEED_AGENT_ID)

    # ---- inventory bookkeeping -------------------------------------------
    def _settle(self, agent_id, side, fills):
        """Update inventory for an aggressor and each resting counterparty."""
        if not fills:
            return
        sign = 1.0 if side == "buy" else -1.0
        tot = 0
        for fl in fills:
            self.inventory[fl.resting_agent_id] = (
                self.inventory.get(fl.resting_agent_id, 0.0) - sign * fl.qty)
            tot += fl.qty
        self.inventory[agent_id] = self.inventory.get(agent_id, 0.0) + sign * tot

    def _market_order(self, agent_id, side, qty):
        """Aggressive market order attributed to ``agent_id`` (inventory-aware)."""
        q = int(round(qty))
        if q <= 0:
            return 0, float("nan"), []
        filled, vwap, fills = self.book.market_order(side, q)
        self._settle(agent_id, side, fills)
        return filled, vwap, fills

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
            _f, _v, fills, _oid = b.add_limit(act.side, act.price, act.qty, agent_id)
            self._settle(agent_id, act.side, fills)
        elif act.kind == "market":
            self._market_order(agent_id, act.side, act.qty)
        elif act.kind == "cancel":
            b.cancel(agent_id)
        # 'none' -> do nothing

    def _apply_actions(self, agent_id, acts):
        """Apply a single Action or a list of Actions (a maker quotes two sides)."""
        if isinstance(acts, (list, tuple)):
            for a in acts:
                self._apply(agent_id, a)
        else:
            self._apply(agent_id, acts)

    def _evolve_fundamental(self):
        """Optional per-step log-fundamental random walk (regime variant only).

        Guarded by ``fundamental_rw_sigma``: at 0 (the calibrated model) it does
        NOT touch the rng, so the rng stream -- and every calibrated result -- is
        bit-identical. At >0 the anchor drifts, giving real trends and permanent
        block impact. run_event's mkt_drift path overwrites log_v explicitly, so
        this only matters for the free-running regime experiment.
        """
        s = self.config.fundamental_rw_sigma
        if s > 0.0:
            self.log_v += s * self.rng.standard_normal()

    def _base_step(self):
        """Pick one random agent, let it read the market, apply its order(s)."""
        self._evolve_fundamental()
        i = int(self.rng.integers(0, len(self.agents)))
        agent = self.agents[i]
        acts = agent.decide(self, self.rng)
        self._apply_actions(agent.agent_id, acts)
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

    # ---- predators (BP2005 anticipatory front-running) -------------------
    def _predator_target_short(self, Q):
        """Aggregate predator short, sized from an *observable* book-walk.

        Predators estimate the block's price impact by walking ``lambda*Q`` into
        the current bids. If the implied drop clears the activation gate they
        front-run ``predator_block_frac * Q`` in aggregate; otherwise they sit
        out (small blocks barely move price, so front-running is not worth it).
        The gate uses the live book, so a bigger block both clears the gate more
        easily and implies a bigger short -- the size dependence is emergent, not
        a dialled-in number.
        """
        cfg = self.config
        p0 = self.mid
        est = self.book.estimate_sell_impact(cfg.predator_lambda * Q)
        if est is None or p0 <= 0:
            return 0.0
        exp_drop = (p0 - est) / p0
        if exp_drop < cfg.predator_gate_drop:
            return 0.0
        return cfg.predator_block_frac * Q

    # ---- treatment --------------------------------------------------------
    def run_event(self, Qover_V, W, announce_info, buyback_ratio, mkt_drift, seed):
        """Run one full treatment for one seed; return the metrics dict.

        Signature and returned keys are stable (experiments.py / calibrate.py
        depend on s1/s2/s3/IS/sigma/Q/V/seller_filled).
        """
        cfg = self.config
        self._reset(seed)
        self.warmup()

        # V is the *window* volume: mean per-step volume over one execution
        # window (W * exec_inter_steps steps). Q/V is then the participation rate
        # (multiples of a window's worth of average volume). TODO(calibration D):
        # tie V to real ADV so Q/V is the empirical sold-shares / ADV.
        exec_window_steps = W * cfg.exec_inter_steps
        V = self.V * exec_window_steps
        Q = Qover_V * V

        total_event_steps = (cfg.announce_day_steps + cfg.drift_steps
                             + exec_window_steps + cfg.post_steps)
        self._event_step = 0
        event_rets: list[float] = []

        def stepper(n, log_v0):
            for _ in range(n):
                self._base_step()
                self._event_step += 1
                if mkt_drift != 0.0:
                    prog = self._event_step / max(total_event_steps, 1)
                    self.log_v = log_v0 + mkt_drift * prog
                event_rets.append(self._ret_hist[-1] if self._ret_hist else 0.0)

        P_ref = self.mid
        log_v0 = self.log_v

        # Buyback: a standing bid support wall the company posts once the sale is
        # public (a buyback *provides a bid*). All subsequent selling -- predator
        # front-running here, or the block walk in the unannounced arm -- has to
        # exhaust this support first, so a larger buyback leaves a smaller drop.
        if buyback_ratio > 0.0:
            qb = buyback_ratio * Q
            support_px = P_ref - cfg.tick_size
            self.book.add_limit("buy", support_px, int(round(qb)), BUYBACK_AGENT_ID)

        # ===== announcement "day 0": predators sell into the news -> s1 ======
        # The announcement gap must *persist*: the FCN makers mean-revert hard,
        # so a one-shot dump is fully bought back within the window. Instead the
        # predators sell their announce tranche CONTINUOUSLY (uniformly) across
        # the window, holding price at a depressed plateau -> P_day0end sits
        # below P_ref and s1 > 0. The announce tranche is the larger one, so s1
        # is the dominant emergent cost (empirically s1 >> s2).
        self.phase = "announce"
        S = self._predator_target_short(Q) if announce_info else 0.0
        S_ann = cfg.predator_announce_frac * S
        S_dr = S - S_ann
        ann_n = max(cfg.announce_day_steps, 1)
        carry = 0.0
        for _ in range(cfg.announce_day_steps):
            if S_ann > 0.0:
                carry += S_ann / ann_n
                q = int(carry)
                carry -= q
                if q > 0:
                    self._market_order(PREDATOR_AGENT_ID, "sell", q)
            stepper(1, log_v0)
        P_day0end = self.mid

        # ===== drift window: predators work the rest of the short -> s2 ======
        # Ramped toward the placement. Whether price keeps sliding (drift-down)
        # or the makers claw it back (rebound) is set by the g1/g2 balance and
        # the ramp -- that is where the s2 archetype dispersion comes from.
        self.phase = "drift"
        drift_n = max(cfg.drift_steps, 1)
        w_sum = 0.5 * drift_n * (drift_n + 1)     # triangular ramp toward exec
        carry = 0.0
        for k in range(cfg.drift_steps):
            if S_dr > 0.0:
                carry += S_dr * (k + 1) / w_sum
                q = int(carry)
                carry -= q
                if q > 0:
                    self._market_order(PREDATOR_AGENT_ID, "sell", q)
            stepper(1, log_v0)
        P_exec_ref = self.mid

        # ===== execution window: the placement -> s3 =========================
        self.phase = "exec"
        if announce_info:
            # Announced offering: placed OFF the lit book at the exogenous
            # underwriter/placement haircut (empirical median ~ -3.1%, size
            # independent -- see config NOTE). The lit-market cost was the
            # anticipation (s1+s2); the placement itself does not walk our book.
            P_exec = P_exec_ref * math.exp(-cfg.exec_discount)
            seller_filled = int(round(Q))
        else:
            # Unannounced counterfactual (exp1): dump the block on the lit tape
            # over W slices (walk the book) -> emergent, size-dependent s3. This
            # isolates the *pure execution* size effect (the delta / sqrt-law
            # sweep), with no predators and no announcement.
            seller_filled = 0
            seller_notional = 0.0
            q_slice = Q / W
            carry_s = 0.0
            for _ in range(W):
                carry_s += q_slice
                s_qty = int(carry_s)
                carry_s -= s_qty
                if s_qty > 0:
                    _f, _v, fills = self._market_order(SELLER_AGENT_ID, "sell", s_qty)
                    for fl in fills:
                        seller_filled += fl.qty
                        seller_notional += fl.qty * fl.price
                self._record_mid()
                stepper(cfg.exec_inter_steps, log_v0)
            P_exec = seller_notional / seller_filled if seller_filled > 0 else P_exec_ref

        # sigma is the realised per-step vol over announce+drift+exec (the event
        # window the empirical sigma is measured on) -- BEFORE the post recovery.
        sigma = float(np.std(event_rets)) if event_rets else 0.0

        # ===== post window: predators cover -> recovery (diagnostic) =========
        self.phase = "post"
        if announce_info and S > 0.0 and cfg.post_steps > 0:
            cover_total = cfg.predator_cover_frac * S
            cn = max(cfg.post_steps, 1)
            carry_c = 0.0
            for _ in range(cfg.post_steps):
                carry_c += cover_total / cn
                c = int(carry_c)
                carry_c -= c
                if c > 0:
                    self._market_order(PREDATOR_AGENT_ID, "buy", c)
                stepper(1, log_v0)
        P_post = self.mid

        s1 = math.log(P_ref) - math.log(P_day0end)
        s2 = math.log(P_day0end) - math.log(P_exec_ref)
        s3 = math.log(P_exec_ref) - math.log(P_exec)
        IS = s1 + s2 + s3

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
            "P_post": P_post,               # NEW: post-cover mid (rebound diag.)
            "predator_short": S,            # NEW: aggregate front-run size
            "seller_filled": seller_filled,
            "s1": s1,
            "s2": s2,
            "s3": s3,
            "IS": IS,
            "sigma": sigma,
        }
