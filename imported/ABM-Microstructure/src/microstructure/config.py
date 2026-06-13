"""SimConfig — 不変の run パラメータ（spec FR / data-model 参照）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SimConfig:
    # 実行
    n_periods: int            # sim ステップ数
    seed: int                 # 単一 RNG seed (D7)
    dt: float = 1e-2          # 時間解像度。jump 確率 lambda_jump*dt 等。dt->0 で連続時間極限 (D6)
    # 価格過程（連続時間パラメータ）
    sigma: float = 0.0        # diffusion vol（baseline は 0、jump 駆動）
    lambda_jump: float = 5.0  # jump 強度（単位時間あたり）
    jump_size: float = 1.0    # J
    initial_price: float = 100.0
    # 機構
    mechanism: Literal["continuous", "batch"] = "continuous"
    batch_interval: int = 1   # N（continuous では無視）
    # フロー
    alpha: float = 0.3        # taker が arbitrageur(=informed) である確率
    noise_rate: float = 1.0   # noise 到着強度（単位時間あたり）
    # MM 行動
    half_spread: float = 0.1  # MM が出す half-spread h（competitive_spread はこれを scan して測る）
    # economics
    fee: float = 0.0          # maker が fill ごとに得る fee（>0）
    opp_cost: float = 0.0     # c: 機会コスト（単位時間あたり）＝退出閾値 (US3)
    # 許容（統計 consistency。flat rel tolerance は持たない＝「緩い方」廃止, D6）
    se_mult: float = 4.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError("alpha must be in [0,1]")
        if self.dt <= 0:
            raise ValueError("dt must be > 0")
        if not (0.0 <= self.lambda_jump * self.dt <= 1.0):
            raise ValueError("lambda_jump*dt must be in [0,1] (refine dt)")
        if not (0.0 <= self.noise_rate * self.dt <= 1.0):
            raise ValueError("noise_rate*dt must be in [0,1] (refine dt)")
        if self.batch_interval < 1:
            raise ValueError("batch_interval >= 1")
        if self.sigma < 0:
            raise ValueError("sigma >= 0")

    @property
    def horizon(self) -> float:
        """連続時間の総時間 T = n_periods * dt。"""
        return self.n_periods * self.dt
