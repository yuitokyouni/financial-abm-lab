"""MMFCNAgent: pams.agents.FCNAgent を subclass し order_volume を config で
スケール可能にした market-maker 役 FCN。

なぜ subclass するか:
  pams 0.2.2 の FCNAgent.submit_orders_by_market (fcn_agent.py:178, :213) は
  order_volume = 1 をハードコードしている。SG 500 体の MARKET_ORDER 需要に
  対し 30 FCN × 1 share = 30 shares/step では 20:1 需給不足、open/close
  約定率が 5-15% に止まる (B-1 smoke で実測)。FCN は YH006 の研究対象では
  なく流動性供給の structural condition なので、order_volume は controlled
  variable として自由に動かしてよい。

実装方針:
  FCNAgent.submit_orders_by_market のロジック全体を踏襲し、order_volume の
  数値だけ self.order_volume_param で差し替える。それ以外 (fundamental /
  chart / noise weight, margin handling) は pams のままにして、bug fix が
  入っても upstream に追従しやすくする。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Union

from pams.agents import FCNAgent
from pams.agents.fcn_agent import MARGIN_FIXED, MARGIN_NORMAL
from pams.market import Market
from pams.order import LIMIT_ORDER, Cancel, Order


class MMFCNAgent(FCNAgent):
    """FCNAgent + order_volume scalable via config (default 10)."""

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.order_volume_param: int = int(settings.get("orderVolume", 10))

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        """FCNAgent.submit_orders_by_market を踏襲し order_volume だけ差し替える。

        参考: pams/agents/fcn_agent.py:124-240
        """
        orders: List[Union[Order, Cancel]] = []
        if not self.is_market_accessible(market_id=market.market_id):
            return orders

        time: int = market.get_time()
        time_window_size: int = min(time, self.time_window_size)
        assert time_window_size >= 0
        assert self.fundamental_weight >= 0.0
        assert self.chart_weight >= 0.0
        assert self.noise_weight >= 0.0

        fundamental_scale: float = 1.0 / max(self.mean_reversion_time, 1)
        fundamental_log_return = fundamental_scale * math.log(
            market.get_fundamental_price() / market.get_market_price()
        )
        assert self.is_finite(fundamental_log_return)

        chart_scale: float = 1.0 / max(time_window_size, 1)
        chart_mean_log_return = chart_scale * math.log(
            market.get_market_price() / market.get_market_price(time - time_window_size)
        )
        assert self.is_finite(chart_mean_log_return)

        noise_log_return: float = self.noise_scale * self.prng.gauss(mu=0.0, sigma=1.0)
        assert self.is_finite(noise_log_return)

        expected_log_return: float = (
            1.0 / (self.fundamental_weight + self.chart_weight + self.noise_weight)
        ) * (
            self.fundamental_weight * fundamental_log_return
            + self.chart_weight
            * chart_mean_log_return
            * (1 if self.is_chart_following else -1)
            + self.noise_weight * noise_log_return
        )
        assert self.is_finite(expected_log_return)

        expected_future_price: float = market.get_market_price() * math.exp(
            expected_log_return * self.time_window_size
        )
        assert self.is_finite(expected_future_price)

        order_volume: int = int(self.order_volume_param)

        if self.margin_type == MARGIN_FIXED:
            assert 0.0 <= self.order_margin <= 1.0
            if expected_future_price > market.get_market_price():
                order_price = expected_future_price * (1 - self.order_margin)
                orders.append(Order(
                    agent_id=self.agent_id,
                    market_id=market.market_id,
                    is_buy=True,
                    kind=LIMIT_ORDER,
                    volume=order_volume,
                    price=order_price,
                    ttl=self.time_window_size,
                ))
            if expected_future_price < market.get_market_price():
                order_price = expected_future_price * (1 + self.order_margin)
                orders.append(Order(
                    agent_id=self.agent_id,
                    market_id=market.market_id,
                    is_buy=False,
                    kind=LIMIT_ORDER,
                    volume=order_volume,
                    price=order_price,
                    ttl=self.time_window_size,
                ))

        if self.margin_type == MARGIN_NORMAL:
            assert self.order_margin >= 0.0
            order_price = (
                expected_future_price
                + self.prng.gauss(mu=0.0, sigma=1.0) * self.order_margin
            )
            assert order_price >= 0.0
            assert order_volume > 0
            if expected_future_price > market.get_market_price():
                orders.append(Order(
                    agent_id=self.agent_id,
                    market_id=market.market_id,
                    is_buy=True,
                    kind=LIMIT_ORDER,
                    volume=order_volume,
                    price=order_price,
                    ttl=self.time_window_size,
                ))
            if expected_future_price < market.get_market_price():
                orders.append(Order(
                    agent_id=self.agent_id,
                    market_id=market.market_id,
                    is_buy=False,
                    kind=LIMIT_ORDER,
                    volume=order_volume,
                    price=order_price,
                    ttl=self.time_window_size,
                ))
        return orders
