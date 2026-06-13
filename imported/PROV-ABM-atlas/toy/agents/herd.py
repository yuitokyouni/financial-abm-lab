"""herd — Model H(群れ、閾値つき herding。原典: Granovetter 1978 threshold model、
herding 系譜として Kirman 1993 / Lux-Marchesi 1999 / Alfarano-Lux-Wagner 2008 を参考)。

T と土台を揃え、speculative 成分だけ trend→herd に変えた混合: fundamentalist(錨)+ herder
(他者の集約行動を読む)+ noise(自走)。

**閾値(間欠性)= H の clustering の素**(2026-06-13 確定、Issue #11): herder は集約 consensus が
**閾値 θ_h を超えた時だけ**多数派に同調し、弱い consensus では不活性(action=0)。この off 状態が
「consensus 強→一斉発火(高ボラ)/弱→静穏(低ボラ)」の間欠を生み volatility clustering になる。
閾値なし常時発火だと relaxation 振動になり SF が出ない(持続 Kirman/ALW 機構は超過需要 drift
chassis と非互換のため、Granovetter 流の閾値 herding を採用。詳細 Issue #11)。

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
THETA_H_MIN, THETA_H_MAX = 0.05, 0.25  # herder consensus 閾値(間欠性。0 で常時発火=旧挙動)


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
            m = float(social.mean())
            # 閾値(間欠性): consensus が強い時だけ多数派に同調、弱ければ不活性。
            if abs(m) > self.theta:
                return int(np.sign(m))
            return 0

        # FUNDAMENTALIST(錨)
        window = ctx.observe(FUNDAMENTAL)[-self.horizon :]
        signal = float(window.mean())
        if abs(signal) > self.theta:
            return int(np.sign(signal))
        return 0


def build_herd_population(
    n: int,
    rng: np.random.Generator,
    beta: tuple[float, float, float] | None = None,
    hs_range: tuple[int, int] | None = None,
    theta_h_range: tuple[float, float] | None = None,
) -> list[HerdAgent]:
    """閾値つき herding 集団を生成。

    `beta`(herder, fundamentalist, noise 比率)・`hs_range`(horizon レンジ)・
    `theta_h_range`(herder consensus 閾値レンジ)を渡すと既定を上書き(calibration 用)。
    `theta_h_range=None` では herder 閾値 = 0(常時発火=旧挙動、後方互換)。
    """
    p = np.asarray(beta if beta is not None else ALPHA, dtype=np.float64)
    p = p / p.sum()  # 丸め誤差で sum≠1 になっても正規化(choice は厳密な 1.0 を要求)
    components = rng.choice(
        [HComponent.HERDER, HComponent.FUNDAMENTALIST, HComponent.NOISE],
        size=n,
        p=p,
    )
    h_lo, h_hi = hs_range if hs_range is not None else (HS_MIN, HS_MAX)
    horizons = rng.integers(h_lo, h_hi + 1, size=n)
    th_lo, th_hi = theta_h_range if theta_h_range is not None else (0.0, 0.0)
    agents: list[HerdAgent] = []
    for comp, h in zip(components, horizons, strict=True):
        if comp == HComponent.FUNDAMENTALIST:
            theta = float(rng.uniform(THETA_F_MIN, THETA_F_MAX))
        elif comp == HComponent.HERDER:
            theta = float(rng.uniform(th_lo, th_hi))  # consensus 閾値(間欠性)
        else:
            theta = 0.0
        agents.append(HerdAgent(HComponent(comp), int(h), theta))
    return agents
