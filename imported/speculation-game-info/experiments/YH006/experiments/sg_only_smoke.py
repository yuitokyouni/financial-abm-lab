"""(3A) SG-only smoke: FCN=0, SG=500, 1500 step 計測.

計測項目:
- runtime
- open/close submits / full_matches / partial / cancelled の内訳
- Σ(signed q_i) 時系列 (意図された aggregate demand)
- buy/sell open/close 方向別カウント
- Fig A wealth Pareto α (約定が起きれば)
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

HERE = Path(__file__).resolve().parent.parent  # experiments/YH006
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

from pams.runners import SequentialRunner  # noqa: E402

from configs.c3_sg_only import make_config  # noqa: E402
from custom_saver import OrderTrackingSaver  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402


def main() -> None:
    warmup = 100
    main_steps = 1500
    num_sg = 500

    cfg = make_config(
        warmup_steps=warmup, main_steps=main_steps,
        num_sg_agents=num_sg, c_ticks=28.0,
        max_normal_orders=2000,
    )

    saver = OrderTrackingSaver()
    runner = SequentialRunner(
        settings=cfg, prng=random.Random(777), logger=saver,
    )
    runner.class_register(SpeculationAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    print(f"\n=== (3A) SG-only C3 smoke ===")
    print(f"seed=777  num_sg={len(sgs)}  warmup={warmup}  main={main_steps}  runtime={elapsed:.1f}s")

    # Close accounting
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

    print(f"\n--- OPEN ---")
    print(f"open_submits       = {o_sub}")
    print(f"open_full_matches  = {o_full}  ({pct(o_full, o_sub)})")
    print(f"open_partial       = {o_part}  ({pct(o_part, o_sub)})")
    print(f"open_cancelled     = {o_cxl}  ({pct(o_cxl, o_sub)})")

    print(f"\n--- CLOSE ---")
    print(f"close_submits      = {c_sub}")
    print(f"close_full_matches = {c_full}  ({pct(c_full, c_sub)})")
    print(f"close_partial      = {c_part}  ({pct(c_part, c_sub)})")
    print(f"close_cancelled    = {c_cxl}  ({pct(c_cxl, c_sub)})")

    print(f"\nround_trips completed = {rts}")
    print(f"substitutions         = {subs}")
    print(f"self-cancels sent     = {cancels_sent}")

    # Σ(signed q) per step (intended aggregate demand)
    T_total = warmup + main_steps
    sum_s = np.zeros(T_total, dtype=np.int64)
    # buy/sell × open/close counts
    n_buy_open = np.zeros(T_total, dtype=np.int64)
    n_sell_open = np.zeros(T_total, dtype=np.int64)
    n_buy_close = np.zeros(T_total, dtype=np.int64)
    n_sell_close = np.zeros(T_total, dtype=np.int64)

    # We only have submit_log (t, signed_q) — can't distinguish open vs close from that
    # But action_log has labels: "buy" / "sell" — for open OR close (same label)
    # Use order_logs from saver + agents' pending_intent history? Not available post-hoc.
    # Easiest: use submit_log and annotate via a match against entry_step/close_step in round_trips —
    # too much surgery. Instead, just report Σ(signed q) and net counts, not open/close split.
    for a in sgs:
        for (t, signed_q) in a.submit_log:
            if 0 <= t < T_total:
                sum_s[t] += signed_q

    # Stats on Σ(s_i)
    main_slice = sum_s[warmup:]
    print(f"\n--- Σ(signed q_i) per step (main session) ---")
    print(f"mean            = {main_slice.mean():.2f}")
    print(f"std             = {main_slice.std():.2f}")
    print(f"abs median      = {float(np.median(np.abs(main_slice))):.1f}")
    print(f"abs max         = {int(np.abs(main_slice).max())}")
    print(f"fraction of steps with Σ=0: {(main_slice == 0).mean()*100:.1f}%")
    print(f"fraction with |Σ|<=5      : {(np.abs(main_slice) <= 5).mean()*100:.1f}%")

    # Raw buy/sell submits per step from submit_log
    buy_counts = np.zeros(T_total, dtype=np.int64)
    sell_counts = np.zeros(T_total, dtype=np.int64)
    for a in sgs:
        for (t, signed_q) in a.submit_log:
            if 0 <= t < T_total:
                if signed_q > 0:
                    buy_counts[t] += 1
                else:
                    sell_counts[t] += 1
    print(f"\n--- buy / sell submits per step (main) ---")
    print(f"buy/step  mean={buy_counts[warmup:].mean():.1f}  max={buy_counts[warmup:].max()}")
    print(f"sell/step mean={sell_counts[warmup:].mean():.1f}  max={sell_counts[warmup:].max()}")

    # Save raw series for further inspection
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    result = {
        "runtime_sec": elapsed,
        "num_sg": len(sgs),
        "warmup": warmup,
        "main_steps": main_steps,
        "open_submits": o_sub,
        "open_full_matches": o_full,
        "open_partial": o_part,
        "open_cancelled": o_cxl,
        "close_submits": c_sub,
        "close_full_matches": c_full,
        "close_partial": c_part,
        "close_cancelled": c_cxl,
        "round_trips": rts,
        "num_substitutions": subs,
        "self_cancels_sent": cancels_sent,
        "sum_signed_q_main_mean": float(main_slice.mean()),
        "sum_signed_q_main_std": float(main_slice.std()),
        "sum_signed_q_main_absmed": float(np.median(np.abs(main_slice))),
        "sum_signed_q_main_absmax": int(np.abs(main_slice).max()),
        "frac_zero": float((main_slice == 0).mean()),
    }
    with open(out_dir / "sg_only_smoke.json", "w") as f:
        json.dump(result, f, indent=2)

    # Also pickle sum_s for time-series plotting later if needed
    with open(out_dir / "sg_only_sum_s.pkl", "wb") as f:
        pickle.dump({"sum_s": sum_s, "buy": buy_counts, "sell": sell_counts,
                     "warmup": warmup, "main_steps": main_steps}, f)

    # Fig A Pareto α if enough data
    ws = np.array([a.sg_wealth for a in sgs])
    w_pos = ws[ws > 0]
    if w_pos.size >= 10:
        xmin = float(np.percentile(w_pos, 90))
        tail = w_pos[w_pos >= xmin]
        if tail.size >= 2 and xmin > 0:
            log_ratio = np.log(tail / xmin).mean()
            alpha = 1.0 / log_ratio if log_ratio > 0 else float("nan")
            print(f"\n--- sg_wealth Pareto (N={w_pos.size}) ---")
            print(f"median = {np.median(w_pos):.0f}  max = {int(w_pos.max())}")
            print(f"α_hill (xmin=p90) = {alpha:.3f}  (tail n={tail.size})")
            result["alpha_hill"] = float(alpha) if np.isfinite(alpha) else None
            result["wealth_median"] = float(np.median(w_pos))
            result["wealth_max"] = float(w_pos.max())
            with open(out_dir / "sg_only_smoke.json", "w") as f:
                json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
