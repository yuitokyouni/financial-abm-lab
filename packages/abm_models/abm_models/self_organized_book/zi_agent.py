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

import random
from typing import Any, Dict, List, Optional

from pams.market import Market

from .base_agent import AgentEvaluation, LimitAgentBase


class SharedAR1Hub:
    """P3-D 対照 (spec 003 §4 拡張): 全 shared_ar1 ZI が共有する bar 単位 AR(1) 共通因子。

    P3 の matched_ar1 (agent ごと独立 AR1) との構造差を 1 変数ずつ埋めるための hub:
      - S2 (横断相関): deviation d_t を全 agent で共有 (hub が bar ごとに 1 回だけ更新)。
        各 agent は rank offset だけ違う値 v_i = center_t + W·(2·rank_i − 1) を読む
        (Kronos の quantile-rank 読み分けの線形 band 版)。
      - S3 (係留先): anchor_smooth_bars=0 なら現在 mid に係留 (= matched_ar1 と同じ、
        D1: S2 のみの差分)。k>0 なら直近 k 完結 bar close (market price) の SMA に係留
        (= Kronos の lookback 履歴予測の慣性 proxy、D2: S2+S3)。

    更新式 (bar ごと 1 回、hub 専用 RNG):
        d_t = φ·d_{t-1} + ε_t,  ε_t ~ N(mu, sigma)
        center_t = anchor_t + d_t
    """

    def __init__(
        self,
        *,
        phi: float,
        sigma: float,
        mu: float = 0.0,
        band_halfwidth: float = 0.0,
        bar_size: int = 10,
        anchor_smooth_bars: int = 0,
        seed: int = 0,
    ):
        self.phi = float(phi)
        self.sigma = float(sigma)
        self.mu = float(mu)
        self.band = float(band_halfwidth)
        self.bar_size = int(bar_size)
        self.anchor_smooth_bars = int(anchor_smooth_bars)
        self.prng = random.Random(seed)
        self._d: float = 0.0
        self._current_bar: int = -1
        self._center: Optional[float] = None
        self._log: list[tuple[int, float, float, float]] = []  # (bar, anchor, d, center)

    def _sma_anchor(self, market: Market, bar_index: int) -> Optional[float]:
        """直近 anchor_smooth_bars 完結 bar の close (market price) の平均。"""
        k = self.anchor_smooth_bars
        closes: list[float] = []
        for b in range(max(0, bar_index - k), bar_index):
            t_close = (b + 1) * self.bar_size - 1
            p = market.get_market_price(t_close)
            if p is not None and p > 0:
                closes.append(float(p))
        if not closes:
            return None
        return sum(closes) / len(closes)

    def ensure_current(self, market: Market, mid: float) -> Optional[float]:
        """現 bar の共有 center を返す。bar が進んでいたら AR(1) を 1 step 進める。

        mid は呼び出し agent の評価時 mid (anchor_smooth_bars=0 のときの係留先、
        および SMA が取れない初期 bar の fallback)。bar 内では最初に評価した agent の
        mid で center が固定される (= Kronos hub と同じ「bar 内固定」cadence)。
        """
        bar_index = market.get_time() // self.bar_size
        if bar_index == self._current_bar:
            return self._center
        anchor: Optional[float] = None
        if self.anchor_smooth_bars > 0:
            anchor = self._sma_anchor(market, bar_index)
        if anchor is None:
            anchor = float(mid)
        eps = self.prng.gauss(self.mu, self.sigma)
        self._d = self.phi * self._d + eps
        self._center = anchor + self._d
        self._current_bar = bar_index
        self._log.append((bar_index, anchor, self._d, self._center))
        return self._center

    def get_eval_for_rank(self, agent_rank: float) -> Optional[float]:
        if self._center is None:
            return None
        return self._center + self.band * (2.0 * float(agent_rank) - 1.0)

    @property
    def log(self) -> list[tuple[int, float, float, float]]:
        return list(self._log)


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
        # P2 実測 default: φ=0.615, σ=3.81e-3 (absolute on mid scale ≈ 300、
        # first-entry pairing 修正規約 = spec 003 §12 round6 追記。旧 0.418/6e-3 は
        # last-wins pairing の bar 内 drift 汚染値)
        self.phi_ar1: float = float(settings.get("phiAr1", 0.615))
        self.sigma_ar1_abs: float = float(settings.get("sigmaAr1Abs", 3.81e-3))
        self.mu_ar1: float = float(settings.get("muAr1", 0.0))
        # AR(1) state (= 前 bar の v_t - mid_t) と現 bar のキャッシュ
        # spec 003 §3.3 の bar/step 2 階層: 評価値は bar 単位で更新、step 単位は TTL/再貼り。
        self._last_v_minus_mid: float | None = None
        self._cached_bar_index: int = -1
        self._cached_v: float | None = None
        # shared_ar1 用 (P3-D): model.run() が注入する共有 hub と rank。
        self.shared_hub: SharedAR1Hub | None = None
        self.agent_rank: float = float(settings.get("agentRank", 0.5))
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
                # P2 実測 default φ=0.615, σ=3.81e-3 (absolute) で Kronos と dose-match。
                if self._last_v_minus_mid is None:
                    self._last_v_minus_mid = 0.0
                eps = self.prng.gauss(self.mu_ar1, self.sigma_ar1_abs)
                v_minus_mid = self.phi_ar1 * self._last_v_minus_mid + eps
                self._last_v_minus_mid = v_minus_mid
                v = mid + v_minus_mid
            elif self.zi_mode == "shared_ar1":
                # P3-D: 共有 AR(1) 共通因子 hub から rank offset 付きで読む。
                # matched_ar1 との差は deviation の共有 (S2) と anchor (S3, hub 設定) のみ。
                if self.shared_hub is None:
                    return AgentEvaluation(side=0)
                center = self.shared_hub.ensure_current(market, mid)
                if center is None or not (center > 0):
                    return AgentEvaluation(side=0)
                v = self.shared_hub.get_eval_for_rank(self.agent_rank)
                if v is None or not (v > 0):
                    return AgentEvaluation(side=0)
            else:
                raise ValueError(f"unknown zi_mode: {self.zi_mode!r}")
            self._cached_bar_index = bar_index
            self._cached_v = v

        # side は v-mid 由来 (Kronos と同じ意思決定式で dose-match を公平に保つ、spec 003 §4)。
        # 設計判断 (spec 003 §3.3 の 2 階層): 「評価値 v = bar 固定」だが side は step ごとに
        # 現 mid と比較して導出する = 固定した私的評価額 v の周りで指値を出す trader は、
        # 価格が v を跨げば自然に反対側の板に立つ (Chiarella 型 LOB の需要関数と同じ扱い)。
        # bar 内 side flip は全条件 (kronos/matched/shared/E) に共通の substrate 特性であり、
        # 条件間比較 (P3/P3-D/E/F) では差分として消える。bounce の駆動源でないことは
        # D1 条件 (同じ step 再計算下で ret_acf[1]≈−0.04) が反例として実証済み。
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
