"""拡張 logger: market step に加えて order / execution 送信を全て捕捉する。

C1 (FCN のみ) の Fig E (order size TS) のため、SG agent の submit_log だけ
でなく、全 agent (FCN 含む) の order を統一的に取得したい。PAMS の Logger
は process_order_log と process_execution_log を提供しているのでこれを
subclass で上書きする。
"""

from __future__ import annotations

from typing import Dict, List

from pams.logs.base import ExecutionLog, OrderLog
from pams.logs.market_step_loggers import MarketStepSaver


class OrderTrackingSaver(MarketStepSaver):
    """MarketStepSaver + order_logs + execution_logs."""

    def __init__(self) -> None:
        super().__init__()
        self.order_logs: List[Dict] = []
        self.execution_logs: List[Dict] = []

    def process_order_log(self, log: OrderLog) -> None:
        self.order_logs.append({
            "order_id": log.order_id,
            "market_id": log.market_id,
            "time": log.time,
            "agent_id": log.agent_id,
            "is_buy": log.is_buy,
            "kind": str(log.kind),
            "volume": log.volume,
            "price": log.price,
        })

    def process_execution_log(self, log: ExecutionLog) -> None:
        self.execution_logs.append({
            "market_id": log.market_id,
            "time": log.time,
            "buy_agent_id": log.buy_agent_id,
            "sell_agent_id": log.sell_agent_id,
            "buy_order_id": log.buy_order_id,
            "sell_order_id": log.sell_order_id,
            "price": log.price,
            "volume": log.volume,
        })
