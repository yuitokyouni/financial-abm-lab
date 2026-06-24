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
        self.zi_mode: str = str(settings.get("ziMode", "naive"))
        self.sigma_eval: float = float(settings.get("sigmaEval", 0.005))
        # matched (independent sample, P1 暫定版)
        self.mu_match: float = float(settings.get("muMatch", 0.0))
        self.sigma_match: float = float(settings.get("sigmaMatch", self.sigma_eval))
        # matched_ar1 用 (P3, spec 003 §4 + 裁定 A): v_t - mid = φ(v_{t-1}-mid) + ε
        # P2 実測 default: φ=0.418, σ=6e-3 (absolute on mid scale ≈ 300)
        self.phi_ar1: float = float(settings.get("phiAr1", 0.418))
        self.sigma_ar1_abs: float = float(settings.get("sigmaAr1Abs", 6e-3))
        self.mu_ar1: float = float(settings.get("muAr1", 0.0))
        # AR(1) state (= 前 bar の v_t - mid_t) と現 bar のキャッシュ
        # spec 003 §3.3 の bar/step 2 階層: 評価値は bar 単位で更新、step 単位は TTL/再貼り。
        self._last_v_minus_mid: float | None = None
        self._cached_bar_index: int = -1
        self._cached_v: float | None = None
        # margin
        self.margin_min: float = float(settings.get("marginMin", 0.001))
        self.margin_max: float = float(settings.get("marginMax", 0.01))
        # state for matched random walk (legacy, used by zi_mode="matched")
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

        # 評価値 v は bar 単位で更新 (spec 003 §3.3 の 2 階層)。同 bar 内では再利用。
        if bar_index == self._cached_bar_index and self._cached_v is not None:
            v = self._cached_v
        else:
            if self.zi_mode == "naive":
                eps = self.prng.gauss(0.0, self.sigma_eval)
                v = mid * (1.0 + eps)
            elif self.zi_mode == "matched":
                # P1 暫定版: independent sample (Kronos 投入前)。
                eps = self.prng.gauss(self.mu_match, self.sigma_match)
                v = mid * (1.0 + eps)
            elif self.zi_mode == "matched_ar1":
                # P3 (spec 003 §4 + 裁定 A): v_t - mid_t = φ (v_{t-1} - mid_{t-1}) + ε
                # ε ~ N(mu_ar1, sigma_ar1_abs)。φ<1 で mid 周辺に mean-revert。
                # P2 実測 default φ=0.418, σ=6e-3 (absolute) で Kronos と dose-match。
                if self._last_v_minus_mid is None:
                    self._last_v_minus_mid = 0.0
                eps = self.prng.gauss(self.mu_ar1, self.sigma_ar1_abs)
                v_minus_mid = self.phi_ar1 * self._last_v_minus_mid + eps
                self._last_v_minus_mid = v_minus_mid
                v = mid + v_minus_mid
            else:
                raise ValueError(f"unknown zi_mode: {self.zi_mode!r}")
            self._cached_bar_index = bar_index
            self._cached_v = v

        # side は v-mid 由来 (Kronos と同じ意思決定式で dose-match を公平に保つ、spec 003 §4)
        # 旧版 (50/50 random side) は P1 naive では成立したが、matched_ar1 では v が mid 周辺に
        # 集中して半分の agent が「反対方向 + margin」で実質クロスしない degeneracy に陥った。
        if v > mid:
            side = 1
        elif v < mid:
            side = -1
        else:
            return AgentEvaluation(side=0)
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
