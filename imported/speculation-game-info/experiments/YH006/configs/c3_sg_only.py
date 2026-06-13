"""(3A) SG-only 構成: FCN を完全に 0 にして SG だけで config C3 を回す。

PAMS の `market.remain_executable_orders` は MARKET_ORDER 同士を約定させない
実装 (market.py:798-834) のため、この構成では SG の成行注文が誰にも約定され
ず 0% fill に落ちる可能性が高い。仮説検証のための構成。
"""

from __future__ import annotations

from typing import Any, Dict

from ._base import base_fcn_config, sg_block


def make_config(
    warmup_steps: int = 200,
    main_steps: int = 1500,
    num_sg_agents: int = 500,
    c_ticks: float = 28.0,
    pareto_alpha: float = 1.5,
    pareto_xmin: float = 9.0,
    max_normal_orders: int = 2000,
) -> Dict[str, Any]:
    # base_fcn_config で骨組みを作って FCN 部分を消す。
    cfg = base_fcn_config(warmup_steps=warmup_steps, main_steps=main_steps,
                          max_normal_orders=max_normal_orders)
    cfg["simulation"]["agents"] = ["SGAgents"]
    cfg.pop("FCNAgents", None)
    cfg["SGAgents"] = sg_block(
        num_agents=num_sg_agents,
        wealth_mode="pareto",
        c_ticks=c_ticks,
        pareto_alpha=pareto_alpha,
        pareto_xmin=pareto_xmin,
    )
    return cfg
