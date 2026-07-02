"""KronosCIAgent: spec 003 §3.6 — agent ごとに別 quantile を評価値にする LIMIT 投稿 agent。

- 1 bar に 1 回、共有 hub が KronosQuantilePredictor.predict_quantile_closes(history) で
  n_samples 個の close サンプルを取り出し、昇順 sort で保持。
- 各 agent は自分の agent_rank ∈ [0, 1] (= 全 KronosCIAgent の agent_id を 0..1 に正規化)
  に対応する quantile を評価値 v_i として使う。
- 方向 side = sign(v_i − mid)、price = v_i × (1 ∓ margin_i)。spec 003 §3.1 の marketability
  内生 (= bounce 構造的消失) はそのまま継承。

これにより:
  (1) 配置層に Kronos 由来の自然な分散が入る (人工 offset 不要)。
  (2) Kronos の「分布幅自体の予測力」を ZI-matched との比較で測れる。
  (3) §10-4 batching: 1 hub × 1 predict で全 agent 分の quantile が揃う。
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import pandas as pd
from pams.market import Market

from ..kronos_lob.bar_aggregator import build_ohlcv_from_market
from .base_agent import AgentEvaluation, LimitAgentBase
from .kronos_quantile import KronosQuantilePredictor, quantile_to_eval


class KronosQuantileHub:
    """全 KronosCIAgent が共有する quantile 評価値 cache。

    bar_index が変わったら 1 回 predict_quantile_closes を呼び、N quantile を sort して保持。
    各 agent は `get_eval_for_rank(agent_rank)` で線形補間 quantile を引く。
    """

    def __init__(self, predictor: KronosQuantilePredictor, bar_size: int, lookback_bars: int):
        self.predictor = predictor
        self.bar_size = bar_size
        self.lookback_bars = lookback_bars
        self._lock = threading.Lock()
        self._current_bar: int = -1
        self._closes_sorted = None  # 現 bar の予測 quantile (= bar t-1 で予想した bar t の中心列)
        self._prev_closes_sorted = None  # 前 bar の予測 quantile (= bar t-2 で予想した bar t-1 = arbitrageur 用 X_t)
        self._last_history_len: int = 0
        self._call_log: list[tuple[int, float, int]] = []

    def ensure_current(self, market: Market) -> Optional["np.ndarray"]:
        time = market.get_time()
        bar_index = time // self.bar_size
        history = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=time + 1,
            price_source="market",
        )
        n_bars_now = len(history)
        if n_bars_now < self.lookback_bars:
            return None
        with self._lock:
            if bar_index == self._current_bar and self._closes_sorted is not None:
                return self._closes_sorted
            x_df = history.iloc[-self.lookback_bars:][
                ["open", "high", "low", "close", "volume", "amount"]
            ].reset_index(drop=True)
            x_ts = pd.Series(history["timestamps"].iloc[-self.lookback_bars:].to_list())
            last_ts = pd.Timestamp(history["timestamps"].iloc[-1])
            dt_step = last_ts - pd.Timestamp(history["timestamps"].iloc[-2])
            y_ts = pd.Series([last_ts + dt_step])
            closes_sorted = self.predictor.predict_quantile_closes(x_df, x_ts, y_ts)
            # bar 更新時に「前 bar の予想」を保存 (§3.7 arbitrageur 用)
            self._prev_closes_sorted = self._closes_sorted
            self._closes_sorted = closes_sorted
            self._current_bar = bar_index
            self._call_log.append((bar_index, float(self.predictor.last_call_dt),
                                   int(closes_sorted.size)))
            return closes_sorted

    def get_eval_for_rank(self, agent_rank: float, closes_sorted) -> float:
        return quantile_to_eval(closes_sorted, agent_rank)

    def get_prev_eval_for_rank(self, agent_rank: float) -> Optional[float]:
        """§3.7 arbitrageur 用: 前 bar の予想 quantile (= 直前予想 X_t)。

        bar t-1 で `closes_sorted` (bar t の予想) を計算した直後 ensure_current が呼ばれると、
        その時点の self._closes_sorted が次 bar (= bar t での) ensure_current で
        self._prev_closes_sorted に押し出される。よって arbitrageur が bar t で
        get_prev_eval_for_rank() を呼ぶと「bar t-1 終了時に予想した bar t の中心」が取れる。
        """
        if self._prev_closes_sorted is None:
            return None
        return quantile_to_eval(self._prev_closes_sorted, agent_rank)

    @property
    def call_log(self) -> list[tuple[int, float, int]]:
        return list(self._call_log)


class KronosCIAgent(LimitAgentBase):
    """spec 003 §3.6 quantile-rank 評価値の LIMIT-posting agent。

    Settings:
        agentRank ∈ [0, 1]: 自分が分布のどの quantile を読むか。
            (省略時は agent_id を全 Kronos agent 数で正規化、ただし全 agent 数を agent 側で
            知る術が無いので、build_lob_config 側で各 agent に明示渡しする。)
        marginMin / marginMax: 価格 = v × (1 ∓ margin)、U(min, max) サンプル。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.agent_rank: float = float(settings.get("agentRank", 0.5))
        self.margin_min: float = float(settings.get("marginMin", 3e-5))
        self.margin_max: float = float(settings.get("marginMax", 1e-4))
        # §3.7 arb_mode (round5 fix):
        #   False = chase (default, 旧 §3.6): v = 現 quantile, side = sign(v - mid)
        #     → Kronos 予測方向に賭ける = drift で全員同方向に振れる degeneracy
        #   True  = arbitrageur (新 §3.7): v = prev_quantile (= 直前予想 X_t),
        #     side = sign(X_t - mid) = sign(X_t - P_t) → P_t > X_t で売り、< X_t で買い。
        #     直前予想からの乖離を fade することで集合 over-shoot に逆らう復元力。
        self.arb_mode: bool = bool(settings.get("arbMode", False))
        self.kronos_hub: Optional[KronosQuantileHub] = None

    def _evaluate(self, market: Market, bar_index: int) -> AgentEvaluation:
        if self.kronos_hub is None:
            return AgentEvaluation(side=0)
        mid = market.get_mid_price()
        if mid is None or mid <= 0:
            mp = market.get_market_price()
            if mp is None or mp <= 0:
                return AgentEvaluation(side=0)
            mid = float(mp)
        else:
            mid = float(mid)

        closes_sorted = self.kronos_hub.ensure_current(market)
        if closes_sorted is None:
            return AgentEvaluation(side=0)

        if self.arb_mode:
            # §3.7: v = 直前予想 X_t、 side = sign(X_t - P_t)
            v = self.kronos_hub.get_prev_eval_for_rank(self.agent_rank)
            if v is None or not (v > 0):
                return AgentEvaluation(side=0)  # 最初の bar は prev 無し
        else:
            v = self.kronos_hub.get_eval_for_rank(self.agent_rank, closes_sorted)
            if not (v > 0):
                return AgentEvaluation(side=0)

        side = 1 if v > mid else (-1 if v < mid else 0)
        if side == 0:
            return AgentEvaluation(side=0)
        margin = self.prng.uniform(self.margin_min, self.margin_max)
        price = v * (1.0 - margin) if side > 0 else v * (1.0 + margin)
        if price <= 0:
            return AgentEvaluation(side=0)
        return AgentEvaluation(
            side=side, price=price, volume=self.order_volume,
            log_payload={"v": v, "mid": mid, "margin": margin,
                         "rank": self.agent_rank, "arb_mode": self.arb_mode},
        )
