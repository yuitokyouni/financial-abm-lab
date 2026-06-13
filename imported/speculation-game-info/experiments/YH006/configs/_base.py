"""Shared FCN baseline block (C1/C2/C3 common market + FCN config).

**MM 特化 FCN 仕様 (3B)**:
CI2002 default の FCN は SG-only 検証で示した通り、SG が純 MARKET_ORDER を
使う場合の liquidity 層として不足。fundamentalWeight / chartWeight /
noiseWeight / orderMargin を MM (market-maker) 役に寄せる:

- fundamentalWeight: expon(2.0) — fundamental 追随強め、価格を安定させる
- chartWeight:       expon(0.1) — trend フォローほぼ無効、liquidity 提供特化
- noiseWeight:       expon(0.5) — 中程度、板に多様性を残す
- orderMargin:       [0.01, 0.05] — mid から 1-5% 以内に限定して常時 bid/ask を出す
- numAgents:         30 (最小限)
- tickSize:          0.00001、marketPrice:  300.0 (CI2002 踏襲)

設計意図: SG 500 体の MARKET_ORDER を受け止める最小限の流動性層。
SG dynamics の観察対象は SG 自身、FCN は研究対象ではなく構造条件。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

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
    "orderVolume": 30,   # B-1: 30 FCN × 30 = 900 shares/step. SG Pareto tail (q_max~240) も吸収
}


def base_fcn_config(warmup_steps: int, main_steps: int, max_normal_orders: int) -> Dict[str, Any]:
    """C1 (FCN only) のベース config を返す。他条件はここに SGAgents を付け足す。"""
    return {
        "simulation": {
            "markets": ["Market"],
            "agents": ["FCNAgents"],
            "sessions": [
                {
                    "sessionName": 0,
                    "iterationSteps": warmup_steps,
                    "withOrderPlacement": True,
                    "withOrderExecution": False,
                    "withPrint": True,
                    "maxNormalOrders": max_normal_orders,
                },
                {
                    "sessionName": 1,
                    "iterationSteps": main_steps,
                    "withOrderPlacement": True,
                    "withOrderExecution": True,
                    "withPrint": True,
                    "maxNormalOrders": max_normal_orders,
                },
            ],
        },
        "Market": deepcopy(_MARKET),
        "FCNAgents": deepcopy(_FCN_AGENTS),
    }


def sg_block(
    num_agents: int,
    wealth_mode: str,
    c_ticks: float,
    M: int = 5,
    S: int = 2,
    B: int = 9,
    pareto_alpha: float = 1.5,
    pareto_xmin: float = 9.0,
) -> Dict[str, Any]:
    """SG agent block. wealthMode ∈ {"uniform","pareto"}."""
    return {
        "class": "SpeculationAgent",
        "numAgents": num_agents,
        "markets": ["Market"],
        "cashAmount": 9,
        "assetVolume": 0,
        "M": M,
        "S": S,
        "B": B,
        "cTicks": c_ticks,
        "wealthMode": wealth_mode,
        "paretoAlpha": pareto_alpha,
        "paretoXmin": pareto_xmin,
    }
