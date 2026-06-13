"""order book primitives: limit order, 連続マッチング, uniform-price clearing。

uniform-price clearing は batch 機構が使い、かつ engine と独立に単体テストできる
（research D5c / clearing 層の検証）。marginal quote が約定全量の価格に効く＝
demand-reduction の素地。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    BUY = 1
    SELL = -1


@dataclass
class Order:
    side: Side
    price: float          # 成行は BUY=+inf / SELL=-inf で表現
    size: float
    agent_id: str
    t: int


def clear_uniform(bids: list[Order], asks: list[Order]) -> tuple[float | None, float]:
    """call auction の uniform clearing。

    returns (clearing_price, matched_volume)。交差しなければ (None, 0.0)。
    clearing price = matched volume を最大化する価格（tie 時は中点）。
    全約定はこの単一価格で成立する（uniform-price）。
    """
    if not bids or not asks:
        return None, 0.0
    prices = sorted({o.price for o in bids + asks if math.isfinite(o.price)})
    if not prices:
        # 双方成行のみ → mid が無い。約定不能扱い。
        return None, 0.0

    def demand_at(p: float) -> float:
        return sum(o.size for o in bids if o.price >= p)

    def supply_at(p: float) -> float:
        return sum(o.size for o in asks if o.price <= p)

    best_p, best_vol = None, 0.0
    for p in prices:
        vol = min(demand_at(p), supply_at(p))
        if vol > best_vol + 1e-12:
            best_vol, best_p = vol, p
        elif abs(vol - best_vol) <= 1e-12 and best_p is not None and vol > 0:
            best_p = (best_p + p) / 2.0  # tie: 中点
    if best_p is None or best_vol <= 0:
        return None, 0.0
    return best_p, best_vol


def continuous_match(resting_bid: Order | None, resting_ask: Order | None,
                     taker: Order) -> tuple[float, float] | None:
    """成行 taker を MM の resting 気配にぶつける（価格優先）。

    returns (fill_price, size) or None。
    """
    if taker.side is Side.BUY and resting_ask is not None:
        return resting_ask.price, min(taker.size, resting_ask.size)
    if taker.side is Side.SELL and resting_bid is not None:
        return resting_bid.price, min(taker.size, resting_bid.size)
    return None
