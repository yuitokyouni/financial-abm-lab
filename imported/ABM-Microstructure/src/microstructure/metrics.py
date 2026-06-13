"""run の集計メトリクス（spec Key Entities / data-model）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Metrics:
    extraction: float          # arbitrageur 累積 PnL = MM 犠牲（ゼロサム）
    noise_pnl: float           # MM が noise から得た spread 収入
    mm_trading_pnl: float      # noise_pnl - extraction（fee 抜きの取引損益）
    fees: float                # MM の fee 収入（maker, fill ごと f）
    mm_net_pnl: float          # mm_trading_pnl + fees（会計補助）
    participation_margin: float  # mm_net_pnl - opp_cost*T（US3, D9）
    mm_exits: bool             # participation_margin < 0
    effective_spread: float    # noise の平均実効スプレッド（full = 2h）
    informed_impact: float     # 診断用: informed fill あたり平均 |Δp|（σ=0 では構成上 ≈J。検証には使わない）
    price_impact: float        # identity-blind flow 回帰 λ̂ = Σx·Δp/Σx²（impact 層, anchor=kyle_lambda, D5b v2）
    n_noise: int
    n_arb: int

    @property
    def n_trades(self) -> int:
        return self.n_noise + self.n_arb
