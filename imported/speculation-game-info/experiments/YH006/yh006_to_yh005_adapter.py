"""PAMS 実行結果 → YH005 simulate() 互換 dict 変換.

YH005/simulate.py 返り dict schema (src: experiments/YH005/simulate.py:238-253):
  prices, h_series, cognitive_prices, final_wealth, num_substitutions,
  num_buy, num_sell, num_active_hold, num_passive_hold, total_wealth,
  round_trips={agent_idx, open_t, close_t, entry_action, entry_quantity, delta_G},
  num_orders_by_size, num_orders_by_size_buy, num_orders_by_size_sell

本 adapter は PAMS の runner + saver + SG agent 群から、main session (session 1)
部分のみを切り出して YH005 互換 dict を返す。warmup (session 0) は破棄する。

wealth / order-size の集計方針:
- C2/C3 (SG あり): SG cognitive wealth (sg_wealth) を使う。order-size は
  SG agent の submit_log を使う (SG 注文のサイズ分布が本題)。
- C1 (SG 無し): SG agents が空なので final_wealth は FCN agents の
  LOB mtm (cash + asset × last_mid) を使う (YH005 の cognitive 比較は
  N/A)。order-size は OrderTrackingSaver.order_logs から全 order を集計。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from speculation_agent import SpeculationAgent


def _collect_main_session_prices(market_step_logs: List[Dict], warmup_steps: int) -> Tuple[np.ndarray, np.ndarray]:
    """main session の (market_time, market_price) を抽出。単一市場前提."""
    filt = [log for log in market_step_logs if log["market_time"] >= warmup_steps]
    if not filt:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.int64)
    sorted_logs = sorted(filt, key=lambda x: x["market_time"])
    times = np.asarray([log["market_time"] for log in sorted_logs], dtype=np.int64)
    prices = np.asarray([log["market_price"] for log in sorted_logs], dtype=np.float64)
    return prices, times


def build_yh005_compatible_dict(
    runner: Any,
    saver: Any,
    warmup_steps: int,
    main_steps: int,
    order_size_buckets: Tuple[int, int] = (50, 100),
) -> Dict[str, Any]:
    """Main session のデータだけを YH005 形式 dict に整形して返す。"""

    prices, times = _collect_main_session_prices(saver.market_step_logs, warmup_steps)
    # YH005 は index 0 = t=0 で連続. PAMS では warmup + main step で t=warmup_steps.
    # ここでは main session の (len=main_steps) を取り出す。
    # times は warmup_steps..warmup_steps+main_steps-1 になるはず。
    T = int(prices.size)

    sg_agents: List[SpeculationAgent] = [
        a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)
    ]
    N_sg = len(sg_agents)

    # --- cognitive history ---
    hist_state = None
    if hasattr(runner.simulator, "_yh006_history"):
        # 単一 market 前提
        store = runner.simulator._yh006_history
        if store:
            hist_state = next(iter(store.values()))

    if hist_state is not None:
        full_h_series = np.asarray(hist_state.h_series, dtype=np.int8)
        # main session 部分 (warmup_steps..warmup_steps+main_steps-1) を切り出す
        h_main = full_h_series[warmup_steps:warmup_steps + T] if full_h_series.size >= warmup_steps + T else \
                 full_h_series[warmup_steps:]
        h_series = np.zeros(T, dtype=np.int8)
        h_series[:h_main.size] = h_main
        # cumulative P
        cognitive_prices = np.cumsum(h_series.astype(np.int64))
    else:
        h_series = np.zeros(T, dtype=np.int8)
        cognitive_prices = np.zeros(T, dtype=np.int64)

    # --- per-step action aggregations (num_buy / num_sell / num_active_hold / num_passive_hold) ---
    num_buy = np.zeros(T, dtype=np.int64)
    num_sell = np.zeros(T, dtype=np.int64)
    num_active_hold = np.zeros(T, dtype=np.int64)
    num_passive_hold = np.zeros(T, dtype=np.int64)
    # order size buckets: per step, signed_qty from submit_log
    small_max, medium_max = order_size_buckets
    num_orders_buy = np.zeros((T, 3), dtype=np.int64)
    num_orders_sell = np.zeros((T, 3), dtype=np.int64)

    for a in sg_agents:
        for (t, label) in a.action_log:
            t_rel = t - warmup_steps
            if t_rel < 0 or t_rel >= T:
                continue
            if label == "buy":
                num_buy[t_rel] += 1
            elif label == "sell":
                num_sell[t_rel] += 1
            elif label == "active_hold":
                num_active_hold[t_rel] += 1
            elif label == "passive_hold":
                num_passive_hold[t_rel] += 1
            # "idle" は他のどれにも該当しない、N - (上記 4 つ) として後で復元可
        for (t, signed_q) in a.submit_log:
            t_rel = t - warmup_steps
            if t_rel < 0 or t_rel >= T:
                continue
            q = abs(signed_q)
            bucket = 0 if q <= small_max else (1 if q <= medium_max else 2)
            if signed_q > 0:
                num_orders_buy[t_rel, bucket] += 1
            else:
                num_orders_sell[t_rel, bucket] += 1

    num_orders = num_orders_buy + num_orders_sell

    # C1 (SG 無し) の場合、OrderTrackingSaver.order_logs から FCN 含む全 order を
    # 集計する。saver が order_logs 属性を持つ場合のみ。
    if N_sg == 0 and hasattr(saver, "order_logs") and saver.order_logs:
        for log in saver.order_logs:
            tt = log["time"]
            t_rel = tt - warmup_steps
            if t_rel < 0 or t_rel >= T:
                continue
            vol = int(log["volume"])
            bucket = 0 if vol <= small_max else (1 if vol <= medium_max else 2)
            if log["is_buy"]:
                num_orders_buy[t_rel, bucket] += 1
            else:
                num_orders_sell[t_rel, bucket] += 1
        num_orders = num_orders_buy + num_orders_sell

    # --- round-trip events (main session 以内のもののみ) ---
    all_rt_agent_idx: List[int] = []
    all_rt_open_t: List[int] = []
    all_rt_close_t: List[int] = []
    all_rt_entry_action: List[int] = []
    all_rt_entry_quantity: List[int] = []
    all_rt_delta_G: List[int] = []
    for a in sg_agents:
        for rt in a.round_trips:
            # Only include round-trips wholly inside main session (open and close both >= warmup)
            if rt["open_t"] < warmup_steps or rt["close_t"] < warmup_steps:
                continue
            all_rt_agent_idx.append(rt["agent_idx"])
            all_rt_open_t.append(rt["open_t"] - warmup_steps)
            all_rt_close_t.append(rt["close_t"] - warmup_steps)
            all_rt_entry_action.append(rt["entry_action"])
            all_rt_entry_quantity.append(rt["entry_quantity"])
            all_rt_delta_G.append(rt["delta_G"])

    round_trips = {
        "agent_idx": np.asarray(all_rt_agent_idx, dtype=np.int64),
        "open_t": np.asarray(all_rt_open_t, dtype=np.int64),
        "close_t": np.asarray(all_rt_close_t, dtype=np.int64),
        "entry_action": np.asarray(all_rt_entry_action, dtype=np.int8),
        "entry_quantity": np.asarray(all_rt_entry_quantity, dtype=np.int64),
        "delta_G": np.asarray(all_rt_delta_G, dtype=np.int64),
    }

    # --- wealth ---
    # final_wealth = cash_amount + asset_volumes * mid_price
    # (PAMS では asset_volumes はまさに position。市場 id は単一前提)
    market_ids = list(runner.simulator.id2market.keys()) if hasattr(runner.simulator, "id2market") else []
    if not market_ids and sg_agents:
        # fallback via the first agent
        market_ids = list(sg_agents[0].asset_volumes.keys())
    # SG cognitive wealth (separate from PAMS LOB cash) — comparable to YH005 w
    final_wealth_list: List[int] = []
    lob_mtm_list: List[float] = []
    total_subs = 0
    last_price = float(prices[-1]) if prices.size > 0 else 0.0
    for a in sg_agents:
        total_subs += a.num_substitutions
        final_wealth_list.append(int(a.sg_wealth))
        asset = 0
        for mid in market_ids:
            asset = a.asset_volumes.get(mid, 0)
            break
        lob_mtm_list.append(float(a.cash_amount) + asset * last_price)

    # C1 (SG 無し) の場合、FCN の LOB mtm を wealth として載せる
    wealth_source = "sg_cognitive"
    if not final_wealth_list:
        wealth_source = "lob_mtm_fcn"
        for a in runner.simulator.agents:
            if isinstance(a, SpeculationAgent):
                continue
            asset = 0
            for mid in market_ids:
                asset = a.asset_volumes.get(mid, 0)
                break
            mtm = float(a.cash_amount) + asset * last_price
            final_wealth_list.append(int(round(mtm)))
            lob_mtm_list.append(mtm)
    final_wealth = np.asarray(final_wealth_list, dtype=np.int64)
    total_wealth = int(final_wealth.sum())
    lob_mtm = np.asarray(lob_mtm_list, dtype=np.float64)

    return {
        "prices": prices,
        "h_series": h_series,
        "cognitive_prices": cognitive_prices,
        "final_wealth": final_wealth,
        "num_substitutions": int(total_subs),
        "num_buy": num_buy,
        "num_sell": num_sell,
        "num_active_hold": num_active_hold,
        "num_passive_hold": num_passive_hold,
        "total_wealth": total_wealth,
        "round_trips": round_trips,
        "num_orders_by_size": num_orders,
        "num_orders_by_size_buy": num_orders_buy,
        "num_orders_by_size_sell": num_orders_sell,
        # meta for downstream
        "_meta": {
            "N_sg": N_sg,
            "T": T,
            "warmup_steps": warmup_steps,
            "num_partial_opens": int(sum(a.num_partial_opens for a in sg_agents)),
            "num_partial_closes": int(sum(a.num_partial_closes for a in sg_agents)),
            "num_zero_opens": int(sum(a.num_zero_opens for a in sg_agents)),
            "num_cancels_sent": int(sum(a.num_cancels_sent for a in sg_agents)),
            "close_submits": int(sum(a.close_submits for a in sg_agents)),
            "close_full_matches": int(sum(a.close_full_matches for a in sg_agents)),
            "close_partial_matches": int(sum(a.close_partial_matches for a in sg_agents)),
            "close_cancelled": int(sum(a.close_cancelled for a in sg_agents)),
            "wealth_source": wealth_source,
            "lob_mtm_min": float(lob_mtm.min()) if lob_mtm.size else 0.0,
            "lob_mtm_max": float(lob_mtm.max()) if lob_mtm.size else 0.0,
            "lob_mtm_median": float(np.median(lob_mtm)) if lob_mtm.size else 0.0,
        },
    }
