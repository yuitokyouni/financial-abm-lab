"""エージェント規則（非学習）。

- MarketMaker: inventory-free、belief m 周りに ±h で両側気配。jump を観測した次に学習（1期 staleness）。
- arbitrageur: 反応的・学習なし。stale quote が利益的なら picking-off（逆選択源）。
- noise: 無方向（engine が rng で生成）。
"""
from __future__ import annotations

from .book import Side


class MarketMaker:
    def __init__(self, initial_price: float) -> None:
        self.m = initial_price  # belief（= 直近に学習した true value）

    def quote(self, h: float) -> tuple[float, float]:
        return self.m - h, self.m + h  # (bid, ask)

    def learn(self, v: float) -> None:
        self.m = v


def arb_decision(v: float, bid: float, ask: float) -> tuple[Side, float] | None:
    """informed arbitrageur の picking-off 判定。

    returns (side, profit) — side は arb の方向、profit は arb 利得(=MM 損)。
    利益的でなければ None。
    """
    if v > ask:
        return Side.BUY, v - ask
    if v < bid:
        return Side.SELL, bid - v
    return None
