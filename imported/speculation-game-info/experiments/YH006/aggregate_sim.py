"""YH006 aggregate-demand simulator (YH005 simulate.py の local fork).

目的: 2×2 比較 (world × wealth) の aggregate-demand × {uniform, Pareto} 側
を YH006 内で完結して走らせるための fork。YH005 simulate() は uniform init
をハードコードしており、Pareto 初期 wealth に対応していない。SPEC §9「YH005
を touch しない」制約を保つために YH006 ローカルに複製する。

元: experiments/YH005/simulate.py (参照版 run_reference と bit-parity 済)。
追加: `wealth_mode` ∈ {"uniform", "pareto"} / `pareto_alpha` / `pareto_xmin`。

契約:
- `wealth_mode="uniform"` は YH005 simulate と同じ seed で bit-一致
  (RNG 消費順を完全保持 — init_u100, init_active, mu0 の順も同じ)。
- `wealth_mode="pareto"` は uniform 経路の後に `rng.uniform(N)` を 1 回余分に
  消費する新規 run。parity 対象外。

共通 analysis/ を含め touch しない方針のまま (SPEC §9)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# history encoder は YH005 から read-only で流用
HERE = Path(__file__).resolve().parent
_YH005 = HERE.parent / "YH005"
sys.path.insert(0, str(_YH005))
from history import quantize_price_change, shift_in, mu_capacity  # noqa: E402


def simulate_aggregate(
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
    wealth_mode: str = "uniform",
    pareto_alpha: float = 1.5,
    pareto_xmin: int = 9,
    snapshot_callback: Optional[Callable[[int, np.ndarray], None]] = None,
    log_substitutes: bool = False,
) -> dict:
    """SG decision rule を aggregate-demand 世界で走らせる。

    `wealth_mode="uniform"` は YH005 simulate と同 seed で bit-一致。
    `wealth_mode="pareto"` は inverse-CDF で `w_i = xmin * U_i^{-1/alpha}`
    を初期 wealth に使い、以後は YH005 と同じダイナミクスを走らせる
    (bankruptcy substitute の新 wealth は uniform のまま — YH005 の規約通り)。

    Phase 2 後方互換拡張 (YH006_1 S2 plan v2 修正 1):
      - `snapshot_callback` (default None): 渡された場合、毎 step で
        `t % max(T // 10, 1) == 0` の時に `snapshot_callback(t, w.copy())` を呼ぶ。
        callee 側で wealth_snapshots に追記する想定。RNG state は消費しない (副作用のみ)。
      - `log_substitutes` (default False): True の場合、bankruptcy substitute 発生時に
        `(t, agent_idx, dead_w, new_w)` を返り dict の `substitute_events` キーに追記。
        default False では返り dict に `substitute_events` キーは出ない (= 既存テスト互換)。

    両引数の default 経路は既存挙動と完全 bit-一致。
    """
    assert history_mode in ("endogenous", "exogenous")
    assert decision_mode in ("strategy", "random")
    assert wealth_mode in ("uniform", "pareto")
    small_max, medium_max = int(order_size_buckets[0]), int(order_size_buckets[1])
    assert small_max < medium_max
    K = mu_capacity(M)
    rng = np.random.default_rng(seed)

    # --- §7.1 初期化 (RNG 消費順は YH005 と完全一致) ---
    strategies = rng.choice([-1, 0, 1], size=(N, S, K)).astype(np.int8)
    init_u100 = rng.integers(0, 100, size=N)
    init_active = rng.integers(0, S, size=N).astype(np.int64)
    mu0 = int(rng.integers(0, K))

    # --- 初期 wealth 分岐 (uniform は YH005 と bit-一致、Pareto は追加 RNG 消費) ---
    if wealth_mode == "uniform":
        w = (int(B) + init_u100).astype(np.int64)
    else:  # "pareto"
        u_pareto = rng.uniform(0.0, 1.0, size=N)
        w_float = pareto_xmin * (u_pareto ** (-1.0 / pareto_alpha))
        w = w_float.astype(np.int64)
        w[w < int(B)] = int(B)  # bankruptcy threshold 以下に落ちないよう clamp

    # --- 状態配列 ---
    G = np.zeros((N, S), dtype=np.int64)
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

    rt_agent_idx: list[int] = []
    rt_open_t: list[int] = []
    rt_close_t: list[int] = []
    rt_entry_action: list[int] = []
    rt_entry_quantity: list[int] = []
    rt_delta_G: list[int] = []

    # Phase 2 後方互換拡張 (snapshot_callback / log_substitutes、default は no-op)
    _substitute_events: list[tuple[int, int, int, int]] = []  # (t, agent_idx, dead_w, new_w)
    _snapshot_period = max(T // 10, 1)

    arange_N = np.arange(N)

    for t in range(T):
        mu_t = mu

        # Phase 2 wealth_ts hook: T/10 step ごと (default callback=None で no-op)
        if snapshot_callback is not None and t % _snapshot_period == 0:
            snapshot_callback(t, w.copy())

        if decision_mode == "strategy":
            recs = strategies[arange_N, active_idx, mu_t].astype(np.int8, copy=True)
        else:
            recs = np.zeros(N, dtype=np.int8)
            for i in range(N):
                u = rng.random()
                if u < random_open_prob:
                    d = rng.random()
                    recs[i] = 1 if d < 0.5 else -1

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

        D = int((effective * quantity).sum())
        dp = D / N
        p += dp

        h = quantize_price_change(dp, C)
        P += h
        if history_mode == "endogenous":
            mu = shift_in(mu, h + 2, M)
        else:
            mu = int(rng.integers(0, K))

        close_idx = np.where(is_close_mask)[0]
        if close_idx.size:
            dG = entry_action[close_idx].astype(np.int64) * (P - entry_price[close_idx])
            rt_agent_idx.extend(close_idx.tolist())
            rt_open_t.extend(entry_step[close_idx].tolist())
            rt_close_t.extend([t] * close_idx.size)
            rt_entry_action.extend(entry_action[close_idx].tolist())
            rt_entry_quantity.extend(entry_quantity[close_idx].tolist())
            rt_delta_G.extend(dG.tolist())
            np.add.at(G, (close_idx, active_idx[close_idx]), dG)
            w[close_idx] += dG * entry_quantity[close_idx]
            position[close_idx] = 0
            entry_price[close_idx] = 0
            entry_action[close_idx] = 0
            entry_quantity[close_idx] = 0
            entry_step[close_idx] = 0

        open_idx = np.where(is_open_mask)[0]
        if open_idx.size:
            position[open_idx] = effective[open_idx].astype(np.int8)
            entry_price[open_idx] = P
            entry_action[open_idx] = effective[open_idx].astype(np.int8)
            entry_quantity[open_idx] = quantity[open_idx]
            entry_step[open_idx] = t

        recs_all = strategies[:, :, mu_t]
        not_active = np.ones((N, S), dtype=bool)
        not_active[arange_N, active_idx] = False

        v_open_mask = (v_pos == 0) & (recs_all != 0) & not_active
        if v_open_mask.any():
            vals = recs_all[v_open_mask]
            v_pos[v_open_mask] = vals
            v_ep[v_open_mask] = P
            v_ea[v_open_mask] = vals

        v_close_mask = (v_pos != 0) & (recs_all == -v_pos) & not_active
        if v_close_mask.any():
            close_i, close_j = np.where(v_close_mask)
            dG_v = v_ea[close_i, close_j].astype(np.int64) * (P - v_ep[close_i, close_j])
            np.add.at(G, (close_i, close_j), dG_v)
            v_pos[v_close_mask] = 0
            v_ep[v_close_mask] = 0
            v_ea[v_close_mask] = 0

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
                # Phase 2 substitute logging (default log_substitutes=False で no-op)
                if log_substitutes:
                    _substitute_events.append((int(t), int(i), int(w[i]), int(new_w)))
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

    out = {
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
    # Phase 2 後方互換: log_substitutes=True の時だけ追加 key を出す
    if log_substitutes:
        out["substitute_events"] = _substitute_events
    return out
