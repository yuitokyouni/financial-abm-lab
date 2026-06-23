"""SelfOrganizedBookMarket: 全 LIMIT 構成の PAMS CDA 実行ラッパー (spec 003)。

P0: ZIAgent のみで warmup 兼疎通テスト。
P1 以降: ZI-matched と KronosCIAgent を追加。

設計 (spec 003):
  - **MMFCN 廃止** (§3.4): 流動性は agent 自身の resting 指値で内生。
  - **warmup = ZI で板を温める** (§3.4): 起動直後の空板問題を解消。
  - 2-session 構成は維持 (Session 0 = warmup, Session 1 = main)。withOrderExecution は
    両セッションとも True (約定を起こさないと板が温まらない / mid が動かない)。これは
    naïve 設計 (002, Session 0 で withOrderExecution=False) との重要な違い。
  - run 戻り値に history_market / history_mid 両方を含める (002 §8.x の規律維持)。
"""
from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type

import numpy as np

from pams.logs.market_step_loggers import MarketStepSaver
from pams.runners import SequentialRunner

from ..kronos_lob.bar_aggregator import build_ohlcv_from_market, closes_to_returns
from .zi_agent import ZIAgent


_MARKET = {
    "class": "Market",
    "tickSize": 0.00001,
    "marketPrice": 300.0,
}


def build_sob_config(
    *,
    warmup_steps: int,
    main_steps: int,
    n_zi: int,
    bar_size: int = 10,
    order_ttl: int = 20,
    order_volume: int = 1,
    sigma_eval: float = 0.005,
    margin_min: float = 0.001,
    margin_max: float = 0.01,
    initial_market_price: float = 300.0,
    tick_size: float = 0.00001,
    max_normal_orders: int = 4000,
    zi_mode: str = "naive",
) -> Dict[str, Any]:
    market = deepcopy(_MARKET)
    market["marketPrice"] = initial_market_price
    market["tickSize"] = tick_size
    zi_block = {
        "class": "ZIAgent",
        "numAgents": int(n_zi),
        "markets": ["Market"],
        "cashAmount": 1_000_000,
        "assetVolume": 1000,
        "barSize": int(bar_size),
        "orderTtl": int(order_ttl),
        "orderVolume": int(order_volume),
        "ziMode": zi_mode,
        "sigmaEval": float(sigma_eval),
        "marginMin": float(margin_min),
        "marginMax": float(margin_max),
    }
    return {
        "simulation": {
            "markets": ["Market"],
            "agents": ["ZIAgents"],
            "sessions": [
                {
                    "sessionName": 0,
                    "iterationSteps": int(warmup_steps),
                    "withOrderPlacement": True,
                    "withOrderExecution": True,  # spec 003: warmup でも約定許可
                    "withPrint": False,
                    "maxNormalOrders": int(max_normal_orders),
                },
                {
                    "sessionName": 1,
                    "iterationSteps": int(main_steps),
                    "withOrderPlacement": True,
                    "withOrderExecution": True,
                    "withPrint": False,
                    "maxNormalOrders": int(max_normal_orders),
                },
            ],
        },
        "Market": market,
        "ZIAgents": zi_block,
    }


class SelfOrganizedBookMarket:
    """全 LIMIT 構成の PAMS CDA ラッパー。

    P0: ZI のみ。P1 以降で Kronos / matched ZI を追加。
    """

    name = "self_organized_book"

    def __init__(
        self,
        *,
        warmup_steps: int = 100,
        main_steps: int = 500,
        n_zi: int = 50,
        bar_size: int = 10,
        order_ttl: int = 20,
        order_volume: int = 1,
        sigma_eval: float = 0.005,
        margin_min: float = 0.001,
        margin_max: float = 0.01,
        initial_market_price: float = 300.0,
        tick_size: float = 0.00001,
        zi_mode: str = "naive",
        extra_agent_classes: Optional[List[Type]] = None,
    ):
        self.warmup_steps = warmup_steps
        self.main_steps = main_steps
        self.n_zi = n_zi
        self.bar_size = bar_size
        self.order_ttl = order_ttl
        self.order_volume = order_volume
        self.sigma_eval = sigma_eval
        self.margin_min = margin_min
        self.margin_max = margin_max
        self.initial_market_price = initial_market_price
        self.tick_size = tick_size
        self.zi_mode = zi_mode
        self.extra_agent_classes = extra_agent_classes or []

    def run(self, *, seed: int) -> dict:
        cfg = build_sob_config(
            warmup_steps=self.warmup_steps, main_steps=self.main_steps, n_zi=self.n_zi,
            bar_size=self.bar_size, order_ttl=self.order_ttl, order_volume=self.order_volume,
            sigma_eval=self.sigma_eval,
            margin_min=self.margin_min, margin_max=self.margin_max,
            initial_market_price=self.initial_market_price,
            tick_size=self.tick_size, zi_mode=self.zi_mode,
        )
        saver = MarketStepSaver()
        runner = SequentialRunner(settings=cfg, prng=random.Random(seed), logger=saver)
        runner.class_register(ZIAgent)
        for cls in self.extra_agent_classes:
            runner.class_register(cls)
        runner._setup()
        runner._run()

        market = runner.simulator.markets[0]
        end_step = market.get_time() + 1

        history_market = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=end_step,
            price_source="market",
        )
        history_mid = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=end_step,
            price_source="mid",
        )
        # main session 区間のみで SF を取る (warmup の transient を除外)
        warmup_bars = self.warmup_steps // self.bar_size
        closes_main_market = history_market["close"].to_numpy(dtype=np.float64)[warmup_bars:]
        closes_main_mid = history_mid["close"].to_numpy(dtype=np.float64)[warmup_bars:]
        ret_market = closes_to_returns(closes_main_market)
        ret_mid = closes_to_returns(closes_main_mid)

        zi_agents = [a for a in runner.simulator.agents if isinstance(a, ZIAgent)]
        n_submitted = sum(len(a.action_log) for a in zi_agents)
        n_executed = sum(len(a.executed_log) for a in zi_agents)
        n_canceled = sum(len(a.canceled_log) for a in zi_agents)

        return {
            "history_market": history_market,
            "history_mid": history_mid,
            "closes_main_market": closes_main_market,
            "closes_main_mid": closes_main_mid,
            "returns_main_market": ret_market,
            "returns_main_mid": ret_mid,
            "n_submitted": n_submitted,
            "n_executed": n_executed,
            "n_canceled": n_canceled,
            "agents": zi_agents,
            "warmup_bars": warmup_bars,
            "bar_size": self.bar_size,
        }
