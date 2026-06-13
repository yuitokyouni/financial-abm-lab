"""認定セルの (ν, lr) 上で Δ_total / Δ_GP / Δ_pred 帰属（prereg-density-spoke.md 規則4）。

6 条件 × 5 seed を並列再計算（D-B12 決定論＝spoke run と同一軌道）し、per-seed markup を
永続化した上で seed ペア差の帰属を出す。spoke run が per-seed 値を保存しなかったための
再計算であり、新規サンプリングではない。charge は dense tier。

usage:
  python scripts/run_attribution.py --around <center-cell-id> --noise-rate 30 --lr 0.15 \
      --out results/attribution_seeds.csv --budget-ledger results/budget.json --parallel 12
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microstructure.designmap import (BudgetLedger, CONDITIONS, cell_id,  # noqa: E402
                                      classify_modulation, parse_cell_id,
                                      run_one_seed, _planned_periods)

import numpy as np  # noqa: E402


def _job(key, cfg, seed):
    m, _, actual, rt = run_one_seed(cfg, seed)
    return key, seed, m.markup, actual, rt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--around", required=True)
    ap.add_argument("--noise-rate", type=float, required=True)
    ap.add_argument("--lr", type=float, required=True)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget-ledger", required=True)
    ap.add_argument("--parallel", type=int, default=1)
    args = ap.parse_args(argv)

    base = parse_cell_id(args.around).replace(noise_rate=args.noise_rate, lr=args.lr)
    jobs = {(mech, N, stal): base.replace(mechanism=mech, batch_interval=N, staleness=stal)
            for mech, N, stal in CONDITIONS}

    ledger = BudgetLedger(args.budget_ledger)
    from concurrent.futures import ProcessPoolExecutor, as_completed
    markups: dict[tuple, dict[int, float]] = {k: {} for k in jobs}
    with ProcessPoolExecutor(max_workers=args.parallel) as ex:
        futs = {}
        for key, cfg in jobs.items():
            for s in range(args.seeds):
                planned = _planned_periods(cfg)
                ledger.charge("dense", planned)
                futs[ex.submit(_job, key, cfg, s)] = planned
        for fut in as_completed(futs):
            key, seed, mk, actual, rt = fut.result()
            ledger.refund("dense", futs[fut] - actual)
            markups[key][seed] = mk
            print(f"{cell_id(jobs[key])} seed={seed} markup={mk:.3f} ({rt:.0f}s)", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cell", "mechanism", "batch_interval", "staleness",
                    "noise_rate", "lr", "seed", "markup"])
        for (mech, N, stal), d in markups.items():
            for s in sorted(d):
                w.writerow([cell_id(jobs[(mech, N, stal)]), mech, N, stal,
                            args.noise_rate, args.lr, s, d[s]])

    arr = {k: np.array([v[s] for s in sorted(v)]) for k, v in markups.items()}
    result = {"modulation": {}, "attribution": {}}
    for stal in ("committed", "revisable"):
        b = arr[("continuous", 1, stal)]
        for N in (5, 20):
            d = arr[("batch", N, stal)] - b
            result["modulation"][f"batch{N}-{stal}"] = {
                "diff_mean": float(d.mean()),
                "diff_se": float(d.std(ddof=1) / math.sqrt(len(d))),
                "class": classify_modulation(d)}
    for N in (5, 20):
        d_total = arr[("batch", N, "committed")] - arr[("continuous", 1, "committed")]
        d_gp = arr[("batch", N, "revisable")] - arr[("continuous", 1, "revisable")]
        d_pred = d_total - d_gp
        k = math.sqrt(len(d_total))
        result["attribution"][f"N={N}"] = {
            "delta_total": float(d_total.mean()), "se_total": float(d_total.std(ddof=1) / k),
            "delta_gp": float(d_gp.mean()), "se_gp": float(d_gp.std(ddof=1) / k),
            "delta_pred": float(d_pred.mean()), "se_pred": float(d_pred.std(ddof=1) / k)}
    summary = out.with_suffix(".json")
    summary.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"done → {out} / {summary}; dense spent {ledger.data['spent']['dense']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
