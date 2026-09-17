"""Rerun an archived cohort unchanged after a kernel correction.

Check current native asks before launching pairs. An unavailable ask stops the
whole cohort; it never silently removes a seed or substitutes another one.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from lobcore import Agent, write_log_file
import lobcore._core as core

from .experiment import WorldExperiment
from .run_ensemble import run_seeds, save_json
from .version import default_lobcore_root, lobcore_git_hash


def load_cohort(path):
    previous = json.loads(Path(path).read_text())
    seeds = previous["seeds"]
    if (len(seeds) < 2 or any(type(s) is not int or s < 0 for s in seeds)
            or seeds != sorted(set(seeds))):
        raise ValueError("Require a sorted, unique cohort of nonnegative seed integers")
    return previous


class AskProbe(Agent):
    def __init__(self, t0):
        self.t0 = t0
        self.observation = None

    def on_wakeup(self, view, ctx):
        if view.now < self.t0:
            ctx.schedule_wakeup(self.t0)
            return
        market = view.market(0)
        self.observation = {
            "time": view.now,
            "bid_price": None if market.best_bid is None else market.best_bid.price,
            "bid_qty": 0 if market.best_bid is None else market.best_bid.qty,
            "ask_price": None if market.best_ask is None else market.best_ask.price,
            "ask_qty": 0 if market.best_ask is None else market.best_ask.qty,
        }


def preflight(plan, output):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in plan["seeds"]:
        config = deepcopy(plan["config"])
        config.update(seed=seed, end_time=config["impact"]["t0"])
        probe = AskProbe(config["end_time"])
        run = WorldExperiment(config)._run(extra_agents=(probe,), strict=True).result
        if probe.observation is None:
            raise ValueError(f"No native t0 observation: seed={seed}")
        if run.meta.lobcore_version != plan["lobcore_commit"]:
            raise ValueError("lobcore commit changed during preflight")
        path = output / f"seed{seed:04d}.bin"
        write_log_file(str(path), run.meta, run.log)
        rows.append({
            "seed": seed, "at_t0": probe.observation,
            "eligible": probe.observation["ask_qty"] > 0,
            "meta": asdict(run.meta), "n_records": len(run.log),
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "log_sha256": hashlib.sha256(run.log.tobytes()).hexdigest(),
        })
    result = {
        "cohort_unchanged": True,
        "missing_ask_seeds": [r["seed"] for r in rows if not r["eligible"]],
        "observations": rows,
        "observation_method": "Read native View at t0 after deliveries, with a non-trading observer in the impact agent slot.",
    }
    save_json(output / "summary.json", result)
    if result["missing_ask_seeds"]:
        raise ValueError(f"Fixed cohort cannot run: absent ask for {result['missing_ask_seeds']}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-plan", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("Require workers >= 1")
    previous = load_cohort(args.previous_plan)
    out = args.out_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new output directory; never overwrite an existing run")
    out.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent
    plan = {
        "seeds": previous["seeds"], "config": previous["config"],
        "analysis": previous["analysis"], "workers": args.workers,
        "lobcore_commit": lobcore_git_hash(default_lobcore_root()),
        "fal_base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))},
        "previous_plan_sha256": hashlib.sha256(args.previous_plan.read_bytes()).hexdigest(),
        "previous_lobcore_commit": previous["lobcore_commit"],
        "selection": "Exact archived cohort retained for before/after software correction; no new exclusions, including no sign-based exclusions.",
        "budget": f"{len(previous['seeds'])} seeds, end={previous['config']['end_time']}; all original model parameters and analysis settings retained.",
    }
    save_json(out / "plan.json", plan)
    save_json(out / "runtime.json", {
        "python": platform.python_version(), "platform": platform.platform(),
        "extension_sha256": hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        "lobcore_commit": plan["lobcore_commit"],
    })
    try:
        check = preflight(plan, out / "preflight")
    except Exception as exc:
        save_json(out / "progress.json", {"status": "STOP: fixed-cohort preflight", "completed": [], "error": str(exc)})
        raise
    print(f"Native ask exists for all {len(check['observations'])} archived seeds", flush=True)
    run_seeds(plan, out, workers=args.workers)


if __name__ == "__main__":
    main()
