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
        self._closes_sorted = None  # np.ndarray (n_samples,) or None
        self._last_history_len: int = 0
        self._call_log: list[tuple[int, float, int]] = []  # (bar_index, dt, n_samples)

    def ensure_current(self, market: Market) -> Optional["np.ndarray"]:
        time = market.get_time()
        bar_index = time // self.bar_size
        # bar の OHLCV 履歴
        history = build_ohlcv_from_market(
            market, bar_size=self.bar_size, start_step=0, end_step=time + 1,
            price_source="market",
        )
        n_bars_now = len(history)
        if n_bars_now < self.lookback_bars:
            return None  # lookback 不足
        # 同 bar 内では再利用
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
            self._closes_sorted = closes_sorted
            self._current_bar = bar_index
            self._call_log.append((bar_index, float(self.predictor.last_call_dt),
                                   int(closes_sorted.size)))
            return closes_sorted

    def get_eval_for_rank(self, agent_rank: float, closes_sorted) -> float:
        return quantile_to_eval(closes_sorted, agent_rank)

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
        # hub は SelfOrganizedBookMarket._inject_hub から差し込まれる
        self.kronos_hub: Optional[KronosQuantileHub] = None

    def _evaluate(self, market: Market, bar_index: int) -> AgentEvaluation:
        if self.kronos_hub is None:
            return AgentEvaluation(side=0)  # hub 未注入 (warmup session 中)
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
            return AgentEvaluation(side=0)  # lookback 不足

        v = self.kronos_hub.get_eval_for_rank(self.agent_rank, closes_sorted)
        if not (v > 0):
            return AgentEvaluation(side=0)
        # 方向: v > mid なら buy、< mid なら sell
        side = 1 if v > mid else (-1 if v < mid else 0)
        if side == 0:
            return AgentEvaluation(side=0)
        margin = self.prng.uniform(self.margin_min, self.margin_max)
        price = v * (1.0 - margin) if side > 0 else v * (1.0 + margin)
        if price <= 0:
            return AgentEvaluation(side=0)
        return AgentEvaluation(
            side=side, price=price, volume=self.order_volume,
            log_payload={"v": v, "mid": mid, "margin": margin, "rank": self.agent_rank},
        )
