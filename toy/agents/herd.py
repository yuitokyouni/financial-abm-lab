"""herd — Model H(群れ、原典: Kirman 1993 / Lux-Marchesi 1999 / Alfarano-Lux-Wagner 2008)。

T と土台を揃え、speculative 成分だけ trend→herd に変えた混合: fundamentalist(錨)+ herder
(他者の集約行動をコピー)+ noise(自走)。fundamentalist がファンダに引き戻すことで価格は
有界になり、herder が opinion を溜める → たまに大きく振れる(fat tails / ボラ集中)。純 herding
(錨なし)は単調暴走して SF が出ないため、原典(ALW は fundamentalist 錨を持つ)に忠実な形にする。

機構の差(T vs H): speculative 成分が読む観測が、価格トレンド(T)か他者の行動(H)か。
→ trend masking は T を、social masking は H を叩く(spec §7.2)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from provabm.ctx import Ctx

from toy.agents.base import Agent
from toy.observation import AGG_ACTION, FUNDAMENTAL

# spec §3.2 の free parameter(calibration target)。T と対称(speculative 成分のみ差し替え)。
ALPHA = (0.5, 0.3, 0.2)  # (herder, fundamentalist, noise) 母集団比率
HS_MIN, HS_MAX = 5, 50  # 観測 horizon
THETA_F_MIN, THETA_F_MAX = 0.0, 0.01  # fundamentalist 発火閾値(誤価格)


class HComponent(StrEnum):
    HERDER = "herder"
    FUNDAMENTALIST = "fundamentalist"
    NOISE = "noise"


@dataclass(slots=True)
class HerdAgent(Agent):
    """Kirman/Lux-Marchesi 型の 1 成分エージェント。"""

    component: HComponent
    horizon: int
    theta: float

    def decide(self, ctx: Ctx) -> int:
        if self.component is HComponent.NOISE:
            return int(ctx.random("noise") * 3) - 1

        if self.component is HComponent.HERDER:
            social = ctx.observe(AGG_ACTION)[-self.horizon :]
            return int(np.sign(float(social.mean())))  # 多数派に同調(他者をコピー)

        # FUNDAMENTALIST(錨)
        window = ctx.observe(FUNDAMENTAL)[-self.horizon :]
        signal = float(window.mean())
        if abs(signal) > self.theta:
            return int(np.sign(signal))
        return 0


def build_herd_population(n: int, rng: np.random.Generator) -> list[HerdAgent]:
    """Kirman/Lux-Marchesi 型集団を生成。"""
    components = rng.choice(
        [HComponent.HERDER, HComponent.FUNDAMENTALIST, HComponent.NOISE],
        size=n,
        p=list(ALPHA),
    )
    horizons = rng.integers(HS_MIN, HS_MAX + 1, size=n)
    agents: list[HerdAgent] = []
    for comp, h in zip(components, horizons, strict=True):
        theta = (
            float(rng.uniform(THETA_F_MIN, THETA_F_MAX))
            if comp == HComponent.FUNDAMENTALIST
            else 0.0
        )
        agents.append(HerdAgent(HComponent(comp), int(h), theta))
    return agents
