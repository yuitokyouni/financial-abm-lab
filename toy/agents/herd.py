"""herd — Model H(herding、spec §3.2)。

``social_{i,t} = mean(ā_{t-h_i^s:t})``、ā = 集約行動履歴。
行動: ``a = sign(social) with prob p_i, else uniform on {-1,0,+1}``。
ヘテロ性: ``p_i ~ Uniform[0.6,0.95]``、``h_i^s ~ DiscreteUniform[5,50]``。

社会信号は ctx.observe("agg_action")(生の集約行動履歴)から内部で計算する(§3.3)。
確率的選択の乱数は **ctx.random 経由**(honest・再現可能)。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from provabm.ctx import Ctx

from toy.agents.base import Agent
from toy.observation import AGG_ACTION

# spec §3.2 のヘテロ性レンジ。
HS_MIN, HS_MAX = 5, 50
P_MIN, P_MAX = 0.6, 0.95


@dataclass(slots=True)
class HerdAgent(Agent):
    """1 体の herder。"""

    horizon: int  # h_i^s
    follow_prob: float  # p_i

    def decide(self, ctx: Ctx) -> int:
        social = ctx.observe(AGG_ACTION)
        signal = float(social[-self.horizon :].mean())
        if ctx.random("follow") < self.follow_prob:
            return int(np.sign(signal))
        # uniform on {-1,0,+1}: int(U[0,1)*3) - 1
        return int(ctx.random("explore") * 3) - 1


def build_herd_population(n: int, rng: np.random.Generator) -> list[HerdAgent]:
    """ヘテロな Model H 集団を生成。"""
    horizons = rng.integers(HS_MIN, HS_MAX + 1, size=n)
    probs = rng.uniform(P_MIN, P_MAX, size=n)
    return [HerdAgent(int(h), float(p)) for h, p in zip(horizons, probs, strict=True)]
