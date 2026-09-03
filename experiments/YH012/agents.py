"""YH012 World agents (Chiarella–Iori 簡略版)."""

from __future__ import annotations

from dataclasses import dataclass, field

from lobcore import Agent, Context, View


# component 割り当て — specs/spec.md と同期
COMP_WAKEUP = 0
COMP_PRICE = 1
COMP_QTY = 2
COMP_SIDE = 3
SENTINEL_FUNDAMENTAL = 0


def quote_mid(view: View, market_id: int = 0) -> float | None:
    m = view.market(market_id)
    if m.best_bid is not None and m.best_ask is not None:
        return (m.best_bid.price + m.best_ask.price) / 2.0
    if m.best_bid is not None:
        return float(m.best_bid.price)
    if m.best_ask is not None:
        return float(m.best_ask.price)
    return None


def _wakeup_delay(ctx: Context, mean_wakeup: float) -> int:
    rate = 1.0 / max(mean_wakeup, 1.0)
    delay = int(round(ctx.rng(COMP_WAKEUP).exponential(rate)))
    return max(1, delay)


def _qty(ctx: Context, qty_min: int, qty_max: int) -> int:
    if qty_max <= qty_min:
        return qty_min
    span = qty_max - qty_min + 1
    return qty_min + int(ctx.rng(COMP_QTY).next_u64() % span)


def _price_offset(ctx: Context, max_offset: int) -> int:
    if max_offset <= 0:
        return 0
    return int(ctx.rng(COMP_PRICE).next_u64() % (max_offset + 1))


@dataclass
class SharedFundamental:
    """sentinel_rng から事前生成した f_t。全 Fundamentalist が共有。"""

    f0: int
    sigma: float
    values: list[int] = field(default_factory=list)

    def prepare(self, kernel, end_time: int) -> None:
        rng = kernel.sentinel_rng(SENTINEL_FUNDAMENTAL)
        vals = [int(self.f0)]
        for _ in range(int(end_time)):
            step = int(round(rng.normal(0.0, float(self.sigma))))
            vals.append(vals[-1] + step)
        self.values = vals

    def at(self, t: int) -> int:
        if not self.values:
            raise RuntimeError("SharedFundamental.prepare() before use")
        idx = max(0, min(int(t), len(self.values) - 1))
        return self.values[idx]


@dataclass
class AgentParams:
    mean_wakeup: float = 800.0
    band: int = 30
    qty_min: int = 1
    qty_max: int = 5
    noise_offset_max: int = 15
    chartist_lookback: int = 3
    market_id: int = 0


def _next_order_id(agent: Agent, ctx: Context) -> int:
    seq = getattr(agent, "_order_seq", 0) + 1
    agent._order_seq = seq  # type: ignore[attr-defined]
    return (ctx.agent_id << 32) + seq


class Fundamentalist(Agent):
    def __init__(self, fundamental: SharedFundamental, params: AgentParams) -> None:
        self.fundamental = fundamental
        self.params = params
        self._order_seq = 0
        self._wake_count = 0

    def on_wakeup(self, view: View, ctx: Context) -> None:
        p = self.params
        f = self.fundamental.at(view.now)
        mid = quote_mid(view, p.market_id)
        qty = _qty(ctx, p.qty_min, p.qty_max)
        off = _price_offset(ctx, 2)
        half = max(1, p.band // 2)
        self._wake_count += 1

        # 毎回両側を出すとイベント過多。空板・乖離時・数回に一度だけリフレッシュ。
        need_quote = mid is None or abs(mid - f) > half or (self._wake_count % 2 == 1)
        if need_quote:
            ctx.submit(
                p.market_id,
                "buy",
                max(1, f - half - off),
                qty,
                order_id=_next_order_id(self, ctx),
            )
            ctx.submit(
                p.market_id,
                "sell",
                f + half + off,
                max(1, qty),
                order_id=_next_order_id(self, ctx),
            )

        if mid is not None:
            if mid < f - p.band:
                target = min(f, int(mid) + max(1, half // 2))
                ctx.submit(
                    p.market_id, "buy", target, qty, order_id=_next_order_id(self, ctx)
                )
            elif mid > f + p.band:
                target = max(f, int(mid) - max(1, half // 2))
                ctx.submit(
                    p.market_id, "sell", target, qty, order_id=_next_order_id(self, ctx)
                )

        nxt = view.now + _wakeup_delay(ctx, p.mean_wakeup)
        ctx.schedule_wakeup(nxt)


class Chartist(Agent):
    def __init__(self, params: AgentParams, *, take_prob: float = 0.25) -> None:
        self.params = params
        self.take_prob = float(take_prob)
        self.mid_history: list[float] = []
        self._order_seq = 0

    def on_wakeup(self, view: View, ctx: Context) -> None:
        p = self.params
        mid = quote_mid(view, p.market_id)
        if mid is not None:
            self.mid_history.append(mid)

        lookback = max(2, p.chartist_lookback)
        if len(self.mid_history) >= lookback:
            recent = self.mid_history[-lookback:]
            ret = recent[-1] - recent[0]
            qty = _qty(ctx, p.qty_min, p.qty_max)
            off = _price_offset(ctx, 3)
            take = ctx.rng(COMP_PRICE).uniform() < self.take_prob
            mkt = view.market(p.market_id)
            if ret > 0:
                if take and mkt.best_ask is not None:
                    price = mkt.best_ask.price
                else:
                    price = int(recent[-1]) + off
                ctx.submit(
                    p.market_id, "buy", price, qty, order_id=_next_order_id(self, ctx)
                )
            elif ret < 0:
                if take and mkt.best_bid is not None:
                    price = mkt.best_bid.price
                else:
                    price = int(recent[-1]) - off
                ctx.submit(
                    p.market_id, "sell", price, qty, order_id=_next_order_id(self, ctx)
                )

        nxt = view.now + _wakeup_delay(ctx, p.mean_wakeup)
        ctx.schedule_wakeup(nxt)


class NoiseTrader(Agent):
    def __init__(self, params: AgentParams, *, f0: int, take_prob: float = 0.35) -> None:
        self.params = params
        self.f0 = int(f0)
        self.take_prob = float(take_prob)
        self._order_seq = 0

    def on_wakeup(self, view: View, ctx: Context) -> None:
        p = self.params
        m = view.market(p.market_id)
        qty = _qty(ctx, p.qty_min, p.qty_max)
        off = _price_offset(ctx, p.noise_offset_max)
        buy = (ctx.rng(COMP_SIDE).next_u64() % 2) == 0
        take = ctx.rng(COMP_PRICE).uniform() < self.take_prob

        if buy:
            if take and m.best_ask is not None:
                price = m.best_ask.price  # marketable
            elif m.best_bid is not None:
                price = m.best_bid.price - off
            elif m.best_ask is not None:
                price = m.best_ask.price - 1 - off
            else:
                price = self.f0 - off
            ctx.submit(
                p.market_id, "buy", max(1, price), qty, order_id=_next_order_id(self, ctx)
            )
        else:
            if take and m.best_bid is not None:
                price = m.best_bid.price
            elif m.best_ask is not None:
                price = m.best_ask.price + off
            elif m.best_bid is not None:
                price = m.best_bid.price + 1 + off
            else:
                price = self.f0 + off
            ctx.submit(p.market_id, "sell", price, qty, order_id=_next_order_id(self, ctx))

        nxt = view.now + _wakeup_delay(ctx, p.mean_wakeup)
        ctx.schedule_wakeup(nxt)


def build_world_agents(
    *,
    n_f: int,
    n_c: int,
    n_n: int,
    fundamental: SharedFundamental,
    params: AgentParams,
    noise_take_prob: float = 0.15,
    chartist_take_prob: float = 0.25,
) -> list[Agent]:
    agents: list[Agent] = []
    for _ in range(n_f):
        agents.append(Fundamentalist(fundamental, params))
    for _ in range(n_c):
        agents.append(Chartist(params, take_prob=chartist_take_prob))
    for _ in range(n_n):
        agents.append(NoiseTrader(params, f0=fundamental.f0, take_prob=noise_take_prob))
    return agents
