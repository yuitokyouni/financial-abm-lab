"""KronosLOBMarket: PAMS CDA に MMFCN (流動性供給) + KronosTrend/Fade (戦略層) を
乗せて run(seed) → dict を返す薄いラッパー (ABMModel protocol 準拠)。

設計:
  - configs/_base.py の YH006 流に倣い、Session 0 (warmup, no execution) +
    Session 1 (main, with execution) の 2 phase。
  - SharedSignalHub は Simulator 構築後に Trend/Fade 全 agent に inject する。
  - 結果は OHLCV 履歴 (bar_size 集約) + agent action log + SF 評価用 close 列。
"""
from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from pams.logs.market_step_loggers import MarketStepSaver
from pams.runners import SequentialRunner

# MMFCN を再利用 (流動性供給)
import sys
from pathlib import Path
_YH006_DIR = Path(__file__).resolve().parents[4] / "imported" / "speculation-game-info" / "experiments" / "YH006"
if _YH006_DIR.exists() and str(_YH006_DIR) not in sys.path:
    sys.path.insert(0, str(_YH006_DIR))
from mm_fcn_agent import MMFCNAgent  # noqa: E402

from ..kronos_aggregate.model import SignalProvider, constant_signal_provider
from .agents import KronosFadeAgent, KronosTrendAgent
from .bar_aggregator import build_ohlcv_from_market, closes_to_returns
from .signal_hub import SharedSignalHub


# --------------------------------------------------------------------------
# Config factory
# --------------------------------------------------------------------------

_MARKET = {
    "class": "Market",
    "tickSize": 0.00001,
    "marketPrice": 300.0,
}

_FCN_AGENTS = {
    "class": "MMFCNAgent",
    "numAgents": 30,
    "markets": ["Market"],
    "assetVolume": 50,
    "cashAmount": 10000,
    "fundamentalWeight": {"expon": [2.0]},
    "chartWeight": {"expon": [0.1]},
    "noiseWeight": {"expon": [0.5]},
    "meanReversionTime": {"uniform": [50, 100]},
    "noiseScale": 0.001,
    "timeWindowSize": [100, 200],
    "orderMargin": [0.01, 0.05],
    "orderVolume": 30,
}


def build_lob_config(
    *,
    warmup_steps: int,
    main_steps: int,
    n_trend: int = 25,
    n_fade: int = 25,
    n_fcn: int = 30,
    bar_size: int = 10,
    lookback_bars: int = 32,
    order_volume: int = 1,
    max_normal_orders: int = 1000,
    timestamp_start: str = "2026-06-01 09:00",
    timestamp_freq: str = "1min",
    initial_market_price: float = 300.0,
) -> Dict[str, Any]:
    """YH006 流の 2-session PAMS config を組み立てる。"""
    market = deepcopy(_MARKET)
    market["marketPrice"] = initial_market_price
    fcn = deepcopy(_FCN_AGENTS)
    fcn["numAgents"] = int(n_fcn)
    trend_block = {
        "class": "KronosTrendAgent",
        "numAgents": int(n_trend),
        "markets": ["Market"],
        "cashAmount": 100000,
        "assetVolume": 100,
        "orderVolume": int(order_volume),
        "barSize": int(bar_size),
        "lookbackBars": int(lookback_bars),
        "timestampStart": timestamp_start,
        "timestampFreq": timestamp_freq,
    }
    fade_block = deepcopy(trend_block)
    fade_block["class"] = "KronosFadeAgent"
    fade_block["numAgents"] = int(n_fade)
    return {
        "simulation": {
            "markets": ["Market"],
            "agents": ["FCNAgents", "TrendAgents", "FadeAgents"],
            "sessions": [
                {
                    "sessionName": 0,
                    "iterationSteps": int(warmup_steps),
                    "withOrderPlacement": True,
                    "withOrderExecution": False,
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
        "FCNAgents": fcn,
        "TrendAgents": trend_block,
        "FadeAgents": fade_block,
    }


# --------------------------------------------------------------------------
# Model wrapper
# --------------------------------------------------------------------------


class KronosLOBMarket:
    """PAMS CDA + MMFCN + Kronos Trend/Fade。`run(seed)` で 1 パス生成。"""

    name = "kronos_lob"

    def __init__(
        self,
        signal_provider: Optional[SignalProvider] = None,
        *,
        warmup_steps: int = 200,
        main_steps: int = 800,
        n_trend: int = 25,
        n_fade: int = 25,
        n_fcn: int = 30,
        bar_size: int = 10,
        lookback_bars: int = 32,
        order_volume: int = 1,
        initial_market_price: float = 300.0,
        max_normal_orders: int = 1000,
    ):
        if signal_provider is None:
            signal_provider = constant_signal_provider(pred_close_mean=initial_market_price * 1.001)
        self.signal_provider = signal_provider
        self.warmup_steps = warmup_steps
        self.main_steps = main_steps
        self.n_trend = n_trend
        self.n_fade = n_fade
        self.n_fcn = n_fcn
        self.bar_size = bar_size
        self.lookback_bars = lookback_bars
        self.order_volume = order_volume
        self.initial_market_price = initial_market_price
        self.max_normal_orders = max_normal_orders

    def _inject_hub(self, simulator, hub: SharedSignalHub) -> None:
        for a in simulator.agents:
            if isinstance(a, (KronosTrendAgent, KronosFadeAgent)):
                a.signal_hub = hub

    def run(self, *, seed: int) -> dict:
        cfg = build_lob_config(
            warmup_steps=self.warmup_steps, main_steps=self.main_steps,
            n_trend=self.n_trend, n_fade=self.n_fade, n_fcn=self.n_fcn,
            bar_size=self.bar_size, lookback_bars=self.lookback_bars,
            order_volume=self.order_volume,
            initial_market_price=self.initial_market_price,
            max_normal_orders=self.max_normal_orders,
        )

        hub = SharedSignalHub(
            provider=self.signal_provider, bar_size=self.bar_size,
            lookback=self.lookback_bars,
        )

        saver = MarketStepSaver()
        runner = SequentialRunner(settings=cfg, prng=random.Random(seed), logger=saver)
        runner.class_register(MMFCNAgent)
        runner.class_register(KronosTrendAgent)
        runner.class_register(KronosFadeAgent)

        # SequentialRunner.main は内部で simulator を構築して回す。inject は
        # _setup の後・session loop の前に行いたい。pams 0.2.2 では runner._setup
        # を分けて呼ぶ手段がないため、main() の前に手動で setup を回し、agent に
        # hub を inject してから session loop を回す手順を取る。
        runner._setup()
        self._inject_hub(runner.simulator, hub)
        runner._run()

        # 結果集計
        market = runner.simulator.markets[0]
        end_step = market.get_time() + 1
        history = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=end_step,
        )
        prices = history["close"].to_numpy(dtype=np.float64)
        returns = closes_to_returns(prices)

        trend_agents = [a for a in runner.simulator.agents if isinstance(a, KronosTrendAgent)]
        fade_agents = [a for a in runner.simulator.agents if isinstance(a, KronosFadeAgent)]

        return {
            "prices": prices,
            "returns": returns,
            "history": history,
            "trend_actions": [a.action_log for a in trend_agents],
            "fade_actions": [a.action_log for a in fade_agents],
            "signal_log": hub.signal_log(),
            "market_step_logs": list(saver.market_step_logs),
            "n_warmup_steps": self.warmup_steps,
            "n_main_steps": self.main_steps,
            "bar_size": self.bar_size,
        }
