"""YH006: Speculation Game agent on LOB (PAMS).

YH005/simulate.py の SG decision rule を PAMS Agent subclass として再実装。

翻訳の要点:
- global history μ(t) は simulator 属性として共有 (history_broadcast.SharedHistoryState)
- round-trip open/close は MARKET_ORDER で送る (Phase 1 成行のみ)
- fill 確定は次 step 冒頭で self.asset_volumes から reconcile
- 部分 close は entry_quantity を actual fill 分だけ残す ("まだ閉じ切れてない")
- bankruptcy は close 完了直後のみチェック (YH005 の close_idx ループに合わせる)
- virtual round-trip は非 active 戦略に対し毎 step 更新、G を貯める

**設計 A': MARKET_ORDER + self-cancel + opposing-liquidity guard** (SPEC §3.2(c) 準拠):
- open / close は常に MARKET_ORDER で送る (SPEC 準拠)
- 送る直前に反対板の LIMIT top 価格を確認 (market.get_best_*_price())。
  None (= LIMIT なし、MARKET top or 空) なら **submit を skip** して
  次 step に延期。
- 送った Order 参照を self._outstanding[market_id] に記録
- 次 step の submit_orders_by_market 冒頭で、自分の未約定 Order に対し
  Cancel を送る (PAMS の order_book.cancel は既 fill / 既 expire に対し
  is_canceled=True をセットするだけで例外を出さない)

guard 導入の理由 (probe で特定):
  反対板が一時的に dry (FCN が片寄った瞬間) な step で毎回 cancel→resubmit
  を繰り返すと、MARKET_ORDER が板に累積して book size が 300 → 1600 に爆発。
  そうなると `priority_queue.remove` (O(N)) × 100 SG cancel per step が
  O(N²) 経路となり runtime が T² scaling する (t=250→300 で 1 step dt が
  283ms → 9429ms に単調増加)。guard で「マッチ不可な瞬間は submit しない」
  ことで accumulation を抑え、book size と cancel cost を bound する。

**Wealth 2-account 設計 (Phase 1 固有決定)**:
SG の cognitive wealth (sg_wealth) と PAMS LOB cash (self.cash_amount) を分離する。
- sg_wealth: YH005 の w に対応。Pareto/uniform 初期化、round-trip close で
  ΔG × entry_quantity で更新、B 未満で bankruptcy → substitute。
- self.cash_amount: PAMS が cost basis を追跡する LOB cash。
  sizing (q = ⌊sg_wealth / B⌋) と bankruptcy 判定に使わないため、
  deeply negative になっても SG ロジックは壊れない。
- q = ⌊sg_wealth / B⌋ で wealth heterogeneity が order size に現れる。
- final_wealth (adapter 経由) = sg_wealth、YH005 と直接比較可能。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Union

import numpy as np

from pams.agents import Agent
from pams.logs.base import Logger
from pams.market import Market
from pams.order import MARKET_ORDER, Cancel, Order

from history_broadcast import get_or_init as _get_shared_history


class SpeculationAgent(Agent):
    """Katahira-Chen 2019 SG agent on LOB."""

    def __init__(
        self,
        agent_id: int,
        prng: random.Random,
        simulator: Any,
        name: str,
        logger: Optional[Logger] = None,
    ) -> None:
        super().__init__(agent_id, prng, simulator, name, logger)
        # Defaults — setup() populates from config.
        self.M: int = 5
        self.S: int = 2
        self.B: int = 9
        self.c_ticks: float = 0.03
        self.wealth_mode: str = "uniform"
        self.pareto_alpha: float = 1.5
        self.pareto_xmin: float = 9.0
        self.strategies: np.ndarray = np.zeros((self.S, 5 ** self.M), dtype=np.int8)
        self.G: np.ndarray = np.zeros(self.S, dtype=np.int64)
        self.active_idx: int = 0
        # SG cognitive wealth (separate from PAMS self.cash_amount)
        self.sg_wealth: int = 0
        # Real round-trip state
        self.position: int = 0
        self.entry_action: int = 0
        self.entry_price_cog: int = 0
        self.entry_quantity: int = 0
        self.entry_step: int = 0
        self.close_price_cog: int = 0
        self.close_step: int = 0
        # Virtual state per strategy
        self.v_pos: np.ndarray = np.zeros(self.S, dtype=np.int8)
        self.v_ep: np.ndarray = np.zeros(self.S, dtype=np.int64)
        self.v_ea: np.ndarray = np.zeros(self.S, dtype=np.int8)
        # Pending LOB order tracking
        self.pending_intent: Optional[str] = None
        self.pending_action: int = 0
        self.pending_quantity_sent: int = 0
        # Logs collected at end of sim
        self.round_trips: List[Dict[str, int]] = []
        self.action_log: List[tuple] = []
        self.submit_log: List[tuple] = []
        # Counters
        self.num_substitutions: int = 0
        self.num_partial_opens: int = 0
        self.num_partial_closes: int = 0
        self.num_zero_opens: int = 0
        # Open/close-intent accounting (成行 MARKET_ORDER + self-cancel 設計の診断用)
        self.open_submits: int = 0           # open MARKET_ORDER を submit した回数
        self.open_full_matches: int = 0      # open が完全約定した回数
        self.open_partial_matches: int = 0   # open が部分約定した回数 (= num_partial_opens)
        self.open_cancelled: int = 0         # open が self-cancel で取り消された回数 (= num_zero_opens)
        self.close_submits: int = 0          # close MARKET_ORDER を submit した回数
        self.close_full_matches: int = 0     # close が完全約定した回数 (= len(round_trips))
        self.close_partial_matches: int = 0  # close が部分約定した回数 (= num_partial_closes)
        self.close_cancelled: int = 0        # close が self-cancel で取り消された回数
        # Outstanding orders per market — at start of each step, cancel these
        self._outstanding: Dict[int, List[Order]] = {}
        self.num_cancels_sent: int = 0
        # opposing-liquidity guard: 反対板 dry で submit を skip した回数
        self.num_liquidity_skips: int = 0
        # C-2 fix: 信念 (position × entry_quantity) と実在庫 (asset_volumes) の
        # 乖離を毎 step 検出してフラット化した回数。0 が健全 (在庫 desync なし)。
        self.num_desync: int = 0
        # #16: 部分 close で約定した filled 株分の実現損益は現状 G/wealth に記帳
        # されず、残量が最終 close する時点の価格でのみ記帳される (= ドロップ)。
        # cognitive round-trip を分割しない YH005 準拠を優先し意図的にドロップし、
        # リーク量 (Σ ΔG_partial × filled) をここで計上して可視化する。意味論の
        # 変更 (分割記帳) は research owner の決定待ち。
        self.partial_close_leaked_dG_q: int = 0
        # Substitute event log: (t, dead_wealth, new_wealth) per event for
        # measurement 7 (dynamic-wealth layer activity diagnosis)
        self.substitute_events: List[tuple] = []
        self._market_id_cache: Optional[int] = None
        # last substitute step (for turnover time per agent)
        self._last_substitute_t: int = 0

    # ------------------------------------------------------------------
    # setup: read config, init strategies, override cash if Pareto/uniform
    # ------------------------------------------------------------------
    def setup(
        self,
        settings: Dict[str, Any],
        accessible_markets_ids: List[int],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # Super requires cashAmount + assetVolume in settings. Keep them as placeholders.
        super().setup(settings=settings, accessible_markets_ids=accessible_markets_ids)

        self.M = int(settings.get("M", 5))
        self.S = int(settings.get("S", 2))
        self.B = int(settings.get("B", 9))
        self.c_ticks = float(settings.get("cTicks", 0.03))
        self.wealth_mode = str(settings.get("wealthMode", "uniform"))
        self.pareto_alpha = float(settings.get("paretoAlpha", 1.5))
        self.pareto_xmin = float(settings.get("paretoXmin", 9))

        K = 5 ** self.M
        flat = [self.prng.choice([-1, 0, 1]) for _ in range(self.S * K)]
        self.strategies = np.asarray(flat, dtype=np.int8).reshape(self.S, K)
        self.G = np.zeros(self.S, dtype=np.int64)
        self.active_idx = self.prng.randrange(self.S)
        self.v_pos = np.zeros(self.S, dtype=np.int8)
        self.v_ep = np.zeros(self.S, dtype=np.int64)
        self.v_ea = np.zeros(self.S, dtype=np.int8)

        if self.wealth_mode == "pareto":
            w = int(self.pareto_xmin * self.prng.paretovariate(self.pareto_alpha))
        elif self.wealth_mode == "uniform":
            w = int(self.B + self.prng.random() * 100)
        else:
            w = int(self.cash_amount)
        self.sg_wealth = w
        # self.cash_amount (PAMS LOB cash) は super().setup が draw した値のまま残す。
        # LOB 執行の cost basis は PAMS 側で追跡され、SG ロジックには干渉しない。

    # ------------------------------------------------------------------
    # Phase 2 ablation hook: open round-trip の q を返す.
    #
    # Default = `max(1, sg_wealth // B)` (= Phase 1 既存挙動と bit-一致)。
    # Phase 2 A1 ablation で subclass が override して `q_const` を返す。
    # Phase 2 全体ルール: 「Phase 1 への後方互換拡張は許容、動作変更は禁止」(S2 plan §0.4)。
    # ------------------------------------------------------------------
    def _compute_open_quantity(self) -> int:
        return max(1, int(self.sg_wealth // self.B))

    # ------------------------------------------------------------------
    # main decision: called by runner once per step (if sampled)
    # ------------------------------------------------------------------
    def submit_orders(self, markets: List[Market]) -> List[Union[Order, Cancel]]:
        orders: List[Union[Order, Cancel]] = []
        for market in markets:
            if not self.is_market_accessible(market.market_id):
                continue
            orders.extend(self.submit_orders_by_market(market))
        return orders

    def submit_orders_by_market(self, market: Market) -> List[Union[Order, Cancel]]:
        orders: List[Union[Order, Cancel]] = []
        t = market.get_time()
        market_id = market.market_id
        self._market_id_cache = market_id

        # Step 0: Cancel any outstanding orders from previous step.
        # order_book.cancel is a no-op (just sets is_canceled) if the order
        # is no longer in the book, so sending Cancel unconditionally is safe.
        prev_outstanding = self._outstanding.pop(market_id, [])
        for ord_obj in prev_outstanding:
            if ord_obj.is_canceled:
                continue
            if ord_obj.order_id is None or ord_obj.placed_at is None:
                # Never accepted by market — skip (shouldn't happen normally)
                continue
            orders.append(Cancel(order=ord_obj))
            self.num_cancels_sent += 1
            # If this was the close that was still alive, account for it
            if self.pending_intent == "close" and ord_obj.volume > 0:
                # partial-fill leftover or total miss — caller will detect via reconcile
                pass

        hist = _get_shared_history(self.simulator, market, self.M, self.c_ticks)
        mu_t = hist.mu
        P_now = hist.P

        self._reconcile(market_id, P_now)

        # C-2 fix — "reality is truth" resync (毎 step, reconcile 直後):
        # 信念 (position × entry_quantity) と実在庫 (asset_volumes) が乖離したら、
        # 実在庫をフラット化して信念を position=0 にリセットする。これは旧
        # stale-fill recovery (pending=None & position==0 のみ) を一般化したもの。
        # 乖離源は 2 つ: (1) 遅延約定が SG 非把握の在庫を残す (position==0 で発覚)、
        # (2) close の over-fill で実在庫が逆符号に反転 (_reconcile が正しく full-
        # close 記帳し position=0 にした残余を、ここで flatten)。position!=0 の hold
        # 中に約定がドリフトしても同じ経路で捕捉する。reconcile は必ず pending_intent
        # を None にするため、この block は毎 step 走り再発を防ぐ。健全時は invariant
        # が成立し発火しない (既存挙動と bit 一致)。
        if self.pending_intent is None:
            actual_vol = int(self.asset_volumes.get(market_id, 0))
            expected_vol = int(self.position) * int(self.entry_quantity)
            if actual_vol != expected_vol:
                self.num_desync += 1
                if actual_vol != 0:
                    flat_order = Order(
                        agent_id=self.agent_id,
                        market_id=market_id,
                        is_buy=(actual_vol < 0),
                        kind=MARKET_ORDER,
                        volume=abs(actual_vol),
                    )
                    orders.append(flat_order)
                    self._outstanding.setdefault(market_id, []).append(flat_order)
                # 破損した round-trip の信念を破棄し flat に戻す
                self.position = 0
                self.entry_action = 0
                self.entry_price_cog = 0
                self.entry_quantity = 0
                self.entry_step = 0
                self._record_action(t, "desync_flatten")
                return orders

        # A3 ablation hook (Phase 2 S6): lifetime cap。base 実装は常に False を
        # 返すため default 経路は既存挙動と bit-一致 (後方互換 protocol)。
        # fire 時は bankruptcy と同じ _substitute() で交代し、残存 position /
        # asset_volumes は次 step の stale-fill recovery (上の flatten 経路、
        # S4 で bankruptcy substitute 後 re-init 境界用に実証済) が回収する。
        if self.pending_intent is None and self._should_force_retire(t):
            self._substitute(t=int(t))
            self._record_action(t, "forced_retire")
            return orders

        rec = int(self.strategies[self.active_idx, mu_t])

        if self.position == 0 and rec != 0:
            is_buy = (rec > 0)
            # opposing-liquidity guard
            opp_best = market.get_best_sell_price() if is_buy else market.get_best_buy_price()
            if opp_best is None:
                self.num_liquidity_skips += 1
                self._record_action(t, "idle")
            else:
                q = self._compute_open_quantity()
                self.pending_intent = "open"
                self.pending_action = rec
                self.pending_quantity_sent = q
                self.entry_action = rec
                self.entry_price_cog = P_now
                self.entry_step = t
                self.open_submits += 1
                new_order = Order(
                    agent_id=self.agent_id,
                    market_id=market_id,
                    is_buy=is_buy,
                    kind=MARKET_ORDER,
                    volume=q,
                )
                orders.append(new_order)
                self._outstanding.setdefault(market_id, []).append(new_order)
                self.submit_log.append((t, rec * q))
                self._record_action(t, "buy" if rec > 0 else "sell")
        elif self.position != 0 and rec == -self.position:
            is_buy = (rec > 0)
            opp_best = market.get_best_sell_price() if is_buy else market.get_best_buy_price()
            if opp_best is None:
                self.num_liquidity_skips += 1
                self._record_action(t, "active_hold")
            else:
                q = int(self.entry_quantity)
                self.pending_intent = "close"
                self.pending_action = rec
                self.pending_quantity_sent = q
                self.close_price_cog = P_now
                self.close_step = t
                self.close_submits += 1
                new_order = Order(
                    agent_id=self.agent_id,
                    market_id=market_id,
                    is_buy=is_buy,
                    kind=MARKET_ORDER,
                    volume=q,
                )
                orders.append(new_order)
                self._outstanding.setdefault(market_id, []).append(new_order)
                self.submit_log.append((t, rec * q))
                self._record_action(t, "buy" if rec > 0 else "sell")
        else:
            if self.position == 0:
                self._record_action(t, "idle")
            elif rec == 0:
                self._record_action(t, "active_hold")
            else:
                self._record_action(t, "passive_hold")

        self._update_virtual(mu_t, P_now)

        return orders

    def _reconcile(self, market_id: int, P_now: int) -> None:
        if self.pending_intent is None:
            return

        actual_vol = int(self.asset_volumes.get(market_id, 0))

        if self.pending_intent == "open":
            if actual_vol == 0:
                self.num_zero_opens += 1
                self.open_cancelled += 1
                self.entry_action = 0
                self.entry_price_cog = 0
                self.entry_quantity = 0
                self.entry_step = 0
            else:
                self.position = 1 if actual_vol > 0 else -1
                new_q = abs(actual_vol)
                if new_q < self.pending_quantity_sent:
                    self.num_partial_opens += 1
                    self.open_partial_matches += 1
                else:
                    self.open_full_matches += 1
                self.entry_quantity = new_q
            self.pending_intent = None
            self.pending_action = 0
            self.pending_quantity_sent = 0

        elif self.pending_intent == "close":
            # C-2 fix: 符号付き分類。entry_sign = self.position (閉じようとする側)。
            #   entry_sign × actual_vol <= 0 : 在庫が 0 に到達 or 逆符号に反転
            #     (over-fill) → 意図した round-trip は閉じた。entry_quantity 分の
            #     ΔG を記帳し flat に戻す。逆符号の残余在庫は次 step の resync guard
            #     が flatten する。
            #   entry_sign × actual_vol > 0 かつ |actual_vol| < entry_quantity :
            #     同符号で減少 → 部分約定。
            #   それ以外 (同符号・不変) : close 未約定 (self-cancel)。
            entry_sign = int(self.position)
            if entry_sign * actual_vol <= 0:
                self.close_full_matches += 1
                dG = int(self.entry_action) * (int(self.close_price_cog) - int(self.entry_price_cog))
                self.G[self.active_idx] += dG
                # SG cognitive wealth update: w += ΔG * q
                self.sg_wealth += int(dG) * int(self.entry_quantity)
                self.round_trips.append({
                    "agent_idx": int(self.agent_id),
                    "open_t": int(self.entry_step),
                    "close_t": int(self.close_step),
                    "entry_action": int(self.entry_action),
                    "entry_quantity": int(self.entry_quantity),
                    "delta_G": int(dG),
                })
                self.position = 0
                self.entry_action = 0
                self.entry_price_cog = 0
                self.entry_quantity = 0
                self.entry_step = 0
                g_max = int(self.G.max())
                best = np.flatnonzero(self.G == g_max).tolist()
                if self.active_idx not in best:
                    new_idx = best[self.prng.randrange(len(best))]
                    self.v_pos[new_idx] = 0
                    self.v_ep[new_idx] = 0
                    self.v_ea[new_idx] = 0
                    self.active_idx = new_idx
                if self.sg_wealth < self.B:
                    self._substitute(t=int(self.close_step))
            elif abs(actual_vol) < self.entry_quantity:
                # 同符号 (entry_sign × actual_vol > 0) で在庫が減少 = 部分約定。
                # #16: filled 株分の実現損益 (ΔG_partial × filled) は記帳せずドロップ
                # し、リーク量を診断計上する (上の counter コメント参照)。
                filled = int(self.entry_quantity) - abs(actual_vol)
                dG_partial = int(self.entry_action) * (
                    int(self.close_price_cog) - int(self.entry_price_cog)
                )
                self.partial_close_leaked_dG_q += int(dG_partial) * int(filled)
                self.position = 1 if actual_vol > 0 else -1
                self.entry_quantity = abs(actual_vol)
                self.num_partial_closes += 1
                self.close_partial_matches += 1
            else:
                # 同符号で |actual_vol| >= entry_quantity (実質不変): close
                # MARKET_ORDER が前 step で約定せず、この step 冒頭で self-cancel
                # された。次 step で同 condition なら再度 MARKET_ORDER を送る。
                self.close_cancelled += 1
            self.pending_intent = None
            self.pending_action = 0
            self.pending_quantity_sent = 0

    def _update_virtual(self, mu_t: int, P_now: int) -> None:
        recs_all = self.strategies[:, mu_t].astype(np.int8)
        not_active = np.ones(self.S, dtype=bool)
        not_active[self.active_idx] = False

        v_open_mask = (self.v_pos == 0) & (recs_all != 0) & not_active
        if v_open_mask.any():
            vals = recs_all[v_open_mask]
            self.v_pos[v_open_mask] = vals
            self.v_ep[v_open_mask] = P_now
            self.v_ea[v_open_mask] = vals

        v_close_mask = (self.v_pos != 0) & (recs_all == -self.v_pos) & not_active
        if v_close_mask.any():
            dG_v = self.v_ea[v_close_mask].astype(np.int64) * (P_now - self.v_ep[v_close_mask])
            js = np.where(v_close_mask)[0]
            for j, dg in zip(js, dG_v):
                self.G[int(j)] += int(dg)
            self.v_pos[v_close_mask] = 0
            self.v_ep[v_close_mask] = 0
            self.v_ea[v_close_mask] = 0

    def _should_force_retire(self, t: int) -> bool:
        """A3 ablation hook (Phase 2 S6): lifetime cap 判定。

        base は常に False = Phase 1 既存挙動 (lifetime cap なし)。
        Phase 2 の LifetimeCapSpeculationAgent が override し、
        在籍 (t − _last_substitute_t) ≥ τ_max で強制交代する。
        """
        return False

    def _substitute(self, t: int = 0) -> None:
        # Snapshot dead state before reset (for measurement 7)
        dead_wealth = int(self.sg_wealth)
        K = 5 ** self.M
        flat = [self.prng.choice([-1, 0, 1]) for _ in range(self.S * K)]
        self.strategies = np.asarray(flat, dtype=np.int8).reshape(self.S, K)
        self.G[:] = 0
        self.active_idx = self.prng.randrange(self.S)
        self.v_pos[:] = 0
        self.v_ep[:] = 0
        self.v_ea[:] = 0
        self.position = 0
        self.entry_action = 0
        self.entry_price_cog = 0
        self.entry_quantity = 0
        self.entry_step = 0
        new_wealth = int(self.B + self.prng.random() * 100)
        self.sg_wealth = new_wealth
        self.num_substitutions += 1
        self.substitute_events.append((int(t), dead_wealth, new_wealth))
        self._last_substitute_t = int(t)

    def _record_action(self, t: int, label: str) -> None:
        self.action_log.append((t, label))
