"""YH005: Katahira et al. (2019) Speculation Game — 参照実装.

クラスベースの per-agent ループで仕様通りに素直に書く。ベクトル化版 (simulate.py)
との bit-parity 担保のため、RNG 消費順序 (§7) を厳守する:

  初期化 (1 回ずつ):
    1. strategies = rng.choice([-1,0,1], size=(N, S, 5^M))
    2. init_u100  = rng.integers(0, 100, size=N)
    3. init_active= rng.integers(0, S, size=N)
    4. mu0        = rng.integers(0, 5^M)

  毎ステップ、エージェント index 0..N-1 の順:
    - decision_mode='random': 各 i で u=rng.random()、u<p のとき d=rng.random()
    - history_mode='exogenous': step 末に 1 回 rng.integers(0, 5^M)
    - close イベント後 (index 順): 戦略レビュー (必要時のみ rng.choice)、破産時は
      rng.choice(...)×1, rng.integers(0,100)×1, rng.integers(0,S)×1

処理順 (§3.11):
  1. μ_t = 現 μ を snapshot
  2. 各エージェント rec を決定 (strategy or random)
  3. effective action 表 (§3.8) で (effective, quantity, kind)
  4. D = Σ effective*quantity, Δp = D/N, p ← p + Δp
  5. h = quantize(Δp, C), μ 更新 (endogenous: shift_in / exogenous: random), P ← P + h
  6. close: ΔG, G 更新, w 更新, position/entry クリア
  7. open : position, entry_price, entry_action, entry_quantity
  8. virtual 更新 (j != active_idx)
  9. close 起きた i について index 順: 戦略レビュー → 破産判定
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from history import quantize_price_change, shift_in, mu_capacity


@dataclass
class Agent:
    """1 エージェント分の状態。strategies と G は S 個の戦略について。"""
    strategies: np.ndarray       # (S, K) int8, 値 ∈ {-1, 0, +1}
    G: np.ndarray                # (S,) int64, 認知利得 (実 + 仮想)
    w: int                       # wealth (int)
    active_idx: int              # 現在使用中の戦略 index
    position: int                # ∈ {-1, 0, +1}
    entry_price: int             # open 時の P
    entry_action: int            # open 時の effective ∈ {-1, +1}
    entry_quantity: int          # open 時の q = floor(w/B)
    entry_step: int              # open 時の step t (round-trip horizon 追跡用)
    virtual_positions: np.ndarray       # (S,) int8
    virtual_entry_prices: np.ndarray    # (S,) int64
    virtual_entry_actions: np.ndarray   # (S,) int8


@dataclass
class Market:
    p: float           # 実価格
    P: int             # 認知価格 (cumsum of h)
    mu: int            # 履歴 index ∈ [0, 5^M)
    M: int


def run_reference(
    N: int,
    M: int,
    S: int,
    T: int,
    B: int = 9,
    C: float = 3.0,
    seed: int = 42,
    p0: float = 100.0,
    history_mode: str = "endogenous",     # 'endogenous' | 'exogenous'
    decision_mode: str = "strategy",       # 'strategy'   | 'random'
    random_open_prob: float = 0.5,
    order_size_buckets: tuple[int, int] = (50, 100),
) -> dict:
    """Speculation Game の per-agent 参照実装。詳細はモジュール docstring。"""
    assert history_mode in ("endogenous", "exogenous")
    assert decision_mode in ("strategy", "random")
    small_max, medium_max = int(order_size_buckets[0]), int(order_size_buckets[1])
    assert small_max < medium_max, "order_size_buckets must be (small_max, medium_max) with small_max < medium_max"
    K = mu_capacity(M)
    rng = np.random.default_rng(seed)

    # --- §7.1 初期化 ---
    all_strategies = rng.choice([-1, 0, 1], size=(N, S, K)).astype(np.int8)
    init_u100 = rng.integers(0, 100, size=N)
    init_active = rng.integers(0, S, size=N)
    mu0 = int(rng.integers(0, K))

    # --- エージェント生成 ---
    agents: list[Agent] = []
    for i in range(N):
        a = Agent(
            strategies=all_strategies[i].copy(),
            G=np.zeros(S, dtype=np.int64),
            w=int(B) + int(init_u100[i]),
            active_idx=int(init_active[i]),
            position=0,
            entry_price=0,
            entry_action=0,
            entry_quantity=0,
            entry_step=0,
            virtual_positions=np.zeros(S, dtype=np.int8),
            virtual_entry_prices=np.zeros(S, dtype=np.int64),
            virtual_entry_actions=np.zeros(S, dtype=np.int8),
        )
        agents.append(a)

    market = Market(p=float(p0), P=0, mu=mu0, M=M)

    # --- ログ配列 ---
    prices = np.empty(T, dtype=np.float64)
    h_series = np.empty(T, dtype=np.int8)
    cognitive_prices = np.empty(T, dtype=np.int64)
    num_buy_log = np.empty(T, dtype=np.int64)
    num_sell_log = np.empty(T, dtype=np.int64)
    num_active_hold_log = np.empty(T, dtype=np.int64)
    num_passive_hold_log = np.empty(T, dtype=np.int64)
    num_orders_by_size_buy = np.zeros((T, 3), dtype=np.int64)
    num_orders_by_size_sell = np.zeros((T, 3), dtype=np.int64)
    num_substitutions = 0

    # round-trip event log (append per close, convert to np.ndarray at return)
    rt_agent_idx: list[int] = []
    rt_open_t: list[int] = []
    rt_close_t: list[int] = []
    rt_entry_action: list[int] = []
    rt_entry_quantity: list[int] = []
    rt_delta_G: list[int] = []

    # ---- メインループ ----
    for t in range(T):
        mu_t = market.mu  # snapshot: このステップの決定に使う

        # 1) 意思決定
        recs = np.zeros(N, dtype=np.int8)
        if decision_mode == "strategy":
            for i in range(N):
                a = agents[i]
                recs[i] = int(a.strategies[a.active_idx, mu_t])
        else:  # 'random' (Null B): position 非参照の literal 解釈
            for i in range(N):
                u = rng.random()
                if u < random_open_prob:
                    d = rng.random()
                    recs[i] = 1 if d < 0.5 else -1
                # else recs[i] = 0

        # 2) effective action 表 (§3.8)
        effective = np.zeros(N, dtype=np.int64)
        quantity = np.zeros(N, dtype=np.int64)
        kinds: list[str] = [""] * N
        for i in range(N):
            a = agents[i]
            rec = int(recs[i])
            pos = a.position
            if pos == 0:
                if rec == 0:
                    kinds[i] = "idle"
                else:
                    effective[i] = rec
                    quantity[i] = a.w // B
                    kinds[i] = "open"
            else:  # pos != 0
                if rec == 0:
                    kinds[i] = "active_hold"
                elif rec == pos:
                    kinds[i] = "passive_hold"
                else:  # rec == -pos
                    effective[i] = rec
                    quantity[i] = a.entry_quantity
                    kinds[i] = "close"

        # 3) 市場集計
        D = int((effective * quantity).sum())
        dp = D / N
        market.p += dp

        # 4) 量子化 + 履歴 + 認知価格
        h = quantize_price_change(dp, C)
        market.P += h
        if history_mode == "endogenous":
            market.mu = shift_in(market.mu, h + 2, M)
        else:
            market.mu = int(rng.integers(0, K))

        # 5) close 実行 — 状態クリア前に round_trips レコードを append
        for i in range(N):
            if kinds[i] == "close":
                a = agents[i]
                dG = int(a.entry_action) * (market.P - int(a.entry_price))
                rt_agent_idx.append(i)
                rt_open_t.append(int(a.entry_step))
                rt_close_t.append(t)
                rt_entry_action.append(int(a.entry_action))
                rt_entry_quantity.append(int(a.entry_quantity))
                rt_delta_G.append(dG)
                a.G[a.active_idx] += dG
                a.w += dG * int(a.entry_quantity)
                a.position = 0
                a.entry_price = 0
                a.entry_action = 0
                a.entry_quantity = 0
                a.entry_step = 0

        # 6) open 実行
        for i in range(N):
            if kinds[i] == "open":
                a = agents[i]
                a.position = int(effective[i])
                a.entry_price = market.P
                a.entry_action = int(effective[i])
                a.entry_quantity = int(quantity[i])
                a.entry_step = t

        # 7) virtual 更新 (j != active_idx)
        for i in range(N):
            a = agents[i]
            for j in range(S):
                if j == a.active_idx:
                    continue
                rec_ij = int(a.strategies[j, mu_t])
                vpos = int(a.virtual_positions[j])
                if vpos == 0:
                    if rec_ij != 0:
                        a.virtual_positions[j] = rec_ij
                        a.virtual_entry_prices[j] = market.P
                        a.virtual_entry_actions[j] = rec_ij
                else:
                    if rec_ij == -vpos:
                        dG_v = int(a.virtual_entry_actions[j]) * (
                            market.P - int(a.virtual_entry_prices[j])
                        )
                        a.G[j] += dG_v
                        a.virtual_positions[j] = 0
                        a.virtual_entry_prices[j] = 0
                        a.virtual_entry_actions[j] = 0
                    # else hold (rec_ij == 0 or rec_ij == vpos)

        # 8) 戦略レビュー + 破産判定 (close 起きた i を index 順)
        for i in range(N):
            if kinds[i] != "close":
                continue
            a = agents[i]
            # レビュー
            g_max = int(a.G.max())
            best = np.flatnonzero(a.G == g_max)
            if a.active_idx not in best:
                new_idx = int(rng.choice(best))
                # 新 j** に virtual がある → クリア (G は更新しない)
                a.virtual_positions[new_idx] = 0
                a.virtual_entry_prices[new_idx] = 0
                a.virtual_entry_actions[new_idx] = 0
                a.active_idx = new_idx
            # 破産置換
            if a.w < B:
                new_strategies = rng.choice([-1, 0, 1], size=(S, K)).astype(np.int8)
                new_w = int(B) + int(rng.integers(0, 100))
                new_active = int(rng.integers(0, S))
                a.strategies = new_strategies
                a.w = new_w
                a.active_idx = new_active
                a.position = 0
                a.entry_price = 0
                a.entry_action = 0
                a.entry_quantity = 0
                a.entry_step = 0
                a.virtual_positions = np.zeros(S, dtype=np.int8)
                a.virtual_entry_prices = np.zeros(S, dtype=np.int64)
                a.virtual_entry_actions = np.zeros(S, dtype=np.int8)
                a.G = np.zeros(S, dtype=np.int64)
                num_substitutions += 1

        # 9) 統計記録
        prices[t] = market.p
        h_series[t] = h
        cognitive_prices[t] = market.P
        num_buy_log[t] = int((effective == 1).sum())
        num_sell_log[t] = int((effective == -1).sum())
        num_active_hold_log[t] = sum(1 for k in kinds if k == "active_hold")
        num_passive_hold_log[t] = sum(1 for k in kinds if k == "passive_hold")
        # order size buckets: effective != 0 のオーダーを quantity で 3 分類
        buy_mask_t = (effective == 1)
        sell_mask_t = (effective == -1)
        buy_q = quantity[buy_mask_t]
        sell_q = quantity[sell_mask_t]
        num_orders_by_size_buy[t, 0] = int((buy_q <= small_max).sum())
        num_orders_by_size_buy[t, 1] = int(((buy_q > small_max) & (buy_q <= medium_max)).sum())
        num_orders_by_size_buy[t, 2] = int((buy_q > medium_max).sum())
        num_orders_by_size_sell[t, 0] = int((sell_q <= small_max).sum())
        num_orders_by_size_sell[t, 1] = int(((sell_q > small_max) & (sell_q <= medium_max)).sum())
        num_orders_by_size_sell[t, 2] = int((sell_q > medium_max).sum())

    final_wealth = np.array([a.w for a in agents], dtype=np.int64)

    round_trips = {
        "agent_idx": np.asarray(rt_agent_idx, dtype=np.int64),
        "open_t": np.asarray(rt_open_t, dtype=np.int64),
        "close_t": np.asarray(rt_close_t, dtype=np.int64),
        "entry_action": np.asarray(rt_entry_action, dtype=np.int8),
        "entry_quantity": np.asarray(rt_entry_quantity, dtype=np.int64),
        "delta_G": np.asarray(rt_delta_G, dtype=np.int64),
    }
    num_orders_by_size = num_orders_by_size_buy + num_orders_by_size_sell

    return {
        "prices": prices,
        "h_series": h_series,
        "cognitive_prices": cognitive_prices,
        "final_wealth": final_wealth,
        "num_substitutions": num_substitutions,
        "num_buy": num_buy_log,
        "num_sell": num_sell_log,
        "num_active_hold": num_active_hold_log,
        "num_passive_hold": num_passive_hold_log,
        "total_wealth": int(final_wealth.sum()),
        "round_trips": round_trips,
        "num_orders_by_size": num_orders_by_size,
        "num_orders_by_size_buy": num_orders_by_size_buy,
        "num_orders_by_size_sell": num_orders_by_size_sell,
    }
