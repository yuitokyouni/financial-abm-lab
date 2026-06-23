"""ZIAgent: Zero-Intelligence LIMIT poster。warmup 用 + ZI-naïve control。

spec 003 §3.4 (ZI warmup) + §4 (ZI-naïve baseline)。

評価値 v_i:
  - mode="naive":     v = mid * (1 + eps),   eps ~ N(0, sigma_eval)
    (Smith-Farmer-Gillemot-Krishnamurthy 2003 ZI に近い)。
  - mode="matched":   v_t = v_{t-1} + delta_t,  delta_t ~ N(mu_match, sigma_match)
    (Kronos の評価値増分の 1 次・2 次モーメントを matching する、P1 で実装)。

P0 では mode="naive" のみ。matched は P1 で zi_matched_agent.py に分離 or 拡張。

side / price:
  - side: rng で 50/50 で buy or sell
  - margin: margin_i ~ U(margin_min, margin_max)
  - price = v * (1 ∓ margin)  (buy なら 1-margin、sell なら 1+margin)

aggressive rate 制御は §3.1 の auto-tune (P1.5) で margin 分布を動かす。
"""
from __future__ import annotations

from typing import Any, Dict, List

from pams.market import Market

from .base_agent import AgentEvaluation, LimitAgentBase


class ZIAgent(LimitAgentBase):
    """Zero-Intelligence LIMIT poster (mid 周辺に random walk 評価値で指値)。"""

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.zi_mode: str = str(settings.get("ziMode", "naive"))  # "naive" or "matched"
        self.sigma_eval: float = float(settings.get("sigmaEval", 0.005))
        # matched 用 (P1 で使う)。sigmaMatch 未指定なら sigmaEval を流用 (構成統一)。
        self.mu_match: float = float(settings.get("muMatch", 0.0))
        self.sigma_match: float = float(settings.get("sigmaMatch", self.sigma_eval))
        # margin
        self.margin_min: float = float(settings.get("marginMin", 0.001))
        self.margin_max: float = float(settings.get("marginMax", 0.01))
        # state for matched random walk
        self._last_v: float | None = None

    def _evaluate(self, market: Market, bar_index: int) -> AgentEvaluation:
        mid = market.get_mid_price()
        if mid is None or mid <= 0:
            # 板が片側空 or 初期化前 → market_price で fallback
            mp = market.get_market_price()
            if mp is None or mp <= 0:
                return AgentEvaluation(side=0)
            mid = float(mp)
        else:
            mid = float(mid)

        if self.zi_mode == "naive":
            eps = self.prng.gauss(0.0, self.sigma_eval)
            v = mid * (1.0 + eps)
        elif self.zi_mode == "matched":
            # AR(1) で random walk: v_t = v_{t-1} + delta
            if self._last_v is None:
                self._last_v = mid
            delta = self.prng.gauss(self.mu_match, self.sigma_match)
            v = self._last_v + delta * mid  # delta は相対変化として扱う
            self._last_v = v
        else:
            raise ValueError(f"unknown zi_mode: {self.zi_mode!r}")

        # side: buy/sell を 50/50
        side = 1 if self.prng.random() < 0.5 else -1
        # margin
        margin = self.prng.uniform(self.margin_min, self.margin_max)
        if side > 0:
            price = v * (1.0 - margin)
        else:
            price = v * (1.0 + margin)

        if price <= 0:
            return AgentEvaluation(side=0)
        return AgentEvaluation(
            side=side, price=price, volume=self.order_volume,
            log_payload={"v": v, "margin": margin, "mid": mid},
        )
