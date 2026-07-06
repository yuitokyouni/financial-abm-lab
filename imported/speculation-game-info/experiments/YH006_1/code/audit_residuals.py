"""Claim-2 residual judgment — computed from L1 ALONE (+ nothing else).

残差a (phantom) と残差b (整合 + flatten初期化) を L1 DataFrame から閉じる。
L2/L3 を参照しない (硬い制約: claim-2 判定を新規ログ実装の正しさに従属させない)。

中核不変量 (settled 状態 = pending 無し & stale でない step):
    R := pos_post * eq_post  (SG が「自分は持っている」と認識する signed 在庫)
    R == av_pre              (口座A の実在庫、当 step 凍結)
これが破れる = SG が説明できない実在庫 = phantom / desync = 残差a.

残差b:
  (整合)  pos_post != 0 なら sign(pos_post)==sign(av_pre) かつ eq_post==|av_pre|.
  (初期化) pos_post == 0 なら eq_post==ep_post==ea_post==es_post==0.
          「両方たまたま 0 だが内部状態が壊れている」ケースを検出.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def judge(l1: pd.DataFrame, stale_heal_steps: int = 1) -> Dict[str, Any]:
    """L1 から残差 a/b を判定し verdict dict を返す."""
    if l1.empty:
        return {"verdict": "NO_DATA", "n_records": 0}

    df = l1.sort_values(["agent_id", "market_id", "t"], kind="stable").reset_index(drop=True)
    R = df["pos_post"].to_numpy() * df["eq_post"].to_numpy()
    av = df["av_pre"].to_numpy()
    settled = (df["pend_post"].to_numpy() == "none") & (~df["stale_issued"].to_numpy())

    # ---- 残差a: settled なのに R != av_pre (phantom / desync) ----
    resid_a_mask = settled & (R != av)
    resid_a = df[resid_a_mask].copy()
    resid_a["R"] = R[resid_a_mask]

    # ---- 残差a': stale が 1 step で癒えているか (per agent-market の連続性) ----
    stale_unhealed = []
    for (aid, mkt), g in df.groupby(["agent_id", "market_id"]):
        g = g.reset_index(drop=True)
        st = g["stale_issued"].to_numpy()
        avg = g["av_pre"].to_numpy()
        for i in np.flatnonzero(st):
            # stale を出した step の次の観測で実在庫が 0 に向かって解消されるべき
            if i + stale_heal_steps < len(g):
                if avg[i + stale_heal_steps] != 0 and st[i + stale_heal_steps]:
                    stale_unhealed.append((int(aid), int(mkt), int(g["t"].iloc[i])))

    # ---- 残差b(整合): SETTLED かつ pos_post != 0 で sign/qty が実在庫と不一致 ----
    # (pending open/close 中は position と実在庫が一致しないのが正常なので settled に限定)
    nz = df["pos_post"].to_numpy() != 0
    sign_ok = np.sign(df["pos_post"].to_numpy()) == np.sign(av)
    qty_ok = df["eq_post"].to_numpy() == np.abs(av)
    resid_b_consist_mask = settled & nz & (~(sign_ok & qty_ok))
    resid_b_consist = df[resid_b_consist_mask]

    # ---- 残差b(初期化): SETTLED flat (pend なし & pos==0) なのに内部状態が非ゼロ ----
    # (pending open を出した step は position=0 のまま entry_action/price を先にセット
    #  するのが正常。これを除外するため pend_post=="none" を必須にする)
    zp = (df["pos_post"].to_numpy() == 0) & (df["pend_post"].to_numpy() == "none")
    dirty = zp & (
        (df["eq_post"].to_numpy() != 0)
        | (df["ep_post"].to_numpy() != 0)
        | (df["ea_post"].to_numpy() != 0)
        | (df["es_post"].to_numpy() != 0)
    )
    resid_b_init = df[dirty]

    n = len(df)
    n_a = int(resid_a_mask.sum())
    n_b_consist = int(resid_b_consist_mask.sum())
    n_b_init = int(dirty.sum())
    n_stale_unhealed = len(stale_unhealed)
    clean = (n_a == 0 and n_b_consist == 0 and n_b_init == 0 and n_stale_unhealed == 0)

    return {
        "verdict": "CLEAN (2口座設計どおり、在庫バグ痕跡なし)" if clean
                   else "DIRTY (実バグの疑い — 下記残差を精査)",
        "n_records": n,
        "n_settled": int(settled.sum()),
        "residual_a_phantom": n_a,
        "residual_a_stale_unhealed": n_stale_unhealed,
        "residual_b_consistency": n_b_consist,
        "residual_b_flatten_init": n_b_init,
        "examples_a": resid_a.head(5).to_dict("records"),
        "examples_b_consist": resid_b_consist.head(5).to_dict("records"),
        "examples_b_init": resid_b_init.head(5).to_dict("records"),
        "stale_unhealed_examples": stale_unhealed[:5],
    }


def print_verdict(v: Dict[str, Any]) -> None:
    print("=" * 74)
    print(f"CLAIM-2 VERDICT: {v['verdict']}")
    print("=" * 74)
    if v.get("n_records", 0) == 0:
        print("  (no L1 records)")
        return
    print(f"  L1 records            : {v['n_records']:,}  (settled: {v['n_settled']:,})")
    print(f"  残差a phantom         : {v['residual_a_phantom']}")
    print(f"  残差a stale未癒着       : {v['residual_a_stale_unhealed']}")
    print(f"  残差b 整合(sign/qty)   : {v['residual_b_consistency']}")
    print(f"  残差b flatten初期化    : {v['residual_b_flatten_init']}")
    for key, lbl in [("examples_a", "phantom"),
                     ("examples_b_consist", "整合違反"),
                     ("examples_b_init", "初期化違反")]:
        ex = v.get(key) or []
        if ex:
            print(f"  --- {lbl} 例 ---")
            for r in ex:
                print(f"      t={r.get('t')} agent={r.get('agent_id')} "
                      f"av_pre={r.get('av_pre')} pos_post={r.get('pos_post')} "
                      f"eq_post={r.get('eq_post')} pend_post={r.get('pend_post')}")
