"""Run a fixed seed ensemble, stopping all workers on the first invalid pair."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import yaml

from .impact import assert_pre_intervention_equal
from .inspect_saved_pair import read_verified_log
from .version import default_lobcore_root, lobcore_git_hash


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def select_eligible_seeds(diagnostic, candidates, config):
    """Apply the fixed-t0 ask criterion to saved, native background observations."""
    diagnostic = Path(diagnostic)
    provenance_path = diagnostic / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    source = Path(__file__).parent
    for name in ("agents.py", "experiment.py"):
        if (
            hashlib.sha256((source / name).read_bytes()).hexdigest()
            != provenance["model_source_sha256"][name]
        ):
            raise ValueError(f"Background source changed since diagnostic: {name}")
    t0 = config["impact"]["t0"]
    observations, eligible = [], []
    for seed in candidates:
        directory = diagnostic / f"seed{seed:04d}"
        summary_path = directory / "summary.json"
        summary = json.loads(summary_path.read_text())
        # Recheck both the saved native quotes and the background log provenance.
        meta, _ = read_verified_log(directory / "background.bin", summary["log"])
        observed_config = deepcopy(meta.agent_config["config"])
        expected = {**config, "seed": seed}
        observed_config["end_time"] = config["end_time"]
        if (
            observed_config != expected
            or meta.master_seed != seed
            or meta.end_time < t0
        ):
            raise ValueError(f"Diagnostic configuration mismatch: seed={seed}")
        quotes_path = directory / "native_quotes.npz"
        quotes_hash = hashlib.sha256(quotes_path.read_bytes()).hexdigest()
        if quotes_hash != summary["native_quotes_sha256"]:
            raise ValueError(f"Native quotes SHA-256 mismatch: seed={seed}")
        with np.load(quotes_path, allow_pickle=False) as data:
            quotes = data["quotes"]
            rows = quotes[quotes[:, 0] == t0]
        if rows.shape != (1, 5):
            raise ValueError(
                f"Require exactly one native observation at t0: seed={seed}"
            )
        _, bid_price, bid_qty, ask_price, ask_qty = map(int, rows[0])
        if bid_qty < 0 or ask_qty < 0:
            raise ValueError(f"Negative native quote quantity: seed={seed}")
        at_t0 = {
            "time": t0,
            "bid_price": bid_price,
            "bid_qty": bid_qty,
            "ask_price": ask_price if ask_qty else None,
            "ask_qty": ask_qty,
        }
        if at_t0 != summary["at_t0"]:
            raise ValueError(f"Native t0 observation/summary mismatch: seed={seed}")
        keep = ask_qty > 0
        if keep:
            eligible.append(seed)
        observations.append(
            {
                "seed": seed,
                "eligible": keep,
                "at_t0": at_t0,
                "reason": "best_ask present at fixed t0"
                if keep
                else "best_ask absent at fixed t0",
                "diagnostic_lobcore_commit": meta.lobcore_version,
                "native_quotes_sha256": quotes_hash,
                "background_log_sha256": summary["log"]["log_sha256"],
                "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            }
        )
    if len(eligible) < 2:
        raise ValueError("Fewer than two eligible seeds")
    return eligible, {
        "criterion": "Exclude iff native best_ask is absent at fixed t0; no outcome-based exclusions.",
        "estimand": "Mean impact conditional on a background best_ask existing at t0.",
        "timing": "Criterion adopted after liquidity diagnosis, before this ensemble rerun.",
        "candidate_seeds": list(candidates),
        "eligible_seeds": eligible,
        "excluded_seeds": [row["seed"] for row in observations if not row["eligible"]],
        "diagnostic_provenance_sha256": hashlib.sha256(
            provenance_path.read_bytes()
        ).hexdigest(),
        "observations": observations,
    }


def verified_pair(directory, config, lobcore_version):
    """Recheck the saved bytes and configuration, including when resuming."""
    summary = json.loads((directory / "summary.json").read_text())
    logs = []
    for arm in ("factual", "baseline"):
        meta, log = read_verified_log(directory / f"{arm}.bin", summary["arms"][arm])
        if meta.agent_config["config"] != config:
            raise ValueError(f"Configuration mismatch: {directory}/{arm}")
        if (
            meta.master_seed != config["seed"]
            or meta.end_time != config["end_time"]
            or meta.allocation_rule != config.get("rule", "price_time")
        ):
            raise ValueError(f"ExperimentMeta/config mismatch: {directory}/{arm}")
        if meta.lobcore_version != lobcore_version:
            raise ValueError(f"lobcore version mismatch: {directory}/{arm}")
        expected_suppress = [] if arm == "factual" else [summary["impact_id"]]
        if meta.agent_config["suppress_agent_ids"] != expected_suppress:
            raise ValueError(f"Suppression mismatch: {directory}/{arm}")
        logs.append(log)
    prefix = assert_pre_intervention_equal(*logs, t0=config["impact"]["t0"])
    if prefix != summary["prefix"]:
        raise ValueError(f"Saved prefix certificate mismatch: {directory}")
    return summary, logs


def run_seeds(plan, out, *, workers, resume=False):
    """Own every child PID; on any failure terminate and reap all remaining jobs."""
    active = {}
    pending = iter(plan["seeds"])
    completed = []
    started = time.monotonic()
    progress = {"status": "RUNNING", "completed": completed}
    try:
        exhausted = False
        while active or not exhausted:
            # Inspect every finished worker before dispatching further work.
            finished = [(p, job) for p, job in active.items() if p.poll() is not None]
            for process, (seed, directory, config, stream, job_start) in finished:
                if (
                    process.returncode not in (0, 1)
                    or not (directory / "summary.json").exists()
                ):
                    stream.flush()
                    details = (
                        (directory / "worker.log").read_text().strip().splitlines()
                    )
                    cause = details[-1] if details else "No worker diagnostics"
                    raise RuntimeError(
                        f"STOP seed={seed}, exit={process.returncode}; "
                        f"{cause}; see {directory / 'worker.log'}"
                    )
                summary, _ = verified_pair(directory, config, plan["lobcore_commit"])
                if summary["status"] not in ("PASS", "FAIL: mean delta <= 0"):
                    raise RuntimeError(f"STOP seed={seed}: {summary['status']}")
                stream.close()
                del active[process]
                completed.append(seed)
                print(
                    f"[{len(completed)}/{len(plan['seeds'])}] seed={seed} "
                    f"prefix=BYTE_EQUAL mean={summary['mean_delta']:+.6f} "
                    f"filled={summary['impact_executed_qty']} "
                    f"elapsed={time.monotonic() - job_start:.1f}s",
                    flush=True,
                )
                save_json(out / "progress.json", progress)
            while not exhausted and len(active) < workers:
                seed = next(pending, None)
                if seed is None:
                    exhausted = True
                    break
                config = deepcopy(plan["config"])
                config["seed"] = seed
                directory = out / f"seed{seed:04d}"
                if resume and (directory / "summary.json").exists():
                    summary, _ = verified_pair(
                        directory, config, plan["lobcore_commit"]
                    )
                    if summary["status"] not in ("PASS", "FAIL: mean delta <= 0"):
                        raise RuntimeError(f"STOP seed={seed}: {summary['status']}")
                    completed.append(seed)
                    print(
                        f"[{len(completed)}/{len(plan['seeds'])}] seed={seed} verified resume",
                        flush=True,
                    )
                    save_json(out / "progress.json", progress)
                    continue
                if directory.exists() and any(directory.iterdir()):
                    raise ValueError(
                        f"Refusing to overwrite incomplete run: {directory}"
                    )
                directory.mkdir(parents=True, exist_ok=True)
                config_path = directory / "config.yaml"
                config_path.write_text(yaml.safe_dump(config, sort_keys=False))
                stream = (directory / "worker.log").open("w")
                env = {
                    **os.environ,
                    "OPENBLAS_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                }
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "experiments.YH012.run_impact",
                        "--config",
                        str(config_path),
                        "--out-dir",
                        str(directory),
                    ],
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
                active[process] = (seed, directory, config, stream, time.monotonic())
            if active:
                time.sleep(0.2)
        progress["status"] = "COMPLETE: all prefixes byte equal"
    except BaseException as exc:
        progress.update(status="STOP", error=str(exc))
        raise
    finally:
        for process in active:
            if process.poll() is None:
                process.terminate()
        for process, job in active.items():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            job[3].close()
        progress["wall_seconds_this_invocation"] = time.monotonic() - started
        save_json(out / "progress.json", progress)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "configs/impact_seed42.yaml",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--n-seeds", type=int, default=40)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--liquidity-diagnostic",
        type=Path,
        help="Saved native background observations used to exclude absent best_ask at fixed t0",
    )
    args = parser.parse_args()
    if args.first_seed < 0 or args.n_seeds < 2 or args.workers < 1:
        parser.error("Require nonnegative seeds, n-seeds >= 2 and workers >= 1")
    config = yaml.safe_load(args.config.read_text())
    config.pop("seed")
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out / "plan.json"
    source_root = Path(__file__).parent
    plan = {
        "seeds": list(range(args.first_seed, args.first_seed + args.n_seeds)),
        "config": config,
        "lobcore_commit": lobcore_git_hash(
            Path(config.get("lobcore_root") or default_lobcore_root())
        ),
        "fal_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source_root.glob("*.py"))
        },
        "workers": args.workers,
        "selection": "Consecutive seeds fixed before examining ensemble outcomes; no sign-based exclusions.",
        "budget": (
            f"{args.n_seeds} seeds; end_time={config['end_time']}; "
            f"{args.workers} independent worker processes. "
            "Default study retains 50000 to measure [45000,50000]; "
            "model parameters and horizon unchanged from the single-seed run."
        ),
        "analysis": {
            "bootstrap_replicates": 4000,
            "bootstrap_seed": 20260905,
            "confidence_level": 0.95,
            "grid_step": 1,
            "tail_start": 45000,
        },
    }
    if args.liquidity_diagnostic:
        plan["seeds"], plan["eligibility"] = select_eligible_seeds(
            args.liquidity_diagnostic, plan["seeds"], config
        )
        plan["selection"] = plan["eligibility"]["criterion"]
        plan["budget"] += (
            f" Eligibility leaves {len(plan['seeds'])}/{args.n_seeds} candidates."
        )
    if plan_path.exists():
        previous = json.loads(plan_path.read_text())
        if (
            not args.resume
            or any(
                previous[k] != plan[k] for k in ("seeds", "config", "lobcore_commit")
            )
            or previous.get("eligibility") != plan.get("eligibility")
        ):
            parser.error(
                "Existing plan requires --resume with identical seeds, config and lobcore"
            )
        simulation_files = (
            "agents.py",
            "experiment.py",
            "impact.py",
            "metrics.py",
            "run_impact.py",
            "version.py",
        )
        if any(
            previous["source_sha256"][name] != plan["source_sha256"][name]
            for name in simulation_files
        ):
            parser.error(
                "Simulation source changed; cannot mix code versions on resume"
            )
        plan = previous
    else:
        save_json(plan_path, plan)
    run_seeds(plan, out, workers=args.workers, resume=args.resume)


if __name__ == "__main__":
    main()
