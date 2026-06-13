"""sim 結果 → Brief §2.1 / §2.2 / §2.3 parquet 3 種への変換.

aggregate (simulate_aggregate) と LOB (PAMS runner + SpeculationAgent) の両世界を
共通 schema に揃える。

Brief §2.1 RT 単位: agent_id, rt_idx, t_open, t_close, horizon, direction, q,
                    w_open, w_close, delta_g, cond, seed
Brief §2.2 agent 単位: agent_id, birth_step, retire_step, lifetime, w_init, w_final,
                        forced_retired, lifetime_capped, n_round_trips, cond, seed
                        (S2 plan v2 修正 3: lifetime は agent identity reset 間隔。
                         1 agent_id が複数 lifetime sample を生むため、本 schema は
                         「最初の lifetime」を載せ、複数 sample は別 (agent_id,
                         lifetime_idx) の long-format でも書く)
Brief §2.3 wealth_ts: t, agent_id, w, is_active, cond, seed
                       (S2 plan v2 修正 5: is_active は両世界で hardcoded True、
                        SOSG (YH007) 用 reservation)
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# RT 単位 (Brief §2.1)
# ---------------------------------------------------------------------------

def round_trips_to_df(
    round_trips: Dict[str, np.ndarray],
    cond: str,
    seed: int,
    agent_w_init: Dict[int, int],
    substitute_events: List[Tuple[int, int, int, int]] = (),
) -> pd.DataFrame:
    """round_trips dict を RT 単位 DataFrame に変換 + w_open/w_close を post-hoc 再構成。

    w_open[k] = agent の k 番目 RT 開始時の sg_wealth (substitute イベント考慮)
    w_close[k] = k 番目 RT close 後の sg_wealth (= w_open[k] + delta_g[k] * q[k])
    substitute イベント (t, agent_idx, dead_w, new_w) が与えられれば、
    その agent の以降の RT は新 wealth から累積。
    """
    n_rt = int(round_trips["close_t"].size)
    if n_rt == 0:
        return pd.DataFrame(columns=[
            "agent_id", "rt_idx", "t_open", "t_close", "horizon",
            "direction", "q", "w_open", "w_close", "delta_g", "cond", "seed",
        ])

    df = pd.DataFrame({
        "agent_id": np.asarray(round_trips["agent_idx"], dtype=np.int64),
        "t_open": np.asarray(round_trips["open_t"], dtype=np.int64),
        "t_close": np.asarray(round_trips["close_t"], dtype=np.int64),
        "horizon": (np.asarray(round_trips["close_t"], dtype=np.int64)
                    - np.asarray(round_trips["open_t"], dtype=np.int64)),
        "direction": np.asarray(round_trips["entry_action"], dtype=np.int8),
        "q": np.asarray(round_trips["entry_quantity"], dtype=np.int64),
        "delta_g": np.asarray(round_trips["delta_G"], dtype=np.float64),
    })
    df = df.sort_values(["agent_id", "t_open"], kind="stable").reset_index(drop=True)
    df["rt_idx"] = df.groupby("agent_id").cumcount()

    # substitute_events を agent ごとに sort (t 昇順)
    sub_by_agent: Dict[int, List[Tuple[int, int, int, int]]] = {}
    for ev in substitute_events:
        t, aid, dead_w, new_w = ev
        sub_by_agent.setdefault(int(aid), []).append((int(t), int(aid), int(dead_w), int(new_w)))
    for aid in sub_by_agent:
        sub_by_agent[aid].sort(key=lambda x: x[0])

    w_open_arr = np.zeros(len(df), dtype=np.float64)
    w_close_arr = np.zeros(len(df), dtype=np.float64)

    for aid, idx in df.groupby("agent_id").groups.items():
        idx_arr = idx.to_numpy()
        w_running = float(agent_w_init.get(int(aid), float("nan")))
        if not np.isfinite(w_running):
            w_open_arr[idx_arr] = np.nan
            w_close_arr[idx_arr] = np.nan
            continue
        sub_q: List[Tuple[int, int, int, int]] = list(sub_by_agent.get(int(aid), []))
        sub_iter = iter(sub_q)
        next_sub = next(sub_iter, None)
        for ridx in idx_arr:
            t_open = int(df.at[ridx, "t_open"])
            # この RT 開始前に発生した substitute を全部消化
            while next_sub is not None and next_sub[0] < t_open:
                w_running = float(next_sub[3])  # new_w
                next_sub = next(sub_iter, None)
            w_open_arr[ridx] = w_running
            dG = float(df.at[ridx, "delta_g"])
            q = float(df.at[ridx, "q"])
            w_running = w_running + dG * q
            w_close_arr[ridx] = w_running

    df["w_open"] = w_open_arr
    df["w_close"] = w_close_arr
    df["cond"] = cond
    df["seed"] = int(seed)
    return df[[
        "agent_id", "rt_idx", "t_open", "t_close", "horizon",
        "direction", "q", "w_open", "w_close", "delta_g", "cond", "seed",
    ]]


# ---------------------------------------------------------------------------
# agent 単位 (Brief §2.2)
# ---------------------------------------------------------------------------

def agents_to_df(
    cond: str,
    seed: int,
    N_total: int,
    w_init: np.ndarray,
    final_wealth: np.ndarray,
    rt_df: pd.DataFrame,
    substitute_events: List[Tuple[int, int, int, int]],
    T_total: int,
    forced_retired_flags: Dict[int, bool] = None,
    lifetime_capped_flags: Dict[int, bool] = None,
) -> pd.DataFrame:
    """agent 単位 DataFrame (Brief §2.2)。

    S2 plan v2 修正 3: lifetime は「最初の identity reset 間隔」を schema 値に入れ、
    複数 sample は agent_lifetime_samples_to_df() で別 long-format に書く。
    1 度も substitute されない agent は lifetime = T_total (censored sample)。
    """
    if forced_retired_flags is None:
        forced_retired_flags = {}
    if lifetime_capped_flags is None:
        lifetime_capped_flags = {}

    sub_by_agent: Dict[int, List[int]] = {}
    for ev in substitute_events:
        t, aid, _dw, _nw = ev
        sub_by_agent.setdefault(int(aid), []).append(int(t))
    for aid in sub_by_agent:
        sub_by_agent[aid].sort()

    n_rt_per_agent = (
        rt_df.groupby("agent_id").size().reindex(np.arange(N_total), fill_value=0)
        if len(rt_df) > 0 else pd.Series(0, index=np.arange(N_total))
    )

    rows = []
    for aid in range(N_total):
        subs = sub_by_agent.get(aid, [])
        if subs:
            birth = 0
            retire = subs[0]
            lifetime = retire - birth
            forced_retired = True   # bankruptcy substitute → wealth < B 退場
        else:
            birth = 0
            retire = int(T_total)
            lifetime = int(T_total)
            forced_retired = False
        rows.append({
            "agent_id": int(aid),
            "birth_step": int(birth),
            "retire_step": int(retire),
            "lifetime": int(lifetime),
            "w_init": float(w_init[aid]) if aid < len(w_init) else float("nan"),
            "w_final": float(final_wealth[aid]) if aid < len(final_wealth) else float("nan"),
            "forced_retired": bool(forced_retired_flags.get(aid, forced_retired)),
            "lifetime_capped": bool(lifetime_capped_flags.get(aid, False)),
            "n_round_trips": int(n_rt_per_agent.get(aid, 0)),
            "cond": cond,
            "seed": int(seed),
        })
    return pd.DataFrame(rows)


def agent_lifetime_samples_to_df(
    cond: str,
    seed: int,
    N_total: int,
    substitute_events: List[Tuple[int, int, int, int]],
    T_total: int,
) -> pd.DataFrame:
    """1 trial × N_total agent の全 lifetime sample を long-format で返す.

    S2 plan v2 修正 3: 1 agent_id が複数 lifetime sample を生む。
    各 sample に censored bool flag を立てる (sim 終了時生存 = censored)。
    """
    sub_by_agent: Dict[int, List[int]] = {}
    for ev in substitute_events:
        t, aid, _dw, _nw = ev
        sub_by_agent.setdefault(int(aid), []).append(int(t))
    for aid in sub_by_agent:
        sub_by_agent[aid].sort()

    rows = []
    for aid in range(N_total):
        subs = sub_by_agent.get(aid, [])
        prev = 0
        for t_sub in subs:
            rows.append({
                "agent_id": int(aid),
                "sample_idx": len([r for r in rows if r["agent_id"] == aid]),
                "t_birth": int(prev),
                "t_end": int(t_sub),
                "lifetime": int(t_sub - prev),
                "censored": False,
                "cond": cond, "seed": int(seed),
            })
            prev = t_sub
        # 最後の生存 segment (sim 終了まで)
        rows.append({
            "agent_id": int(aid),
            "sample_idx": len([r for r in rows if r["agent_id"] == aid]),
            "t_birth": int(prev),
            "t_end": int(T_total),
            "lifetime": int(T_total - prev),
            "censored": True,
            "cond": cond, "seed": int(seed),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# wealth time-series (Brief §2.3)
# ---------------------------------------------------------------------------

def wealth_ts_to_df(
    cond: str,
    seed: int,
    snapshots: List[Tuple[int, np.ndarray]],
) -> pd.DataFrame:
    """wealth_snapshots を long-format DataFrame に変換.

    is_active は S2 plan v2 修正 5 で hardcoded True (SOSG 用 reservation)。
    """
    rows = []
    for t, w_arr in snapshots:
        N = len(w_arr)
        for aid in range(N):
            rows.append({
                "t": int(t),
                "agent_id": int(aid),
                "w": float(w_arr[aid]),
                "is_active": True,   # S2 plan v2 修正 5: hardcoded、SOSG (YH007) 用 reservation
                "cond": cond, "seed": int(seed),
            })
    return pd.DataFrame(rows)
