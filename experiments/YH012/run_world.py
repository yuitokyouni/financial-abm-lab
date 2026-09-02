#!/usr/bin/env python3
"""World のみ実行し、出口基準の統計を表示して log を保存する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.YH012.experiment import WorldExperiment


def main() -> None:
    parser = argparse.ArgumentParser(description="YH012 Phase 1 World run")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "configs" / "poc_seed42.yaml",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "artifacts",
    )
    args = parser.parse_args()

    exp = WorldExperiment.from_yaml(args.config)
    run = exp.run()
    stats = run.stats

    print("=== YH012 Phase 1 World ===")
    print(f"seed={exp.seed} end_time={exp.end_time} agents={exp.n_f}+{exp.n_c}+{exp.n_n}")
    print(f"lobcore_version={run.result.meta.lobcore_version}")
    print(f"state_hash={run.result.state_hash}")
    print(f"n_events={stats.n_events} n_fills={stats.n_fills}")
    print(f"spread_positive_frac={stats.spread_positive_frac:.4f}")
    print(f"mean_spread={stats.mean_spread:.4f}")
    print(f"volatility={stats.volatility:.6f}")
    print(f"mid_f_corr={stats.mid_f_corr:.4f} n_mid_obs={stats.n_mid_obs}")

    gates = {
        "spread_ge_90pct": stats.spread_positive_frac >= 0.90,
        "fills_gt_0": stats.n_fills > 0,
        "mid_f_corr_gt_0": stats.mid_f_corr > 0.0,
    }
    print("gates:", gates)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / f"world_seed{exp.seed}.bin"
    stats_path = args.out_dir / f"world_seed{exp.seed}_stats.json"
    exp.save_log(log_path, run)
    stats_path.write_text(
        json.dumps(
            {
                "meta": {
                    "master_seed": run.result.meta.master_seed,
                    "lobcore_version": run.result.meta.lobcore_version,
                    "end_time": run.result.meta.end_time,
                    "agent_config": run.result.meta.agent_config,
                },
                "state_hash": run.result.state_hash,
                "stats": stats.__dict__,
                "gates": gates,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {log_path}")
    print(f"wrote {stats_path}")


if __name__ == "__main__":
    main()
