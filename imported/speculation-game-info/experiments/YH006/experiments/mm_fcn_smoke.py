"""(3B) MM-FCN + SG smoke: 500 SG × 1500 step × seed=777 で判定.

判定基準:
  - open 約定率 > 50%
  - close 約定率 > 50%
  - Σ(s_i) std > 0 (stuck しない)
  - runtime < 60s
  - wealth 分布が変動 (min/median/max が初期値から動く)

全て満たせば full run へ進む材料になる。
"""

from __future__ import annotations

import json
import pickle
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

from pams.runners import SequentialRunner  # noqa: E402

from configs.c3 import make_config  # noqa: E402
from custom_saver import OrderTrackingSaver  # noqa: E402
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402


def main() -> None:
    # Smoke は scope 縮小して短時間で判定する。健全なら full run でスケールアップ。
    warmup = 100
    main_steps = 500
    num_sg = 100
    num_fcn = 30

    cfg = make_config(
        warmup_steps=warmup, main_steps=main_steps,
        num_sg_agents=num_sg, c_ticks=28.0,
        max_normal_orders=2000,
    )
    cfg["FCNAgents"]["numAgents"] = num_fcn

    saver = OrderTrackingSaver()
    runner = SequentialRunner(
        settings=cfg, prng=random.Random(777), logger=saver,
    )
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    o_sub = sum(a.open_submits for a in sgs)
    o_full = sum(a.open_full_matches for a in sgs)
    o_part = sum(a.open_partial_matches for a in sgs)
    o_cxl = sum(a.open_cancelled for a in sgs)
    c_sub = sum(a.close_submits for a in sgs)
    c_full = sum(a.close_full_matches for a in sgs)
    c_part = sum(a.close_partial_matches for a in sgs)
    c_cxl = sum(a.close_cancelled for a in sgs)
    cancels_sent = sum(a.num_cancels_sent for a in sgs)
    rts = sum(len(a.round_trips) for a in sgs)
    subs = sum(a.num_substitutions for a in sgs)

    def pct(x, total):
        return f"{x/max(total,1)*100:.1f}%"

    print(f"\n=== (3B) MM-FCN + SG C3 smoke ===")
    print(f"seed=777  num_sg={num_sg}  num_fcn={num_fcn}  warmup={warmup}  main={main_steps}")
    print(f"runtime = {elapsed:.1f}s")
    print(f"\n--- OPEN ---")
    print(f"open_submits      = {o_sub}")
    print(f"open_full_matches = {o_full}  ({pct(o_full, o_sub)})")
    print(f"open_partial      = {o_part}  ({pct(o_part, o_sub)})")
    print(f"open_cancelled    = {o_cxl}  ({pct(o_cxl, o_sub)})")
    print(f"\n--- CLOSE ---")
    print(f"close_submits     = {c_sub}")
    print(f"close_full_matches= {c_full}  ({pct(c_full, c_sub)})")
    print(f"close_partial     = {c_part}  ({pct(c_part, c_sub)})")
    print(f"close_cancelled   = {c_cxl}  ({pct(c_cxl, c_sub)})")
    print(f"\nround_trips       = {rts}")
    print(f"substitutions     = {subs}")
    print(f"self-cancels sent = {cancels_sent}")

    # Σ(signed q_i) per step
    T_total = warmup + main_steps
    sum_s = np.zeros(T_total, dtype=np.int64)
    buy_counts = np.zeros(T_total, dtype=np.int64)
    sell_counts = np.zeros(T_total, dtype=np.int64)
    for a in sgs:
        for (t, signed_q) in a.submit_log:
            if 0 <= t < T_total:
                sum_s[t] += signed_q
                if signed_q > 0:
                    buy_counts[t] += 1
                else:
                    sell_counts[t] += 1
    main_slice = sum_s[warmup:]
    main_buy = buy_counts[warmup:]
    main_sell = sell_counts[warmup:]
    print(f"\n--- Σ(signed q_i) per step (main) ---")
    print(f"mean   = {main_slice.mean():.2f}")
    print(f"std    = {main_slice.std():.2f}")
    print(f"abs median = {float(np.median(np.abs(main_slice))):.1f}")
    print(f"abs max    = {int(np.abs(main_slice).max())}")
    print(f"frac Σ=0   = {(main_slice == 0).mean()*100:.1f}%")
    print(f"buy/step  mean={main_buy.mean():.1f}  max={main_buy.max()}")
    print(f"sell/step mean={main_sell.mean():.1f}  max={main_sell.max()}")

    # wealth
    ws = np.array([a.sg_wealth for a in sgs])
    w_pos = ws[ws > 0]
    print(f"\n--- sg_wealth ---")
    print(f"N={ws.size}  min={ws.min()}  median={float(np.median(ws)):.0f}  max={int(ws.max())}")
    alpha = float("nan")
    if w_pos.size >= 10:
        xmin = float(np.percentile(w_pos, 90))
        tail = w_pos[w_pos >= xmin]
        if tail.size >= 2 and xmin > 0:
            log_ratio = np.log(tail / xmin).mean()
            alpha = 1.0 / log_ratio if log_ratio > 0 else float("nan")
    print(f"α_hill(xmin=p90) = {alpha:.3f}")

    # Judgment
    print(f"\n=== JUDGMENT (target thresholds) ===")
    o_rate = o_full / max(o_sub, 1)
    c_rate = c_full / max(c_sub, 1)
    ok_open = o_rate > 0.50
    ok_close = c_rate > 0.50 if c_sub > 0 else False
    ok_std = main_slice.std() > 0
    ok_runtime = elapsed < 60.0
    ok_wealth = ws.min() != ws.max()  # 変動している
    print(f"  open 約定率 > 50%       : {pct(o_full, o_sub)}  [{'PASS' if ok_open else 'FAIL'}]")
    print(f"  close 約定率 > 50%      : {pct(c_full, c_sub)}  [{'PASS' if ok_close else 'FAIL'}]")
    print(f"  Σ(s_i) std > 0           : {main_slice.std():.2f}  [{'PASS' if ok_std else 'FAIL'}]")
    print(f"  runtime < 60s            : {elapsed:.1f}s  [{'PASS' if ok_runtime else 'FAIL'}]")
    print(f"  wealth min≠max (変動)    : min={ws.min()} max={ws.max()}  [{'PASS' if ok_wealth else 'FAIL'}]")

    all_pass = ok_open and ok_close and ok_std and ok_runtime and ok_wealth
    print(f"\n=== OVERALL : {'PASS — proceed to full run' if all_pass else 'FAIL — stop and consult'} ===")

    out = {
        "runtime_sec": elapsed,
        "num_sg": num_sg, "num_fcn": num_fcn,
        "warmup": warmup, "main_steps": main_steps,
        "open_submits": o_sub, "open_full_matches": o_full,
        "open_partial": o_part, "open_cancelled": o_cxl,
        "close_submits": c_sub, "close_full_matches": c_full,
        "close_partial": c_part, "close_cancelled": c_cxl,
        "round_trips": rts, "num_substitutions": subs,
        "cancels_sent": cancels_sent,
        "sum_s_mean": float(main_slice.mean()),
        "sum_s_std": float(main_slice.std()),
        "sum_s_absmax": int(np.abs(main_slice).max()),
        "wealth_min": int(ws.min()), "wealth_median": float(np.median(ws)),
        "wealth_max": int(ws.max()),
        "alpha_hill": float(alpha) if np.isfinite(alpha) else None,
        "judgment": {
            "open_rate_ok": bool(ok_open), "close_rate_ok": bool(ok_close),
            "sum_std_ok": bool(ok_std), "runtime_ok": bool(ok_runtime),
            "wealth_ok": bool(ok_wealth), "all_pass": bool(all_pass),
        },
    }
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "mm_fcn_smoke.json", "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
