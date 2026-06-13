"""C1: FCN baseline (no SG agents)."""

from __future__ import annotations

from typing import Any, Dict

from ._base import base_fcn_config


def make_config(
    warmup_steps: int = 500,
    main_steps: int = 5000,
    max_normal_orders: int = 2000,
) -> Dict[str, Any]:
    cfg = base_fcn_config(warmup_steps=warmup_steps, main_steps=main_steps,
                          max_normal_orders=max_normal_orders)
    return cfg
