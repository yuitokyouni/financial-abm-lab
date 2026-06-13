"""YH005: Speculation Game — ベクトル化実装.

参照実装 (model.run_reference) と bit-parity するベクトル化版。§7 の RNG 消費順を
厳守する。主な違い:

  - 戦略選択 (strategy mode): fancy indexing で一発
  - effective action 表: boolean マスクで (N,) 配列ベクトル化
  - close/open 実行: マスク selection + scatter 更新
  - virtual 更新: (N, S) boolean マスクで一括 + np.add.at で G 更新
  - ただし: (i) decision_mode='random' の per-agent RNG、(ii) close 起きた i の
    戦略レビュー + 破産判定は、index 順の for-loop を残す (RNG 一致のため)
"""

from __future__ import annotations

import numpy as np

from history import quantize_price_change, shift_in, mu_capacity


def simulate(
    N: int,
    M: int,
    S: int,
    T: int,
    B: int = 9,
    C: float = 3.0,
    seed: int = 42,
    p0: float = 100.0,
    history_mode: str = "endogenous",
    decision_mode: str = "strategy",
    random_open_prob: float = 0.5,
    order_size_buckets: tuple[int, int] = (50, 100),
) -> dict:
    assert history_mode in ("endogenous", "exogenous")
    assert decision_mode in ("strategy", "random")
    small_max, medium_max = int(order_size_buckets[0]), int(order_size_buckets[1])
    assert small_max < medium_max, "order_size_buckets must be (small_max, medium_max) with small_max < medium_max"
    K = mu_capacity(M)
    rng = np.random.default_rng(seed)

    # --- §7.1 初期化 ---
    strategies = rng.choice([-1, 0, 1], size=(N, S, K)).astype(np.int8)
    init_u100 = rng.integers(0, 100, size=N)
    init_active = rng.integers(0, S, size=N).astype(np.int64)
    mu0 = int(rng.integers(0, K))

    # --- 状態配列 ---
    G = np.zeros((N, S), dtype=np.int64)
    w = (int(B) + init_u100).astype(np.int64)
    active_idx = init_active
    position = np.zeros(N, dtype=np.int8)
    entry_price = np.zeros(N, dtype=np.int64)
    entry_action = np.zeros(N, dtype=np.int8)
    entry_quantity = np.zeros(N, dtype=np.int64)
    entry_step = np.zeros(N, dtype=np.int64)
    v_pos = np.zeros((N, S), dtype=np.int8)
    v_ep = np.zeros((N, S), dtype=np.int64)
    v_ea = np.zeros((N, S), dtype=np.int8)

    mu = mu0
    P = 0
    p = float(p0)

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

    # round-trip event log (per-close append; converted at return)
    rt_agent_idx: list[int] = []
    rt_open_t: list[int] = []
    rt_close_t: list[int] = []
    rt_entry_action: list[int] = []
    rt_entry_quantity: list[int] = []
    rt_delta_G: list[int] = []

    arange_N = np.arange(N)

    for t in range(T):
        mu_t = mu  # snapshot

        # 1) 意思決定
        if decision_mode == "strategy":
            recs = strategies[arange_N, active_idx, mu_t]  # (N,) int8
            recs = recs.astype(np.int8, copy=True)
        else:  # 'random' — 参照版と同じ per-agent 順序で RNG を消費
            recs = np.zeros(N, dtype=np.int8)
            for i in range(N):
                u = rng.random()
                if u < random_open_prob:
                    d = rng.random()
                    recs[i] = 1 if d < 0.5 else -1

        # 2) effective action 表 (§3.8) — マスクベクトル化
        is_open_mask = (position == 0) & (recs != 0)
        is_close_mask = (position != 0) & (recs == -position)
        is_active_hold_mask = (position != 0) & (recs == 0)
        is_passive_hold_mask = (position != 0) & (recs == position)

        effective = np.zeros(N, dtype=np.int64)
        quantity = np.zeros(N, dtype=np.int64)
        effective[is_open_mask] = recs[is_open_mask]
        quantity[is_open_mask] = w[is_open_mask] // B
        effective[is_close_mask] = recs[is_close_mask]
        quantity[is_close_mask] = entry_quantity[is_close_mask]

        # 3) 市場集計
        D = int((effective * quantity).sum())
        dp = D / N
        p += dp

        # 4) 量子化 + 履歴 + 認知価格
        h = quantize_price_change(dp, C)
        P += h
        if history_mode == "endogenous":
            mu = shift_in(mu, h + 2, M)
        else:
            mu = int(rng.integers(0, K))

        # 5) close 実行 — 状態クリア前に round_trips レコードを append (agent_idx 昇順)
        close_idx = np.where(is_close_mask)[0]
        if close_idx.size:
            dG = entry_action[close_idx].astype(np.int64) * (P - entry_price[close_idx])
            rt_agent_idx.extend(close_idx.tolist())
            rt_open_t.extend(entry_step[close_idx].tolist())
            rt_close_t.extend([t] * close_idx.size)
            rt_entry_action.extend(entry_action[close_idx].tolist())
            rt_entry_quantity.extend(entry_quantity[close_idx].tolist())
            rt_delta_G.extend(dG.tolist())
            # G[i, active_idx[i]] += dG_i  (各 i は distinct なので直接 += で安全、ただし
            # 可読性のため np.add.at を使用)
            np.add.at(G, (close_idx, active_idx[close_idx]), dG)
            w[close_idx] += dG * entry_quantity[close_idx]
            position[close_idx] = 0
            entry_price[close_idx] = 0
            entry_action[close_idx] = 0
            entry_quantity[close_idx] = 0
            entry_step[close_idx] = 0

        # 6) open 実行
        open_idx = np.where(is_open_mask)[0]
        if open_idx.size:
            position[open_idx] = effective[open_idx].astype(np.int8)
            entry_price[open_idx] = P
            entry_action[open_idx] = effective[open_idx].astype(np.int8)
            entry_quantity[open_idx] = quantity[open_idx]
            entry_step[open_idx] = t

        # 7) virtual 更新 (j != active_idx)
        #    recs_all[i, j] = strategies[i, j, mu_t]  (全 N, S)
        recs_all = strategies[:, :, mu_t]  # (N, S) int8
        not_active = np.ones((N, S), dtype=bool)
        not_active[arange_N, active_idx] = False

        # virtual open: v_pos==0 and rec!=0 and not_active
        v_open_mask = (v_pos == 0) & (recs_all != 0) & not_active
        if v_open_mask.any():
            vals = recs_all[v_open_mask]
            v_pos[v_open_mask] = vals
            v_ep[v_open_mask] = P
            v_ea[v_open_mask] = vals

        # virtual close: v_pos!=0 and rec == -v_pos and not_active
        v_close_mask = (v_pos != 0) & (recs_all == -v_pos) & not_active
        if v_close_mask.any():
            close_i, close_j = np.where(v_close_mask)
            dG_v = v_ea[close_i, close_j].astype(np.int64) * (P - v_ep[close_i, close_j])
            np.add.at(G, (close_i, close_j), dG_v)
            v_pos[v_close_mask] = 0
            v_ep[v_close_mask] = 0
            v_ea[v_close_mask] = 0

        # 8) 戦略レビュー + 破産判定 (close 起きた i を index 順)
        for i in close_idx:
            i = int(i)
            g_max = int(G[i].max())
            best = np.flatnonzero(G[i] == g_max)
            if active_idx[i] not in best:
                new_idx = int(rng.choice(best))
                v_pos[i, new_idx] = 0
                v_ep[i, new_idx] = 0
                v_ea[i, new_idx] = 0
                active_idx[i] = new_idx
            if w[i] < B:
                new_strategies = rng.choice([-1, 0, 1], size=(S, K)).astype(np.int8)
                new_w = int(B) + int(rng.integers(0, 100))
                new_active = int(rng.integers(0, S))
                strategies[i] = new_strategies
                w[i] = new_w
                active_idx[i] = new_active
                position[i] = 0
                entry_price[i] = 0
                entry_action[i] = 0
                entry_quantity[i] = 0
                entry_step[i] = 0
                v_pos[i] = 0
                v_ep[i] = 0
                v_ea[i] = 0
                G[i] = 0
                num_substitutions += 1

        # 9) 統計記録
        prices[t] = p
        h_series[t] = h
        cognitive_prices[t] = P
        buy_mask_t = (effective == 1)
        sell_mask_t = (effective == -1)
        num_buy_log[t] = int(buy_mask_t.sum())
        num_sell_log[t] = int(sell_mask_t.sum())
        num_active_hold_log[t] = int(is_active_hold_mask.sum())
        num_passive_hold_log[t] = int(is_passive_hold_mask.sum())
        buy_q = quantity[buy_mask_t]
        sell_q = quantity[sell_mask_t]
        num_orders_by_size_buy[t, 0] = int((buy_q <= small_max).sum())
        num_orders_by_size_buy[t, 1] = int(((buy_q > small_max) & (buy_q <= medium_max)).sum())
        num_orders_by_size_buy[t, 2] = int((buy_q > medium_max).sum())
        num_orders_by_size_sell[t, 0] = int((sell_q <= small_max).sum())
        num_orders_by_size_sell[t, 1] = int(((sell_q > small_max) & (sell_q <= medium_max)).sum())
        num_orders_by_size_sell[t, 2] = int((sell_q > medium_max).sum())

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
        "final_wealth": w.copy(),
        "num_substitutions": num_substitutions,
        "num_buy": num_buy_log,
        "num_sell": num_sell_log,
        "num_active_hold": num_active_hold_log,
        "num_passive_hold": num_passive_hold_log,
        "total_wealth": int(w.sum()),
        "round_trips": round_trips,
        "num_orders_by_size": num_orders_by_size,
        "num_orders_by_size_buy": num_orders_by_size_buy,
        "num_orders_by_size_sell": num_orders_by_size_sell,
    }
