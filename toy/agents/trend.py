"""trend — Model T(trend-following、spec §3.2)。

``trend_{i,t} = mean(r_{t-h_i:t}) / std(r_{t-h_i:t})``、r = log-return。
行動: ``a = sign(trend) if |trend| > θ_i else 0``。
ヘテロ性: ``h_i ~ DiscreteUniform[5,50]``、``θ_i ~ Uniform[0.5,2.0]``。

観測は ctx.observe("price_returns")(生 log-return 履歴)から取り、trend は **内部で** 計算する
(観測チャネル介入が機構の入力源を degrade するが機構自体は ablate しない設計、§3.3)。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from provabm.ctx import Ctx

from toy.agents.base import Agent
from toy.observation import PRICE_RETURNS

# spec §3.2 のヘテロ性レンジ。
H_MIN, H_MAX = 5, 50
THETA_MIN, THETA_MAX = 0.5, 2.0


@dataclass(slots=True)
class TrendAgent(Agent):
    """1 体の trend-follower。"""

    horizon: int  # h_i
    theta: float  # θ_i(発火閾値)

    def decide(self, ctx: Ctx) -> int:
        returns = ctx.observe(PRICE_RETURNS)
        window = returns[-self.horizon :]
        sd = float(window.std())
        if sd == 0.0:  # 履歴ゼロ/定数(burn-in 初期)→ 中立
            return 0
        trend = float(window.mean()) / sd
        if abs(trend) > self.theta:
            return int(np.sign(trend))
        return 0


def build_trend_population(n: int, rng: np.random.Generator) -> list[TrendAgent]:
    """ヘテロな Model T 集団を生成(param は `rng` から決定的に引く)。"""
    horizons = rng.integers(H_MIN, H_MAX + 1, size=n)
    thetas = rng.uniform(THETA_MIN, THETA_MAX, size=n)
    return [TrendAgent(int(h), float(t)) for h, t in zip(horizons, thetas, strict=True)]
