"""全 7 条件の condition spec dict.

S2 で active なのは C0u/C0p のみ。C2/C3/C2_A1/C3_A1/C3_A3 は S3-S6 で使う
placeholder として spec を記述しておく (パラメタ参照用、S2 段階では実行しない)。

各条件 spec のキー:
  - world: "agg" | "lob"
  - wealth_mode: "uniform" | "pareto"
  - q_rule: "wealth" | "const"   (wealth = ⌊w/B⌋ デフォ、const = q_const 固定)
  - lifetime_cap: bool             (A3 ablation で True)
  - その他、world ごとのパラメタ
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class CondSpec:
    name: str
    world: str          # "agg" | "lob"
    wealth_mode: str    # "uniform" | "pareto"
    q_rule: str         # "wealth" (Eq.1 ⌊w/B⌋) | "const" (A1 ablation)
    lifetime_cap: bool  # True for A3 ablation
    notes: str = ""

    def asdict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "world": self.world,
            "wealth_mode": self.wealth_mode, "q_rule": self.q_rule,
            "lifetime_cap": self.lifetime_cap, "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# 共通パラメタ (Phase 1 と完全一致、SPEC §3)
# ---------------------------------------------------------------------------

# aggregate (C0u, C0p)
AGG_PARAMS: Dict[str, Any] = {
    "N": 100,
    "M": 5,
    "S": 2,
    "T": 50_000,
    "B": 9,
    "C": 3.0,
    "p0": 100.0,
    "history_mode": "endogenous",
    "decision_mode": "strategy",
    "order_size_buckets": (50, 100),
}

# Pareto wealth init (C0p, C3, C3_A1, C3_A3 共通)
PARETO_ALPHA: float = 1.5
PARETO_XMIN: int = 9    # = B

# LOB session params (C2, C3, C2_A1, C3_A1, C3_A3 共通、Phase 1 default)
LOB_PARAMS: Dict[str, Any] = {
    "N_sg": 100,
    "B": 9,
    "M": 5,
    "S": 2,
    "warmup_steps": 200,
    "main_steps": 1500,
    "num_fcn": 30,
    "max_normal_orders": 500,
    "c_ticks": 28.0,    # Phase 1 較正値 (要 calibration JSON load、ここは default)
}


# ---------------------------------------------------------------------------
# 7 条件 spec dict
# ---------------------------------------------------------------------------

CONDITIONS: Dict[str, CondSpec] = {
    "C0u": CondSpec(
        name="C0u", world="agg", wealth_mode="uniform",
        q_rule="wealth", lifetime_cap=False,
        notes="aggregate baseline, uniform init",
    ),
    "C0p": CondSpec(
        name="C0p", world="agg", wealth_mode="pareto",
        q_rule="wealth", lifetime_cap=False,
        notes="aggregate baseline, Pareto α=1.5 init",
    ),
    "C2": CondSpec(
        name="C2", world="lob", wealth_mode="uniform",
        q_rule="wealth", lifetime_cap=False,
        notes="LOB main, uniform init (Phase 1 と同設定)",
    ),
    "C3": CondSpec(
        name="C3", world="lob", wealth_mode="pareto",
        q_rule="wealth", lifetime_cap=False,
        notes="LOB main, Pareto α=1.5 init (Phase 1 主実験)",
    ),
    "C2_A1": CondSpec(
        name="C2_A1", world="lob", wealth_mode="uniform",
        q_rule="const", lifetime_cap=False,
        notes="A1 ablation: q = q_const (LOB uniform)",
    ),
    "C3_A1": CondSpec(
        name="C3_A1", world="lob", wealth_mode="pareto",
        q_rule="const", lifetime_cap=False,
        notes="A1 ablation 主役: q = q_const (LOB Pareto)",
    ),
    "C3_A3": CondSpec(
        name="C3_A3", world="lob", wealth_mode="pareto",
        q_rule="wealth", lifetime_cap=True,
        notes="A3 ablation: lifetime cap τ_max (LOB Pareto)",
    ),
}


# Default seed range for Phase 2 ensemble (Brief §3 S2)
ENSEMBLE_SEED_BASE = 1000
ENSEMBLE_N_TRIALS = 100


def aggregate_kwargs(cond: CondSpec) -> Dict[str, Any]:
    """aggregate_sim.simulate_aggregate に渡す kwargs を返す。"""
    assert cond.world == "agg", f"{cond.name} is not aggregate"
    kwargs = dict(AGG_PARAMS)
    kwargs["wealth_mode"] = cond.wealth_mode
    if cond.wealth_mode == "pareto":
        kwargs["pareto_alpha"] = PARETO_ALPHA
        kwargs["pareto_xmin"] = PARETO_XMIN
    return kwargs


def lob_settings(cond: CondSpec, c_ticks: Optional[float] = None) -> Dict[str, Any]:
    """LOB run_experiment 用の設定を返す (S3 で本格使用、S2 は smoke のみ)。"""
    assert cond.world == "lob", f"{cond.name} is not LOB"
    s = dict(LOB_PARAMS)
    if c_ticks is not None:
        s["c_ticks"] = c_ticks
    s["wealth_mode"] = cond.wealth_mode
    s["q_rule"] = cond.q_rule
    s["lifetime_cap"] = cond.lifetime_cap
    return s
