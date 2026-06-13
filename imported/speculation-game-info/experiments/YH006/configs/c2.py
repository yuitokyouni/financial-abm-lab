"""C2: FCN + SG agents (uniform initial wealth)."""

from __future__ import annotations

from typing import Any, Dict

from ._base import base_fcn_config, sg_block


def make_config(
    warmup_steps: int = 500,
    main_steps: int = 5000,
    num_sg_agents: int = 500,
    c_ticks: float = 0.03,
    max_normal_orders: int = 2000,
) -> Dict[str, Any]:
    cfg = base_fcn_config(warmup_steps=warmup_steps, main_steps=main_steps,
                          max_normal_orders=max_normal_orders)
    cfg["simulation"]["agents"] = ["FCNAgents", "SGAgents"]
    cfg["SGAgents"] = sg_block(
        num_agents=num_sg_agents,
        wealth_mode="uniform",
        c_ticks=c_ticks,
    )
    return cfg
