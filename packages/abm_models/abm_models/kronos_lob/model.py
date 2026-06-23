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
from .adaptive_agent import KronosAdaptiveAgent
from .agents import KronosFadeAgent, KronosTrendAgent
from .bar_aggregator import build_ohlcv_from_market, closes_to_returns
from .predator import PredatorAgent
from .signal_hub import SharedSignalHub
from .spoofer import SpooferAgent


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
    n_adaptive: int = 0,
    bar_size: int = 10,
    lookback_bars: int = 32,
    order_volume: int = 1,
    max_normal_orders: int = 1000,
    timestamp_start: str = "2026-06-01 09:00",
    timestamp_freq: str = "1min",
    initial_market_price: float = 300.0,
    score_window: int = 50,
    r_min_base: float = 0.0,
    r_min_conf_coef: float = 0.0,
    execution_horizon: int = 1,
    fcn_order_volume: int = 30,
    n_predator: int = 0,
    predator_order_volume: int = 1,
    n_spoofer: int = 0,
    spoof_volume: int = 100,
    spoof_offset_ticks: int = 5,
    spoof_side: str = "both",
    spoof_ttl: int = 1,
) -> Dict[str, Any]:
    """YH006 流の 2-session PAMS config を組み立てる (YH007-2/3 共通)。

    n_adaptive>0 で KronosAdaptiveAgent (YH007-3 内生混合) を追加する。
    n_trend/n_fade=0 で純粋 adaptive 構成も可能。
    """
    market = deepcopy(_MARKET)
    market["marketPrice"] = initial_market_price
    fcn = deepcopy(_FCN_AGENTS)
    fcn["numAgents"] = int(n_fcn)
    fcn["orderVolume"] = int(fcn_order_volume)
    common = {
        "markets": ["Market"],
        "cashAmount": 100000,
        "assetVolume": 100,
        "orderVolume": int(order_volume),
        "barSize": int(bar_size),
        "lookbackBars": int(lookback_bars),
        "timestampStart": timestamp_start,
        "timestampFreq": timestamp_freq,
        "executionHorizon": int(execution_horizon),
    }
    agent_names: list[str] = ["FCNAgents"]
    extra_blocks: Dict[str, Any] = {}

    if n_trend > 0:
        b = deepcopy(common)
        b["class"] = "KronosTrendAgent"
        b["numAgents"] = int(n_trend)
        extra_blocks["TrendAgents"] = b
        agent_names.append("TrendAgents")
    if n_fade > 0:
        b = deepcopy(common)
        b["class"] = "KronosFadeAgent"
        b["numAgents"] = int(n_fade)
        extra_blocks["FadeAgents"] = b
        agent_names.append("FadeAgents")
    if n_adaptive > 0:
        b = deepcopy(common)
        b["class"] = "KronosAdaptiveAgent"
        b["numAgents"] = int(n_adaptive)
        b["scoreWindow"] = int(score_window)
        b["rMinBase"] = float(r_min_base)
        b["rMinConfCoef"] = float(r_min_conf_coef)
        extra_blocks["AdaptiveAgents"] = b
        agent_names.append("AdaptiveAgents")
    if n_predator > 0:
        extra_blocks["PredatorAgents"] = {
            "class": "PredatorAgent",
            "numAgents": int(n_predator),
            "markets": ["Market"],
            "cashAmount": 100000,
            "assetVolume": 100,
            "orderVolume": int(predator_order_volume),
        }
        agent_names.append("PredatorAgents")
    if n_spoofer > 0:
        extra_blocks["SpooferAgents"] = {
            "class": "SpooferAgent",
            "numAgents": int(n_spoofer),
            "markets": ["Market"],
            "cashAmount": 1_000_000,
            "assetVolume": 1000,
            "spoofVolume": int(spoof_volume),
            "spoofOffsetTicks": int(spoof_offset_ticks),
            "spoofSide": str(spoof_side),
            "spoofTtl": int(spoof_ttl),
        }
        agent_names.append("SpooferAgents")

    return {
        "simulation": {
            "markets": ["Market"],
            "agents": agent_names,
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
        **extra_blocks,
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
        n_adaptive: int = 0,
        bar_size: int = 10,
        lookback_bars: int = 32,
        order_volume: int = 1,
        initial_market_price: float = 300.0,
        max_normal_orders: int = 1000,
        score_window: int = 50,
        r_min_base: float = 0.0,
        r_min_conf_coef: float = 0.0,
        execution_horizon: int = 1,
        fcn_order_volume: int = 30,
        n_predator: int = 0,
        predator_order_volume: int = 1,
        n_spoofer: int = 0,
        spoof_volume: int = 100,
        spoof_offset_ticks: int = 5,
        spoof_side: str = "both",
        spoof_ttl: int = 1,
    ):
        if signal_provider is None:
            signal_provider = constant_signal_provider(pred_close_mean=initial_market_price * 1.001)
        self.signal_provider = signal_provider
        self.warmup_steps = warmup_steps
        self.main_steps = main_steps
        self.n_trend = n_trend
        self.n_fade = n_fade
        self.n_fcn = n_fcn
        self.n_adaptive = n_adaptive
        self.bar_size = bar_size
        self.lookback_bars = lookback_bars
        self.order_volume = order_volume
        self.initial_market_price = initial_market_price
        self.max_normal_orders = max_normal_orders
        self.score_window = score_window
        self.r_min_base = r_min_base
        self.r_min_conf_coef = r_min_conf_coef
        self.execution_horizon = execution_horizon
        self.fcn_order_volume = fcn_order_volume
        self.n_predator = n_predator
        self.predator_order_volume = predator_order_volume
        self.n_spoofer = n_spoofer
        self.spoof_volume = spoof_volume
        self.spoof_offset_ticks = spoof_offset_ticks
        self.spoof_side = spoof_side
        self.spoof_ttl = spoof_ttl

    def _inject_hub(self, simulator, hub: SharedSignalHub) -> None:
        from .agents import _KronosReaderAgent
        for a in simulator.agents:
            if isinstance(a, _KronosReaderAgent):
                a.signal_hub = hub

    def run(self, *, seed: int) -> dict:
        cfg = build_lob_config(
            warmup_steps=self.warmup_steps, main_steps=self.main_steps,
            n_trend=self.n_trend, n_fade=self.n_fade, n_fcn=self.n_fcn,
            n_adaptive=self.n_adaptive,
            bar_size=self.bar_size, lookback_bars=self.lookback_bars,
            order_volume=self.order_volume,
            initial_market_price=self.initial_market_price,
            max_normal_orders=self.max_normal_orders,
            score_window=self.score_window,
            r_min_base=self.r_min_base,
            r_min_conf_coef=self.r_min_conf_coef,
            execution_horizon=self.execution_horizon,
            fcn_order_volume=self.fcn_order_volume,
            n_predator=self.n_predator,
            predator_order_volume=self.predator_order_volume,
            n_spoofer=self.n_spoofer,
            spoof_volume=self.spoof_volume,
            spoof_offset_ticks=self.spoof_offset_ticks,
            spoof_side=self.spoof_side,
            spoof_ttl=self.spoof_ttl,
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
        runner.class_register(KronosAdaptiveAgent)
        runner.class_register(PredatorAgent)
        runner.class_register(SpooferAgent)

        runner._setup()
        self._inject_hub(runner.simulator, hub)
        runner._run()

        market = runner.simulator.markets[0]
        end_step = market.get_time() + 1
        history = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=end_step,
        )
        prices = history["close"].to_numpy(dtype=np.float64)
        returns = closes_to_returns(prices)

        trend_agents = [a for a in runner.simulator.agents if isinstance(a, KronosTrendAgent)]
        fade_agents = [a for a in runner.simulator.agents if isinstance(a, KronosFadeAgent)]
        adaptive_agents = [a for a in runner.simulator.agents if isinstance(a, KronosAdaptiveAgent)]
        predator_agents = [a for a in runner.simulator.agents if isinstance(a, PredatorAgent)]
        spoofer_agents = [a for a in runner.simulator.agents if isinstance(a, SpooferAgent)]

        return {
            "prices": prices,
            "returns": returns,
            "history": history,
            "trend_actions": [a.action_log for a in trend_agents],
            "fade_actions": [a.action_log for a in fade_agents],
            "adaptive_actions": [a.action_log for a in adaptive_agents],
            "predation_logs": [a.predation_log for a in predator_agents],
            "spoof_logs": [a.spoof_log for a in spoofer_agents],
            "signal_log": hub.signal_log(),
            "market_step_logs": list(saver.market_step_logs),
            "n_warmup_steps": self.warmup_steps,
            "n_main_steps": self.main_steps,
            "bar_size": self.bar_size,
        }
