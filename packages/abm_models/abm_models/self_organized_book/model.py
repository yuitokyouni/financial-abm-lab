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
from .kronos_agent import KronosCIAgent, KronosQuantileHub
from .kronos_quantile import KronosQuantilePredictor
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
    zi_phi_ar1: float = 0.418,
    zi_sigma_ar1_abs: float = 6e-3,
    zi_mu_ar1: float = 0.0,
    # 戦略役 ZI (matched_ar1) を 2nd group で混在させる (P3 dose-match 用)
    n_zi_strategy: int = 0,
    zi_strategy_mode: str = "matched_ar1",
    zi_strategy_phi_ar1: float = 0.418,
    zi_strategy_sigma_ar1_abs: float = 6e-3,
    zi_strategy_mu_ar1: float = 0.0,
    zi_strategy_margin_min: float = 2.0e-5,
    zi_strategy_margin_max: float = 6.0e-5,
    n_kronos: int = 0,
    kronos_lookback_bars: int = 32,
    kronos_margin_min: float = 3e-5,
    kronos_margin_max: float = 1e-4,
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
        "phiAr1": float(zi_phi_ar1),
        "sigmaAr1Abs": float(zi_sigma_ar1_abs),
        "muAr1": float(zi_mu_ar1),
        "marginMin": float(margin_min),
        "marginMax": float(margin_max),
    }
    agents_list = ["ZIAgents"]
    extra_blocks: Dict[str, Any] = {}
    # 戦略役 ZI (matched_ar1) を 2nd group として混在 (P3 dose-match: kronos と同じ流動性役 ZI
    # を両 condition で持ち、戦略役だけが Kronos か ZI-matched で違う構成にできる)
    if n_zi_strategy > 0:
        extra_blocks["ZIAgentsStrategy"] = {
            "class": "ZIAgent",
            "numAgents": int(n_zi_strategy),
            "markets": ["Market"],
            "cashAmount": 1_000_000,
            "assetVolume": 1000,
            "barSize": int(bar_size),
            "orderTtl": int(order_ttl),
            "orderVolume": int(order_volume),
            "ziMode": zi_strategy_mode,
            "phiAr1": float(zi_strategy_phi_ar1),
            "sigmaAr1Abs": float(zi_strategy_sigma_ar1_abs),
            "muAr1": float(zi_strategy_mu_ar1),
            "marginMin": float(zi_strategy_margin_min),
            "marginMax": float(zi_strategy_margin_max),
        }
        agents_list.append("ZIAgentsStrategy")
    if n_kronos > 0:
        # 各 Kronos agent に固有の agent_rank を割り当て (0..1 等間隔)
        for i in range(n_kronos):
            rank = (i + 0.5) / n_kronos if n_kronos > 1 else 0.5
            name = f"KronosAgents{i}"
            extra_blocks[name] = {
                "class": "KronosCIAgent",
                "numAgents": 1,
                "markets": ["Market"],
                "cashAmount": 1_000_000,
                "assetVolume": 1000,
                "barSize": int(bar_size),
                "orderTtl": int(order_ttl),
                "orderVolume": int(order_volume),
                "agentRank": float(rank),
                "marginMin": float(kronos_margin_min),
                "marginMax": float(kronos_margin_max),
            }
            agents_list.append(name)
    return {
        "simulation": {
            "markets": ["Market"],
            "agents": agents_list,
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
        **extra_blocks,
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
        zi_phi_ar1: float = 0.418,
        zi_sigma_ar1_abs: float = 6e-3,
        zi_mu_ar1: float = 0.0,
        n_zi_strategy: int = 0,
        zi_strategy_mode: str = "matched_ar1",
        zi_strategy_phi_ar1: float = 0.418,
        zi_strategy_sigma_ar1_abs: float = 6e-3,
        zi_strategy_mu_ar1: float = 0.0,
        zi_strategy_margin_min: float = 2.0e-5,
        zi_strategy_margin_max: float = 6.0e-5,
        extra_agent_classes: Optional[List[Type]] = None,
        # Kronos backend
        n_kronos: int = 0,
        kronos_lookback_bars: int = 32,
        kronos_n_samples: int = 32,
        kronos_temperature: float = 1.0,
        kronos_top_p: float = 0.9,
        kronos_margin_min: float = 3e-5,
        kronos_margin_max: float = 1e-4,
        kronos_predictor: Optional[KronosQuantilePredictor] = None,
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
        self.zi_phi_ar1 = zi_phi_ar1
        self.zi_sigma_ar1_abs = zi_sigma_ar1_abs
        self.zi_mu_ar1 = zi_mu_ar1
        self.n_zi_strategy = n_zi_strategy
        self.zi_strategy_mode = zi_strategy_mode
        self.zi_strategy_phi_ar1 = zi_strategy_phi_ar1
        self.zi_strategy_sigma_ar1_abs = zi_strategy_sigma_ar1_abs
        self.zi_strategy_mu_ar1 = zi_strategy_mu_ar1
        self.zi_strategy_margin_min = zi_strategy_margin_min
        self.zi_strategy_margin_max = zi_strategy_margin_max
        self.extra_agent_classes = extra_agent_classes or []
        self.n_kronos = n_kronos
        self.kronos_lookback_bars = kronos_lookback_bars
        self.kronos_n_samples = kronos_n_samples
        self.kronos_temperature = kronos_temperature
        self.kronos_top_p = kronos_top_p
        self.kronos_margin_min = kronos_margin_min
        self.kronos_margin_max = kronos_margin_max
        self.kronos_predictor = kronos_predictor

    def run(self, *, seed: int) -> dict:
        cfg = build_sob_config(
            warmup_steps=self.warmup_steps, main_steps=self.main_steps, n_zi=self.n_zi,
            bar_size=self.bar_size, order_ttl=self.order_ttl, order_volume=self.order_volume,
            sigma_eval=self.sigma_eval,
            margin_min=self.margin_min, margin_max=self.margin_max,
            initial_market_price=self.initial_market_price,
            tick_size=self.tick_size, zi_mode=self.zi_mode,
            zi_phi_ar1=self.zi_phi_ar1,
            zi_sigma_ar1_abs=self.zi_sigma_ar1_abs,
            zi_mu_ar1=self.zi_mu_ar1,
            n_zi_strategy=self.n_zi_strategy,
            zi_strategy_mode=self.zi_strategy_mode,
            zi_strategy_phi_ar1=self.zi_strategy_phi_ar1,
            zi_strategy_sigma_ar1_abs=self.zi_strategy_sigma_ar1_abs,
            zi_strategy_mu_ar1=self.zi_strategy_mu_ar1,
            zi_strategy_margin_min=self.zi_strategy_margin_min,
            zi_strategy_margin_max=self.zi_strategy_margin_max,
            n_kronos=self.n_kronos,
            kronos_lookback_bars=self.kronos_lookback_bars,
            kronos_margin_min=self.kronos_margin_min,
            kronos_margin_max=self.kronos_margin_max,
        )
        # Kronos predictor (n_kronos>0 のとき必須)
        kronos_hub = None
        if self.n_kronos > 0:
            predictor = self.kronos_predictor or KronosQuantilePredictor(
                lookback=self.kronos_lookback_bars,
                n_samples=self.kronos_n_samples,
                temperature=self.kronos_temperature,
                top_p=self.kronos_top_p,
            )
            kronos_hub = KronosQuantileHub(
                predictor=predictor,
                bar_size=self.bar_size,
                lookback_bars=self.kronos_lookback_bars,
            )
        saver = MarketStepSaver()
        runner = SequentialRunner(settings=cfg, prng=random.Random(seed), logger=saver)
        runner.class_register(ZIAgent)
        if self.n_kronos > 0:
            runner.class_register(KronosCIAgent)
        for cls in self.extra_agent_classes:
            runner.class_register(cls)
        runner._setup()
        # inject Kronos hub into all KronosCIAgent instances
        if kronos_hub is not None:
            for a in runner.simulator.agents:
                if isinstance(a, KronosCIAgent):
                    a.kronos_hub = kronos_hub
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
        kronos_agents = [a for a in runner.simulator.agents if isinstance(a, KronosCIAgent)]
        n_submitted = sum(len(a.action_log) for a in zi_agents + kronos_agents)
        n_executed = sum(len(a.executed_log) for a in zi_agents + kronos_agents)
        n_canceled = sum(len(a.canceled_log) for a in zi_agents + kronos_agents)

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
            "zi_agents": zi_agents,
            "kronos_agents": kronos_agents,
            "kronos_hub_calls": (kronos_hub.call_log if kronos_hub is not None else []),
            "warmup_bars": warmup_bars,
            "bar_size": self.bar_size,
        }
