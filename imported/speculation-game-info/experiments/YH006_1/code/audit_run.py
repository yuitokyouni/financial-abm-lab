"""Step1 short run: exercise the L1/L2/L3 hooks end-to-end on a short C2 (LOB
uniform), then close claim-2 (residual a/b from L1), and emit #4 counterparty
composition (L2) + step2(iii) discretization stats (L3).

Reuses the Phase-2 config recipe (run_experiment.run_lob_trial_smoke) but swaps
SG class -> InstrumentedSpeculationAgent and logger -> AuditLogger.

Run:  python3 audit_run.py --warmup 200 --main 300 --seed 1000
"""

from __future__ import annotations

import argparse
import random as _stdlib_random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
YH006 = HERE.parent.parent / "YH006"
for p in (str(HERE), str(YH006)):
    if p not in sys.path:
        sys.path.insert(0, p)

from pams.runners import SequentialRunner  # noqa: E402

from configs.c2 import make_config  # noqa: E402  (LOB uniform)
from mm_fcn_agent import MMFCNAgent  # noqa: E402
from sg_agent import (  # noqa: E402
    WInitLoggingSpeculationAgent, QConstSpeculationAgent, LifetimeCapSpeculationAgent,
)
from audit_instrument import (  # noqa: E402
    InstrumentedSpeculationAgent, AuditLogger, gather_l1, agent_class_map,
)
import audit_residuals  # noqa: E402

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--main", type=int, default=300)
    ap.add_argument("--num-sg", type=int, default=100)
    ap.add_argument("--num-fcn", type=int, default=30)
    ap.add_argument("--c-ticks", type=float, default=28.0)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--out", type=str, default=str(HERE.parent / "outputs" / "audit"),
                    help="dump dir for audit_L{1,2,3}.parquet (default: YH006_1/outputs/audit, gitignored)")
    args = ap.parse_args()
    OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)

    cfg = make_config(
        warmup_steps=args.warmup, main_steps=args.main,
        num_sg_agents=args.num_sg, c_ticks=args.c_ticks, max_normal_orders=500,
    )
    cfg["FCNAgents"]["numAgents"] = args.num_fcn
    cfg["SGAgents"]["class"] = "InstrumentedSpeculationAgent"

    logger = AuditLogger()
    runner = SequentialRunner(
        settings=cfg, prng=_stdlib_random.Random(args.seed), logger=logger,
    )
    for cls in (WInitLoggingSpeculationAgent, QConstSpeculationAgent,
                LifetimeCapSpeculationAgent, InstrumentedSpeculationAgent, MMFCNAgent):
        runner.class_register(cls)

    print(f"[run] C2 warmup={args.warmup} main={args.main} "
          f"num_sg={args.num_sg} num_fcn={args.num_fcn} seed={args.seed}")
    runner.main()

    sgs = [a for a in runner.simulator.agents
           if isinstance(a, InstrumentedSpeculationAgent)]
    print(f"[run] done. SG agents={len(sgs)}")

    # ---------- L1 -> claim-2 verdict (L1 単独) ----------
    l1 = gather_l1(sgs)
    l1.to_parquet(OUT / "audit_L1.parquet")
    print(f"[L1] records={len(l1):,} -> {OUT/'audit_L1.parquet'}")
    verdict = audit_residuals.judge(l1)
    audit_residuals.print_verdict(verdict)

    # ---------- L2 -> #4 counterparty composition ----------
    l2 = pd.DataFrame(logger.executions)
    l2.to_parquet(OUT / "audit_L2.parquet")
    cmap = agent_class_map(runner.simulator)
    print("\n" + "=" * 74 + "\n#4 SG 約定相手の内訳 (L2)\n" + "=" * 74)
    if not l2.empty:
        l2["buy_cls"] = l2["buy_agent_id"].map(cmap)
        l2["sell_cls"] = l2["sell_agent_id"].map(cmap)
        # SG が絡む約定 (SG が buy か sell) について、相手側の class を数える
        sg_fills = []
        for _, r in l2.iterrows():
            if r["buy_cls"] == "SG":
                sg_fills.append(r["sell_cls"])   # SG buy の相手
            if r["sell_cls"] == "SG":
                sg_fills.append(r["buy_cls"])    # SG sell の相手
        s = pd.Series(sg_fills)
        print(f"  総約定 ={len(l2):,}  SG が関与した約定サイド ={len(sg_fills):,}")
        if len(s):
            vc = s.value_counts()
            for cls, cnt in vc.items():
                print(f"    相手が {cls:5s}: {cnt:>8,}  ({cnt/len(s):6.2%})")
    else:
        print("  (no executions)")

    # ---------- L3 -> step2(iii) 離散化特性 ----------
    l3 = pd.DataFrame(logger.market_steps)
    l3.to_parquet(OUT / "audit_L3.parquet")
    print("\n" + "=" * 74 + "\nstep2(iii) 離散化特性 (L3, main session のみ)\n" + "=" * 74)
    m = l3[l3["t"] >= args.warmup].copy()
    px = m["market_price"].to_numpy(dtype=float)
    if px.size > 2:
        ret = np.diff(np.log(px))
        h = np.clip(np.round(np.diff(px) / args.c_ticks), -2, 2).astype(int)
        zero_frac = float(np.mean(np.diff(px) == 0))
        print(f"  main steps={px.size}  1-step return: std={ret.std():.5f}  "
              f"zero-return frac={zero_frac:.2%}")
        print(f"  c_ticks={args.c_ticks} 量子化 h 分布: "
              + ", ".join(f"{k}:{(h==k).mean():.1%}" for k in [-2, -1, 0, 1, 2]))
        depth = (m["n_buy"] + m["n_sell"]).to_numpy()
        print(f"  板厚み(n_buy+n_sell) p10/p50/p90 = "
              f"{np.percentile(depth,10):.0f}/{np.percentile(depth,50):.0f}/{np.percentile(depth,90):.0f}")
    else:
        print("  (insufficient price series)")

    print(f"\n[dump] L1/L2/L3 -> {OUT}/audit_L{{1,2,3}}.parquet")


if __name__ == "__main__":
    main()
