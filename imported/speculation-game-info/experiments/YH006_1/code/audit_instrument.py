"""Claim-2 execution-layer audit — step0/step1 instrumentation.

Phase-1 code is NOT touched (monkey-patch 禁止, Brief §4.4). All observation is
a pure subclass + a PAMS Logger, following the established WInitLogging /
QConst / LifetimeCap subclass pattern (sg_agent.py).

Three INDEPENDENT logs:
  L1 (agent-side, self.l1_records): reconcile 前/後 の
      口座A(実在庫 asset_volumes + cash) と 口座B(SG 内部状態).
      claim-2 の残差 a/b は L1 単独で閉じる (audit_residuals.judge) —
      L2/L3 の実装の正しさに一切依存しない (硬い制約).
  L2 (logger-side, AuditLogger.executions): 約定ごと (t, buy_id, sell_id, qty, price) → #4.
  L3 (logger-side, AuditLogger.market_steps): step ごと mid/best bid/ask/depth → #1, step2(iii).

なぜ関数分割が要らないか: PAMS では matching(口座A変異) は Runner の execution
phase、reconcile(口座B反映) は次 step の agent メソッド冒頭 (speculation_agent.py:8)。
両者は Runner ループで構造分離済で、`submit_orders_by_market` 実行中 asset_volumes は
凍結。よって super() を wrap するだけで reconcile 前(super前)/後(super後)の2時点が取れる。
唯一のトラップ = stale-fill recovery が _reconcile の前に early-return する点は、
メソッド全体を wrap することで両 exit path を漏れなく捕捉して回避している。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Phase 1 の subclass 群 (WInitLogging を継承して w_init logging を保存)
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sg_agent import WInitLoggingSpeculationAgent  # noqa: E402

from pams.logs.base import Logger  # noqa: E402
from pams.market import Market  # noqa: E402
from pams.order import Cancel, Order  # noqa: E402


class InstrumentedSpeculationAgent(WInitLoggingSpeculationAgent):
    """submit_orders_by_market を wrap し L1(口座A 2時点 + 口座B pre/post)を記録.

    default 挙動は親と bit-一致 (super() をそのまま呼ぶだけ、判断ロジックに介入しない)。
    """

    def setup(self, settings, accessible_markets_ids, *args, **kwargs) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.l1_records: List[Dict[str, Any]] = []
        self._prev_av: Dict[int, int] = {}

    def _snap(self) -> tuple:
        # 口座B の内部状態スナップショット (pending は str/None)
        return (
            int(self.position),
            int(self.entry_quantity),
            int(self.entry_action),
            int(self.entry_price_cog),
            int(self.entry_step),
            self.pending_intent if self.pending_intent is not None else "none",
        )

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        mid = int(market.market_id)
        t = int(market.get_time())
        # --- reconcile 前 (口座A 真実: asset_volumes は本メソッド中 凍結) ---
        av_pre = int(self.asset_volumes.get(mid, 0))
        cash_pre = float(self.cash_amount)
        pre = self._snap()
        n_act = len(self.action_log)
        n_rt = len(self.round_trips)

        orders = super().submit_orders_by_market(market)  # stale-recovery / reconcile / 発注

        # --- reconcile 後 (口座B 反映後) ---
        post = self._snap()
        new_labels = [lbl for (_, lbl) in self.action_log[n_act:]]
        stale_issued = "stale_flatten" in new_labels
        rt_added = len(self.round_trips) - n_rt
        prev_av = int(self._prev_av.get(mid, 0))

        self.l1_records.append({
            "t": t, "agent_id": int(self.agent_id), "market_id": mid,
            "av_pre": av_pre, "cash_pre": cash_pre,
            "av_delta_raw": av_pre - prev_av,
            # 口座B pre
            "pos_pre": pre[0], "eq_pre": pre[1], "ea_pre": pre[2],
            "ep_pre": pre[3], "es_pre": pre[4], "pend_pre": pre[5],
            # 口座B post
            "pos_post": post[0], "eq_post": post[1], "ea_post": post[2],
            "ep_post": post[3], "es_post": post[4], "pend_post": post[5],
            "stale_issued": bool(stale_issued), "rt_added": int(rt_added),
        })
        self._prev_av[mid] = av_pre
        return orders


class AuditLogger(Logger):
    """L2(約定) と L3(市場 step) を独立した2リストに収集する PAMS Logger.

    claim-2(L1) はこの Logger を一切参照しないため、本 Logger の正しさに
    claim-2 判定が従属しない (独立性の硬い制約を構造で保証)。
    """

    def __init__(self) -> None:
        super().__init__()
        self.executions: List[Dict[str, Any]] = []      # L2
        self.market_steps: List[Dict[str, Any]] = []     # L3

    def process_execution_log(self, log) -> None:  # noqa: ANN001
        self.executions.append({
            "t": int(log.time), "market_id": int(log.market_id),
            "buy_agent_id": int(log.buy_agent_id),
            "sell_agent_id": int(log.sell_agent_id),
            "qty": int(log.volume), "price": float(log.price),
        })

    def process_market_step_end_log(self, log) -> None:  # noqa: ANN001
        m = log.market
        try:
            mid = m.get_mid_price()
        except Exception:
            mid = None
        bb = m.get_best_buy_price()
        ba = m.get_best_sell_price()
        self.market_steps.append({
            "t": int(m.get_time()), "market_id": int(m.market_id),
            "mid": (float(mid) if mid is not None else None),
            "market_price": float(m.get_market_price()),
            "best_bid": (float(bb) if bb is not None else None),
            "best_ask": (float(ba) if ba is not None else None),
            "n_buy": int(m.get_n_buy_order()), "n_sell": int(m.get_n_sell_order()),
        })


def gather_l1(sg_agents) -> "Any":
    """全 SG agent の L1 を 1 DataFrame に集約."""
    import pandas as pd
    rows: List[Dict[str, Any]] = []
    for a in sg_agents:
        rows.extend(getattr(a, "l1_records", []))
    return pd.DataFrame(rows)


def agent_class_map(simulator) -> Dict[int, str]:
    """agent_id -> {'SG','MMFCN','OTHER'} (L2 の相手分類用、#4)."""
    from mm_fcn_agent import MMFCNAgent  # type: ignore
    m: Dict[int, str] = {}
    for a in simulator.agents:
        if isinstance(a, WInitLoggingSpeculationAgent):
            m[int(a.agent_id)] = "SG"
        elif isinstance(a, MMFCNAgent):
            m[int(a.agent_id)] = "MMFCN"
        else:
            m[int(a.agent_id)] = "OTHER"
    return m
