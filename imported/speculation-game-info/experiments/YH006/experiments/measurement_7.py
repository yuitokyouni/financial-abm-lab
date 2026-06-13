"""計測 7: 系の openness 診断 (substitute rate / wealth injection / turnover).

C3 smoke (現行 B-1 config: MM-FCN order_volume=30, SG=100 Pareto, 600 step)
で以下を計算し、YH005_1 (aggregate-demand) の対応値と比較:

(i)   substitute_rate = total_subs / (N_sg × T_main)  per agent-step
(ii)  wealth_injection_rate = Σ(new - dead) / T_main  per step
       (Σ(signed_q) ゼロサム誤差との相対比較)
(iii) turnover_time = mean lifetime between consecutive substitutes per agent

YH005_1 baseline (phase1_metrics.json):
  N=1000, T=50000, num_substitutions=102087, total_wealth_T=48401
"""

from __future__ import annotations

import json
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
    warmup = 100
    main_steps = 600
    num_sg = 100
    num_fcn = 30
    seed = 777

    cfg = make_config(
        warmup_steps=warmup, main_steps=main_steps,
        num_sg_agents=num_sg, c_ticks=28.0,
        max_normal_orders=2000,
    )
    cfg["FCNAgents"]["numAgents"] = num_fcn

    saver = OrderTrackingSaver()
    runner = SequentialRunner(settings=cfg, prng=random.Random(seed), logger=saver)
    runner.class_register(SpeculationAgent)
    runner.class_register(MMFCNAgent)

    t0 = time.perf_counter()
    runner.main()
    elapsed = time.perf_counter() - t0

    sgs = [a for a in runner.simulator.agents if isinstance(a, SpeculationAgent)]

    # Aggregate substitute events across agents
    all_events: list[tuple[int, int, int, int]] = []  # (agent_id, t, dead_w, new_w)
    for a in sgs:
        for (t, dead_w, new_w) in a.substitute_events:
            all_events.append((a.agent_id, t, dead_w, new_w))

    total_subs = len(all_events)
    T_main = main_steps  # main session steps; substitute_events fires using close_step which is in absolute time
    # filter to main-session events only (close_step >= warmup)
    main_events = [e for e in all_events if e[1] >= warmup]
    N_main_subs = len(main_events)

    # (i) substitute rate per agent-step
    subst_rate_total = total_subs / (num_sg * (warmup + main_steps))
    subst_rate_main = N_main_subs / (num_sg * main_steps)

    # (ii) wealth injection per step (main session)
    wealth_injection_total = sum(new_w - dead_w for (_, t, dead_w, new_w) in main_events)
    wealth_injection_per_step = wealth_injection_total / main_steps if main_steps > 0 else 0.0

    # Compare to Σ(signed_q) "zero-sum noise" magnitude
    sum_s = np.zeros(warmup + main_steps, dtype=np.int64)
    for a in sgs:
        for (t, signed_q) in a.submit_log:
            if 0 <= t < warmup + main_steps:
                sum_s[t] += signed_q
    main_sum_s = sum_s[warmup:]
    abs_mean_sum_s = float(np.abs(main_sum_s).mean())
    std_sum_s = float(main_sum_s.std())

    # (iii) turnover time
    # Per-agent: list of substitute timestamps. Inter-arrival times averaged.
    inter_arrival_all = []
    for a in sgs:
        ts = sorted([e[0] for e in a.substitute_events if e[0] >= warmup])
        # Define lifetime as: (warmup + main_steps - first_t) for the trailing slot
        # and ts[i+1] - ts[i] for inner slots
        if not ts:
            continue
        prev = warmup  # birth (or last substitute) at warmup boundary as approximation
        for t in ts:
            inter_arrival_all.append(t - prev)
            prev = t
    mean_turnover = float(np.mean(inter_arrival_all)) if inter_arrival_all else float("inf")
    median_turnover = float(np.median(inter_arrival_all)) if inter_arrival_all else float("inf")

    # Aggregate stats
    dead_wealths = [e[3] - (e[3] - e[2]) for e in main_events]  # = e[2]
    dead_wealths = [e[2] for e in main_events]
    new_wealths = [e[3] for e in main_events]

    # YH005_1 reference values
    yh005_1 = {
        "N": 1000,
        "T": 50000,
        "num_substitutions": 102087,
        "subst_rate": 102087 / (1000 * 50000),  # per agent-step
        "total_wealth_T": 48401,  # final
        # Inter-arrival per agent: 50M agent-steps / 102087 substitutes = 490 step / substitute
        "mean_turnover_step": (1000 * 50000) / 102087,
    }

    print("=" * 70)
    print(f"=== Measurement 7: openness diagnosis (C3 smoke, seed={seed}) ===")
    print("=" * 70)
    print(f"Config: num_sg={num_sg}, num_fcn={num_fcn}, warmup={warmup}, main={main_steps}")
    print(f"runtime: {elapsed:.1f}s")
    print()

    print("--- raw counts ---")
    print(f"total_substitutions (all)   = {total_subs}")
    print(f"main-session substitutions  = {N_main_subs}")
    print()

    print("--- (i) substitute rate per agent-step ---")
    print(f"YH006 C3 (main)  = {subst_rate_main:.3e}  ({N_main_subs}/{num_sg*main_steps})")
    print(f"YH005_1 baseline = {yh005_1['subst_rate']:.3e}  ({yh005_1['num_substitutions']}/{yh005_1['N']*yh005_1['T']})")
    ratio = subst_rate_main / yh005_1['subst_rate']
    print(f"ratio C3/agg     = {ratio:.3f}x  ({'lower' if ratio<1 else 'higher'} activity)")
    print()

    print("--- (ii) wealth injection per step ---")
    print(f"Σ(new - dead) over main events = {wealth_injection_total}")
    print(f"per-step injection             = {wealth_injection_per_step:+.2f}")
    if main_events:
        print(f"per-event mean injection       = {wealth_injection_total/len(main_events):+.2f}")
        print(f"  dead wealth: min={min(dead_wealths)} mean={float(np.mean(dead_wealths)):.1f} max={max(dead_wealths)}")
        print(f"  new  wealth: min={min(new_wealths)} mean={float(np.mean(new_wealths)):.1f} max={max(new_wealths)}")
    print(f"Σ(signed_q) per-step abs mean  = {abs_mean_sum_s:.2f}  (zero-sum noise)")
    print(f"Σ(signed_q) per-step std       = {std_sum_s:.2f}")
    if abs_mean_sum_s > 0:
        print(f"injection / |Σs| ratio         = {abs(wealth_injection_per_step)/abs_mean_sum_s:.3f}")
        print(f"  → {'DOMINANT' if abs(wealth_injection_per_step) > abs_mean_sum_s else 'minor'}")
    print()

    print("--- (iii) agent turnover time ---")
    print(f"YH006 C3 mean inter-arrival   = {mean_turnover:.0f} step/agent  (n_intervals={len(inter_arrival_all)})")
    print(f"YH006 C3 median inter-arrival = {median_turnover:.0f} step/agent")
    print(f"YH005_1 baseline mean         = {yh005_1['mean_turnover_step']:.0f} step/agent")
    if mean_turnover != float("inf"):
        ratio_t = mean_turnover / yh005_1['mean_turnover_step']
        print(f"ratio C3/agg                  = {ratio_t:.3f}x  ({'longer' if ratio_t>1 else 'shorter'} lifetime)")

    # Save
    out = {
        "config": {"num_sg": num_sg, "num_fcn": num_fcn, "warmup": warmup,
                   "main_steps": main_steps, "seed": seed},
        "runtime_sec": elapsed,
        "i_substitute_rate": {
            "yh006_c3_main": subst_rate_main,
            "yh005_1_baseline": yh005_1["subst_rate"],
            "ratio": float(ratio) if N_main_subs > 0 else None,
            "n_main_subs": N_main_subs,
            "n_total_subs": total_subs,
        },
        "ii_wealth_injection": {
            "total_main": wealth_injection_total,
            "per_step": wealth_injection_per_step,
            "per_event": (wealth_injection_total/len(main_events)) if main_events else None,
            "dead_wealth_stats": {
                "min": int(min(dead_wealths)) if dead_wealths else None,
                "mean": float(np.mean(dead_wealths)) if dead_wealths else None,
                "max": int(max(dead_wealths)) if dead_wealths else None,
            },
            "new_wealth_stats": {
                "min": int(min(new_wealths)) if new_wealths else None,
                "mean": float(np.mean(new_wealths)) if new_wealths else None,
                "max": int(max(new_wealths)) if new_wealths else None,
            },
            "sum_signed_q_abs_mean": abs_mean_sum_s,
            "sum_signed_q_std": std_sum_s,
            "injection_vs_noise_ratio": (abs(wealth_injection_per_step)/abs_mean_sum_s) if abs_mean_sum_s > 0 else None,
        },
        "iii_turnover": {
            "yh006_c3_mean_step_per_agent": float(mean_turnover) if mean_turnover != float("inf") else None,
            "yh006_c3_median": float(median_turnover) if median_turnover != float("inf") else None,
            "yh005_1_mean": yh005_1["mean_turnover_step"],
            "n_intervals": len(inter_arrival_all),
        },
    }
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "measurement_7.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nsaved: {out_dir / 'measurement_7.json'}")


if __name__ == "__main__":
    main()
