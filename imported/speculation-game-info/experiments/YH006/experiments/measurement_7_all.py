"""計測 7 の C1/C2/C3 並列実行 + C3 の variance decomposition (a)(b)(c).

3 条件:
  C1: MM-FCN only (SG=0) — FCN baseline, FCN substitute は 0 のはず
  C2: MM-FCN + SG uniform wealth (100 SG)
  C3: MM-FCN + SG Pareto wealth (100 SG)

各条件で計測:
  (i)   substitute rate per agent-step
  (ii)  wealth injection rate
  (iii) mean lifetime = N × T / total_subs

C3 で追加:
  (a) realized P&L variance from round_trips
  (b) partial fill 相関 (proxy: ratio of partial events to round-trips)
  (c) mark-to-market variance proxy: 累積 |position| × |Δmid|
"""

from __future__ import annotations

import json
import random
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict

warnings.filterwarnings("ignore", category=UserWarning)

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

from pams.runners import SequentialRunner  # noqa: E402

from configs.c1 import make_config as c1_config  # noqa: E402
from configs.c2 import make_config as c2_config  # noqa: E402
from configs.c3 import make_config as c3_config  # noqa: E402
from custom_saver import OrderTrackingSaver  # noqa: E402
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from speculation_agent import SpeculationAgent  # noqa: E402

WARMUP = 100
MAIN_STEPS = 600
NUM_SG = 100
NUM_FCN = 30
SEED = 777

YH005_1 = {
    "N": 1000, "T": 50000,
    "num_substitutions": 102087,
    "subst_rate": 102087 / (1000 * 50000),
    "mean_lifetime": (1000 * 50000) / 102087,
}


def run_condition(cond: str) -> Dict[str, Any]:
    if cond == "C1":
        cfg = c1_config(warmup_steps=WARMUP, main_steps=MAIN_STEPS, max_normal_orders=2000)
    elif cond == "C2":
        cfg = c2_config(warmup_steps=WARMUP, main_steps=MAIN_STEPS,
                        num_sg_agents=NUM_SG, c_ticks=28.0, max_normal_orders=2000)
    elif cond == "C3":
        cfg = c3_config(warmup_steps=WARMUP, main_steps=MAIN_STEPS,
                        num_sg_agents=NUM_SG, c_ticks=28.0, max_normal_orders=2000)
    else:
        raise ValueError(cond)
    cfg["FCNAgents"]["numAgents"] = NUM_FCN

    saver = OrderTrackingSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(SEED), logger=saver)
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]
    n_sg = len(sgs)

    # Substitute events (main session only)
    sub_events = []
    for a in sgs:
        for (t, dead_w, new_w) in a.substitute_events:
            if t >= WARMUP:
                sub_events.append((a.agent_id, t, dead_w, new_w))
    n_subs = len(sub_events)

    # (i) substitute rate
    if n_sg > 0:
        rate_main = n_subs / (n_sg * MAIN_STEPS)
    else:
        rate_main = 0.0

    # (ii) wealth injection
    if sub_events:
        injection_total = sum(new_w - dead_w for (_, _, dead_w, new_w) in sub_events)
        injection_per_step = injection_total / MAIN_STEPS
        per_event = injection_total / len(sub_events)
        dead_ws = [e[2] for e in sub_events]
        new_ws = [e[3] for e in sub_events]
        dead_stats = (min(dead_ws), float(np.mean(dead_ws)), max(dead_ws))
        new_stats = (min(new_ws), float(np.mean(new_ws)), max(new_ws))
    else:
        injection_total = 0
        injection_per_step = 0.0
        per_event = None
        dead_stats = (None, None, None)
        new_stats = (None, None, None)

    # Σ(signed_q) noise
    sum_s = np.zeros(WARMUP + MAIN_STEPS, dtype=np.int64)
    for a in sgs:
        for (t, signed_q) in a.submit_log:
            if 0 <= t < WARMUP + MAIN_STEPS:
                sum_s[t] += signed_q
    main_sum_s = sum_s[WARMUP:]
    sigma_abs_mean = float(np.abs(main_sum_s).mean())
    sigma_std = float(main_sum_s.std())

    # (iii) mean lifetime via N*T/subs
    if n_subs > 0 and n_sg > 0:
        lifetime = n_sg * MAIN_STEPS / n_subs
    else:
        lifetime = float("inf")

    out = {
        "condition": cond,
        "runtime_sec": elapsed,
        "n_sg": n_sg,
        "n_subs_main": n_subs,
        "substitute_rate": rate_main,
        "rate_ratio_vs_yh005_1": (rate_main / YH005_1["subst_rate"]) if rate_main > 0 else None,
        "wealth_injection_total": injection_total,
        "wealth_injection_per_step": injection_per_step,
        "wealth_injection_per_event": per_event,
        "dead_w_min_mean_max": dead_stats,
        "new_w_min_mean_max": new_stats,
        "sigma_abs_mean": sigma_abs_mean,
        "sigma_std": sigma_std,
        "injection_vs_noise": (abs(injection_per_step) / sigma_abs_mean) if sigma_abs_mean > 0 else None,
        "mean_lifetime_step_per_agent": lifetime if lifetime != float("inf") else None,
        "lifetime_ratio_vs_yh005_1": (lifetime / YH005_1["mean_lifetime"]) if lifetime != float("inf") else None,
    }

    # C3 only: variance decomposition
    if cond == "C3":
        out["decomposition"] = compute_c3_decomposition(sgs, saver)

    return out


def compute_c3_decomposition(sgs, saver) -> Dict[str, Any]:
    """C3 の wealth variance を 3 成分に分解 (a/b/c).

    (a) realized cognitive P&L variance from round_trips
    (b) partial fill 比率 (round-trip ベース)
    (c) MTM variance proxy: 累積 |position| × |Δmid|
    """
    # mid prices time-series (main session)
    sorted_logs = sorted(saver.market_step_logs, key=lambda x: x["market_time"])
    mids: dict[int, float] = {log["market_time"]: float(log["market_price"]) for log in sorted_logs}
    times = sorted(mids.keys())
    main_times = [t for t in times if t >= WARMUP]
    main_mids = np.array([mids[t] for t in main_times], dtype=np.float64)
    dmids = np.diff(main_mids)
    abs_dmids = np.abs(dmids)
    main_t_offset = main_times[0] if main_times else WARMUP

    # (a) realized P&L variance — per round-trip cognitive P&L = delta_G * entry_quantity
    pnls = []
    for a in sgs:
        for rt in a.round_trips:
            if rt["close_t"] >= WARMUP and rt["open_t"] >= WARMUP:
                pnls.append(int(rt["delta_G"]) * int(rt["entry_quantity"]))
    pnls_arr = np.array(pnls, dtype=np.float64) if pnls else np.array([], dtype=np.float64)
    a_var = float(pnls_arr.var()) if pnls_arr.size > 1 else 0.0
    a_mean_abs = float(np.abs(pnls_arr).mean()) if pnls_arr.size > 0 else 0.0
    a_per_step = float((pnls_arr ** 2).sum() / MAIN_STEPS) if pnls_arr.size > 0 else 0.0

    # (b) partial fill ratio
    n_partial_close = sum(a.close_partial_matches for a in sgs)
    n_partial_open = sum(a.open_partial_matches for a in sgs)
    n_full_close = sum(a.close_full_matches for a in sgs)
    n_full_open = sum(a.open_full_matches for a in sgs)
    rt_total = sum(len(a.round_trips) for a in sgs)
    partial_close_ratio = n_partial_close / max(rt_total, 1)
    partial_open_ratio = n_partial_open / max(n_full_open + n_partial_open + 1, 1)

    # (c) MTM variance proxy: per step per agent, |position| × |Δmid|
    # Reconstruct position(t, i) from round_trips: position is non-zero between open_t and close_t
    # Per step accumulate (sum over agents) |q_i| × |Δmid_t|
    mtm_step = np.zeros(len(main_times), dtype=np.float64)
    main_t_to_idx = {t: i for i, t in enumerate(main_times)}

    for a in sgs:
        for rt in a.round_trips:
            o = int(rt["open_t"])
            c = int(rt["close_t"])
            q = int(rt["entry_quantity"])
            for tt in range(max(o, WARMUP) + 1, min(c, WARMUP + MAIN_STEPS) + 1):
                if tt in main_t_to_idx:
                    idx = main_t_to_idx[tt]
                    if 0 < idx < len(abs_dmids) + 1:
                        # Δmid at step tt = main_mids[idx] - main_mids[idx-1]
                        dm = abs_dmids[idx - 1] if idx - 1 < len(abs_dmids) else 0.0
                        mtm_step[idx] += q * dm

    c_total = float(mtm_step.sum())
    c_per_step_mean = float(mtm_step.mean()) if mtm_step.size > 0 else 0.0
    c_var = float(mtm_step.var()) if mtm_step.size > 1 else 0.0

    return {
        "a_realized_pnl": {
            "n_round_trips": int(pnls_arr.size),
            "variance": a_var,
            "mean_abs": a_mean_abs,
            "per_step_sum_sq_over_T": a_per_step,
        },
        "b_partial_fill": {
            "n_partial_close": n_partial_close,
            "n_partial_open": n_partial_open,
            "n_full_close": n_full_close,
            "n_full_open": n_full_open,
            "n_round_trips": rt_total,
            "partial_close_to_round_trip_ratio": partial_close_ratio,
            "partial_open_to_open_ratio": partial_open_ratio,
        },
        "c_mtm_variance_proxy": {
            "cumulative_abs_position_x_dmid": c_total,
            "per_step_mean": c_per_step_mean,
            "per_step_variance": c_var,
            "median_abs_dmid": float(np.median(abs_dmids)) if abs_dmids.size > 0 else 0.0,
        },
    }


def main() -> None:
    print("=" * 80)
    print(f"Measurement 7 (3-condition): C1 / C2 / C3 — seed={SEED}, "
          f"warmup={WARMUP}, main={MAIN_STEPS}, num_sg={NUM_SG}, num_fcn={NUM_FCN}")
    print("=" * 80)

    results = {}
    for cond in ("C1", "C2", "C3"):
        print(f"\n--- running {cond} ---")
        results[cond] = run_condition(cond)
        print(f"   runtime: {results[cond]['runtime_sec']:.1f}s  "
              f"n_subs(main)={results[cond]['n_subs_main']}")

    # Save
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "measurement_7_all.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print combined table
    print("\n" + "=" * 80)
    print("Measurement 7 — combined table (per condition vs YH005_1 baseline)")
    print("=" * 80)
    print(f"{'metric':40s} {'C1':>15s} {'C2':>15s} {'C3':>15s}")
    print("-" * 80)
    fmt_int = lambda v: f"{v}" if v is not None else "—"
    fmt_f3 = lambda v: f"{v:.3e}" if v is not None else "—"
    fmt_f2 = lambda v: f"{v:.2f}" if v is not None else "—"
    fmt_f0 = lambda v: f"{v:.0f}" if v is not None else "—"

    print(f"{'(i) substitute_rate (per agent-step)':40s} "
          f"{fmt_f3(results['C1']['substitute_rate']):>15s} "
          f"{fmt_f3(results['C2']['substitute_rate']):>15s} "
          f"{fmt_f3(results['C3']['substitute_rate']):>15s}")
    print(f"{'    ratio vs YH005_1 (2.04e-3)':40s} "
          f"{fmt_f2(results['C1']['rate_ratio_vs_yh005_1']):>15s} "
          f"{fmt_f2(results['C2']['rate_ratio_vs_yh005_1']):>15s} "
          f"{fmt_f2(results['C3']['rate_ratio_vs_yh005_1']):>15s}")

    print(f"{'(ii) wealth_injection / step':40s} "
          f"{fmt_f2(results['C1']['wealth_injection_per_step']):>15s} "
          f"{fmt_f2(results['C2']['wealth_injection_per_step']):>15s} "
          f"{fmt_f2(results['C3']['wealth_injection_per_step']):>15s}")
    print(f"{'    injection / |Σs| ratio':40s} "
          f"{fmt_f3(results['C1']['injection_vs_noise']):>15s} "
          f"{fmt_f3(results['C2']['injection_vs_noise']):>15s} "
          f"{fmt_f3(results['C3']['injection_vs_noise']):>15s}")

    print(f"{'(iii) mean_lifetime (step/agent)':40s} "
          f"{fmt_f0(results['C1']['mean_lifetime_step_per_agent']):>15s} "
          f"{fmt_f0(results['C2']['mean_lifetime_step_per_agent']):>15s} "
          f"{fmt_f0(results['C3']['mean_lifetime_step_per_agent']):>15s}")
    print(f"{'    ratio vs YH005_1 (490 step)':40s} "
          f"{fmt_f2(results['C1']['lifetime_ratio_vs_yh005_1']):>15s} "
          f"{fmt_f2(results['C2']['lifetime_ratio_vs_yh005_1']):>15s} "
          f"{fmt_f2(results['C3']['lifetime_ratio_vs_yh005_1']):>15s}")

    if "decomposition" in results["C3"]:
        d = results["C3"]["decomposition"]
        print()
        print("C3 wealth variance decomposition:")
        print(f"  (a) realized P&L: var={d['a_realized_pnl']['variance']:.2f}  "
              f"mean|P&L|={d['a_realized_pnl']['mean_abs']:.2f}  "
              f"sum²/T={d['a_realized_pnl']['per_step_sum_sq_over_T']:.2f}  "
              f"n_rt={d['a_realized_pnl']['n_round_trips']}")
        print(f"  (b) partial close / round-trip = {d['b_partial_fill']['partial_close_to_round_trip_ratio']:.4f}")
        print(f"      partial open / total open  = {d['b_partial_fill']['partial_open_to_open_ratio']:.4f}")
        print(f"  (c) Σ_{{t,i}} |q_i|·|Δmid_t| = {d['c_mtm_variance_proxy']['cumulative_abs_position_x_dmid']:.0f}  "
              f"(per-step mean = {d['c_mtm_variance_proxy']['per_step_mean']:.2f})")
        print(f"      median|Δmid| = {d['c_mtm_variance_proxy']['median_abs_dmid']:.4f}")

    print(f"\nsaved: {out_dir / 'measurement_7_all.json'}")


if __name__ == "__main__":
    main()
