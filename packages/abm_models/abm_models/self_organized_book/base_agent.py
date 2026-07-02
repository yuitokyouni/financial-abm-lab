"""LimitAgentBase: spec 003 §3.1 の片側 resting + TTL/cancel + bar/step 2 階層 (§3.3) の
共通土台。サブクラスは `_evaluate(market, bar_index)` で評価値 v_i を返すだけ。

責務 (spec 003):
  - 片側 resting (§3.1, §10-2): 同一 agent が両側に同時に LIMIT を出さない。
  - TTL/cancel (§3.1, §3.3): 残存指値は step 単位で自己キャンセル + 再貼り付け (再評価)。
    pams の ttl は保険的に併用。
  - bar/step 2 階層 (§3.3): 評価値 v_i は bar 単位で更新、step 単位で価格を再計算する
    (queue dynamics を維持しつつ bar 間凍結を避ける)。
  - aggressive/passive 内生 (§3.1): price = v × (1 ∓ margin)。クロスすれば aggressive、
    しなければ resting。bounce が消える本質。

責務外 (サブクラスで実装):
  - 評価値 v_i の生成 (ZI = random walk, Kronos = quantile-rank)。
  - margin_i, side_i (buy/sell) の決定。LimitAgentBase は base にデフォルトのみ。

最小限の bookkeeping (spec 003 §3.5: 在庫/予算は仮想化、$-game payoff で mark-to-market):
  - `_outstanding`: 自分が submit して、まだ約定もキャンセルも受けてない Order の list。
  - 片側 resting 保証: submit_orders_by_market は冒頭で _outstanding を全て Cancel 候補に積む。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pams.agents import Agent
from pams.market import Market
from pams.order import LIMIT_ORDER, Cancel, Order


@dataclass(frozen=True)
class AgentEvaluation:
    """サブクラスの _evaluate が返すデータ。

    side ∈ {-1, 0, +1}: -1=sell, +1=buy, 0=abstain。
    price は **指値価格そのもの** (margin はサブクラス内で適用済とする)。
    """
    side: int
    price: Optional[float] = None
    volume: int = 1
    log_payload: Optional[dict] = None


class LimitAgentBase(Agent):
    """spec 003 §3.1/§3.3 を満たす LIMIT-posting agent の基底。

    サブクラスは `_evaluate(market, bar_index) -> AgentEvaluation` を実装するだけ。
    """

    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.bar_size: int = int(settings.get("barSize", 10))
        self.order_ttl: int = int(settings.get("orderTtl", 20))
        self.order_volume: int = int(settings.get("orderVolume", 1))
        # PAMS callbacks は OrderLog/ExecutionLog/CancelLog (Order インスタンスを持たない,
        # order_id でひも付け) なので、(a) submit_orders で返した Order を _pending に積む、
        # (b) submitted_order callback で order_id 経由で _outstanding dict に移す。
        self._pending_orders: List[Order] = []
        self._outstanding: Dict[int, Order] = {}
        # diagnostics
        self.action_log: list[tuple[int, int, Optional[float], Optional[dict]]] = []
        self.executed_log: list[tuple[int, bool, float, int]] = []  # (time, is_buy, price, volume)
        self.canceled_log: list[tuple[int, bool, Optional[float]]] = []

    # ---- subclass hook ----
    def _evaluate(self, market: Market, bar_index: int) -> AgentEvaluation:
        raise NotImplementedError

    # ---- PAMS callbacks (log = OrderLog / ExecutionLog / CancelLog, NOT Order) ----
    def submitted_order(self, log) -> None:
        if log.agent_id != self.agent_id:
            return
        # _pending の中で order_id 一致の Order を _outstanding に移動
        # (PAMS は Order インスタンスに order_id を後付けする)
        for o in list(self._pending_orders):
            if o.order_id == log.order_id:
                self._outstanding[log.order_id] = o
                self._pending_orders.remove(o)
                return

    def executed_order(self, log) -> None:
        # ExecutionLog は buy_agent_id / sell_agent_id / buy_order_id / sell_order_id を持つ
        side_is_buy = None
        my_oid = None
        if getattr(log, "buy_agent_id", None) == self.agent_id:
            side_is_buy = True
            my_oid = log.buy_order_id
        elif getattr(log, "sell_agent_id", None) == self.agent_id:
            side_is_buy = False
            my_oid = log.sell_order_id
        else:
            return
        if my_oid in self._outstanding:
            del self._outstanding[my_oid]
        self.executed_log.append(
            (int(log.time), bool(side_is_buy), float(log.price), int(log.volume))
        )

    def canceled_order(self, log) -> None:
        if log.agent_id != self.agent_id:
            return
        oid = log.order_id
        if oid in self._outstanding:
            del self._outstanding[oid]
        self.canceled_log.append(
            (int(log.cancel_time), bool(log.is_buy), log.price)
        )

    # ---- main loop ----
    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        return sum((self.submit_orders_by_market(m) for m in markets), [])

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        if not self.is_market_accessible(market_id=market.market_id):
            return []
        time = market.get_time()
        bar_index = time // self.bar_size

        out: List[Union[Order, Cancel]] = []
        # 1. 片側 resting 保証: 前 step の残存 outstanding を全部 Cancel に積む
        for oid, o in list(self._outstanding.items()):
            out.append(Cancel(order=o))

        # 2. 新規評価
        eval_ = self._evaluate(market, bar_index)
        self.action_log.append(
            (time, eval_.side,
             None if eval_.price is None else float(eval_.price),
             eval_.log_payload)
        )
        if eval_.side == 0 or eval_.price is None or eval_.price <= 0:
            return out  # abstain (Cancel のみ)

        is_buy = eval_.side > 0
        new_order = Order(
            agent_id=self.agent_id, market_id=market.market_id,
            is_buy=is_buy, kind=LIMIT_ORDER,
            volume=int(eval_.volume),
            price=float(eval_.price),
            ttl=int(self.order_ttl),
        )
        # PAMS が order_id を後付けする前に Order インスタンスを保持
        self._pending_orders.append(new_order)
        out.append(new_order)
        return out
