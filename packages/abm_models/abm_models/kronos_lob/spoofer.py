"""YH007-7: 見せ板 agent (機構 5, layering/spoofing)。

毎 step、現在価格から `spoof_offset_ticks` 離れた価格に大 LIMIT を出して、TTL=1 で
次 step に expire させる。約定する前に消えるので "見せ板" として価格 / depth を歪める。
spec §2 機構 5 (増幅器仮説)。signal_hub 不要。

シンプル化: 片側 (bid 側 or ask 側 or 両側) を config で指定。両側だと
"layering" (sandwich) になり、Δ_bid と Δ_ask の sweet spot を奪う。
"""
from __future__ import annotations

from typing import Any, Dict, List, Union

from pams.agents import Agent
from pams.market import Market
from pams.order import LIMIT_ORDER, Cancel, Order


class SpooferAgent(Agent):
    """見せ板 LIMIT (TTL=1) を毎 step 出す agent。

    Settings:
        spoofVolume (int): 1 LIMIT あたりの大きさ (default 100)。
        spoofOffsetTicks (int): mid から離す tick 数 (default 5)。
        spoofSide (str): "buy" / "sell" / "both" (default "both")。
        spoofTtl (int): LIMIT の TTL step 数 (default 1)。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.spoof_volume: int = int(settings.get("spoofVolume", 100))
        self.spoof_offset_ticks: int = int(settings.get("spoofOffsetTicks", 5))
        side = str(settings.get("spoofSide", "both")).lower()
        if side not in ("buy", "sell", "both"):
            raise ValueError(f"spoofSide must be buy/sell/both, got {side}")
        self.spoof_side: str = side
        self.spoof_ttl: int = int(settings.get("spoofTtl", 1))
        self.spoof_log: list[tuple[int, str, float, int]] = []  # (time, side, price, vol)

    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        return sum((self.submit_orders_by_market(m) for m in markets), [])

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        if not self.is_market_accessible(market_id=market.market_id):
            return []
        cur_price = float(market.get_market_price())
        tick = float(market.tick_size)
        orders: List[Union[Order, Cancel]] = []
        time = market.get_time()

        if self.spoof_side in ("buy", "both"):
            # 高い bid を見せて bid 側 depth を膨らます
            price = max(tick, cur_price - tick * self.spoof_offset_ticks)
            orders.append(Order(
                agent_id=self.agent_id, market_id=market.market_id,
                is_buy=True, kind=LIMIT_ORDER,
                volume=int(self.spoof_volume), price=float(price), ttl=int(self.spoof_ttl),
            ))
            self.spoof_log.append((time, "buy_layer", float(price), int(self.spoof_volume)))

        if self.spoof_side in ("sell", "both"):
            # 安い ask を見せて ask 側 depth を膨らます
            price = cur_price + tick * self.spoof_offset_ticks
            orders.append(Order(
                agent_id=self.agent_id, market_id=market.market_id,
                is_buy=False, kind=LIMIT_ORDER,
                volume=int(self.spoof_volume), price=float(price), ttl=int(self.spoof_ttl),
            ))
            self.spoof_log.append((time, "sell_layer", float(price), int(self.spoof_volume)))

        return orders
