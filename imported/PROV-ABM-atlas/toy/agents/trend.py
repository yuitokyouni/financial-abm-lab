"""trend — Model T(Chiarella-Iori 型、原典: Chiarella-Iori-Perelló 2009)。

chartist + fundamentalist + noise の混合(chartist 優勢)。各成分は観測ベクトルから内部で
信号を計算する(B2 ≠ A、spec §3.2):

- **chartist**: 価格 return 履歴を読み、正規化トレンド `mean(r)/std(r)` を計算。
- **fundamentalist**: 誤価格系列 `m=log(p*/p)`(雑音つき観測 §3.1)を読み平均回帰。
- **noise**: 一様ランダム行動(自走の素 — 純決定論の死んだ不動点を回避)。

noise 成分があるため、初期の平坦市場から自力で立ち上がる(v0.2 自作 T の死活問題を解消)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from provabm.ctx import Ctx

from toy.agents.base import Agent
from toy.observation import FUNDAMENTAL, PRICE_RETURNS

# spec §3.2 の free parameter(calibration target)。デフォルトは自走 + SF を出す目安。
ALPHA = (0.5, 0.3, 0.2)  # (chartist, fundamentalist, noise) 母集団比率
H_MIN, H_MAX = 5, 50  # 観測 horizon
THETA_C_MIN, THETA_C_MAX = 0.5, 2.0  # chartist 発火閾値(正規化トレンド)
THETA_F_MIN, THETA_F_MAX = 0.0, 0.01  # fundamentalist 発火閾値(誤価格 = log 比)


class TComponent(StrEnum):
    CHARTIST = "chartist"
    FUNDAMENTALIST = "fundamentalist"
    NOISE = "noise"


@dataclass(slots=True)
class TrendAgent(Agent):
    """Chiarella-Iori 型の 1 成分エージェント。"""

    component: TComponent
    horizon: int
    theta: float

    def decide(self, ctx: Ctx) -> int:
        if self.component is TComponent.NOISE:
            # 一様ランダム {-1,0,+1}(自走の素)。乱数は ctx 経由(honest・再現可能)。
            return int(ctx.random("noise") * 3) - 1

        if self.component is TComponent.CHARTIST:
            window = ctx.observe(PRICE_RETURNS)[-self.horizon :]
            sd = float(window.std())
            if sd == 0.0:
                return 0
            signal = float(window.mean()) / sd  # 正規化トレンド
        else:  # FUNDAMENTALIST
            window = ctx.observe(FUNDAMENTAL)[-self.horizon :]
            signal = float(window.mean())  # 平均誤価格(>0 = 割安 → 買い)

        if abs(signal) > self.theta:
            return int(np.sign(signal))
        return 0


def build_trend_population(
    n: int, rng: np.random.Generator, alpha: tuple[float, float, float] | None = None
) -> list[TrendAgent]:
    """Chiarella-Iori 型集団を生成(成分割当・horizon・閾値を rng から決定的に引く)。

    `alpha`(chartist, fundamentalist, noise 比率)を渡すと既定 ALPHA を上書き(calibration 用)。
    """
    p = np.asarray(alpha if alpha is not None else ALPHA, dtype=np.float64)
    p = p / p.sum()  # 丸め誤差で sum≠1 になっても正規化(choice は厳密な 1.0 を要求)
    components = rng.choice(
        [TComponent.CHARTIST, TComponent.FUNDAMENTALIST, TComponent.NOISE],
        size=n,
        p=p,
    )
    horizons = rng.integers(H_MIN, H_MAX + 1, size=n)
    agents: list[TrendAgent] = []
    for comp, h in zip(components, horizons, strict=True):
        if comp == TComponent.CHARTIST:
            theta = float(rng.uniform(THETA_C_MIN, THETA_C_MAX))
        elif comp == TComponent.FUNDAMENTALIST:
            theta = float(rng.uniform(THETA_F_MIN, THETA_F_MAX))
        else:
            theta = 0.0
        agents.append(TrendAgent(TComponent(comp), int(h), theta))
    return agents
