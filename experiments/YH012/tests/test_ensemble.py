import json
from dataclasses import asdict
import hashlib
import tarfile

import numpy as np
import pytest

from experiments.YH012.ensemble import (
    bootstrap_weights,
    sample_delta,
    seed_statistics,
    window_statistics,
)
from experiments.YH012.impact import ImpactSeries
from experiments.YH012.run_ensemble import run_seeds


def test_common_grid_holds_previous_value_and_preserves_missing():
    series = ImpactSeries(
        np.array([2, 5, 7, 10]), np.array([1, 3, np.nan, 4]), np.zeros(4)
    )
    actual = sample_delta(series, np.arange(11))
    np.testing.assert_allclose(
        actual, [np.nan, np.nan, 1, 1, 1, 3, 3, np.nan, np.nan, np.nan, 4]
    )
    with pytest.raises(ValueError, match="horizon"):
        sample_delta(series, np.arange(12))


def test_sample_sd_is_distinct_from_ci_and_no_missing_seed_is_dropped():
    values = np.array([[1, 2, np.nan], [3, 6, 3]])
    # Exhaustive bootstrap of n=2 has means [1,2,2,3], equally weighted.
    weights = np.array([[1, 0], [0.5, 0.5], [0.5, 0.5], [0, 1]])
    stats = seed_statistics(values, weights)
    np.testing.assert_allclose(stats["mean"], [2, 4, np.nan])
    np.testing.assert_allclose(stats["sd"], [np.sqrt(2), 2 * np.sqrt(2), np.nan])
    np.testing.assert_allclose(stats["se"], [1, 2, np.nan])
    np.testing.assert_allclose(stats["ci_low"], [1.075, 2.15, np.nan])
    np.testing.assert_allclose(stats["ci_high"], [2.925, 5.85, np.nan])
    np.testing.assert_array_equal(stats["n_finite"], [2, 2, 1])


def test_tail_ci_resamples_seed_time_means_not_independent_time_points():
    times = np.arange(5)
    # Perfectly anti-correlated adjacent values: each seed time mean is zero.
    delta = np.array([[1, -1, 1, -1, 99], [-3, 3, -3, 3, 99]])
    weights = bootstrap_weights(2, replicates=100, seed=42)
    result = window_statistics(times, delta, weights, start=0, end=4)
    assert result["mean"] == result["sd"] == result["ci_low"] == result["ci_high"] == 0
    assert result["per_seed_time_mean"] == [0, 0]
    assert seed_statistics(delta, weights)["sd"][0] > 0
    np.testing.assert_array_equal(
        weights, bootstrap_weights(2, replicates=100, seed=42)
    )
    np.testing.assert_allclose(weights.sum(axis=1), 1)


def test_missing_tail_is_rejected_instead_of_excluding_a_seed():
    with pytest.raises(ValueError, match="coverage"):
        window_statistics(
            np.arange(3),
            np.array([[1, np.nan, 1], [2, 2, 2]]),
            np.eye(2),
            start=0,
            end=2,
        )


@pytest.mark.parametrize("exit_code", [1, 2])
def test_first_failed_worker_stops_dispatch_and_terminates_other_children(
    tmp_path, monkeypatch, exit_code
):
    from experiments.YH012 import run_ensemble

    created = []

    class Process:
        def __init__(self, *args, **kwargs):
            self.index = len(created)
            self.returncode = exit_code if self.index == 0 else None
            self.terminated = False
            created.append(self)

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def wait(self, **kwargs):
            return self.returncode

    monkeypatch.setattr(run_ensemble.subprocess, "Popen", Process)
    monkeypatch.setattr(run_ensemble.time, "sleep", lambda _: None)
    plan = {"seeds": list(range(10)), "config": {}, "lobcore_commit": "a" * 40}
    with pytest.raises(RuntimeError, match=f"STOP seed=0, exit={exit_code}"):
        run_seeds(plan, tmp_path, workers=3)
    assert len(created) == 3
    assert all(p.terminated for p in created[1:])
    progress = json.loads((tmp_path / "progress.json").read_text())
    assert progress["status"] == "STOP"
    assert progress["completed"] == []


def test_nonpositive_seeds_are_retained_on_resume(tmp_path, monkeypatch):
    from experiments.YH012 import run_ensemble

    directory = tmp_path / "seed0000"
    directory.mkdir()
    (directory / "summary.json").write_text("{}")
    monkeypatch.setattr(
        run_ensemble,
        "verified_pair",
        lambda *args: ({"status": "FAIL: mean delta <= 0"}, []),
    )
    run_seeds(
        {"seeds": [0], "config": {}, "lobcore_commit": "a" * 40},
        tmp_path,
        workers=1,
        resume=True,
    )
    assert json.loads((tmp_path / "progress.json").read_text())["completed"] == [0]


@pytest.fixture
def saved_ensemble(tmp_path):
    from lobcore import ExperimentMeta, LOG_DTYPE, write_log_file
    from experiments.YH012.impact import assert_pre_intervention_equal

    directory = tmp_path / "runs"
    directory.mkdir()
    common = {"end_time": 12, "impact": {"t0": 5, "t1": 7, "qty": 200}}
    plan = {
        "config": common,
        "seeds": [0, 1],
        "lobcore_commit": "a" * 40,
        "analysis": {
            "tail_start": 10,
            "bootstrap_replicates": 100,
            "bootstrap_seed": 42,
        },
    }
    (directory / "plan.json").write_text(json.dumps(plan))
    (directory / "progress.json").write_text(
        json.dumps({"status": "COMPLETE: all prefixes byte equal", "completed": [0, 1]})
    )
    for seed in (0, 1):
        run = directory / f"seed{seed:04d}"
        run.mkdir()
        config = {**common, "seed": seed}
        (run / "config.yaml").write_text(json.dumps(config))
        summary = {
            "impact_id": 1,
            "arms": {},
            "mean_delta": 1 if seed == 0 else -1,
            "impact_executed_qty": 200,
            "impact_fill_count": 1,
        }
        logs = []
        for arm in ("factual", "baseline"):
            log = np.zeros(3, dtype=LOG_DTYPE)
            log["received_at"] = [2, 6, 10]
            log["best_bid_price"] = [99, 101, 99] if seed == 0 else [99, 97, 103]
            if arm == "baseline":
                log["best_bid_price"] = 99
            log["best_ask_price"] = log["best_bid_price"] + 2
            log["best_bid_qty"] = log["best_ask_qty"] = 1
            raw = bytearray(log.tobytes())
            raw[11:16] = b"abcde"
            log = np.frombuffer(raw, dtype=LOG_DTYPE)
            meta = ExperimentMeta(
                seed,
                "price_time",
                2,
                1,
                12,
                "a" * 40,
                agent_config={
                    "config": config,
                    "suppress_agent_ids": [] if arm == "factual" else [1],
                },
            )
            write_log_file(str(run / f"{arm}.bin"), meta, log)
            summary["arms"][arm] = {
                "meta": asdict(meta),
                "log_sha256": hashlib.sha256(raw).hexdigest(),
                "n_records": 3,
            }
            logs.append(log)
        summary["prefix"] = assert_pre_intervention_equal(*logs, t0=5)
        (run / "summary.json").write_text(json.dumps(summary))
    return directory


def test_saved_ensemble_reanalysis_and_archive_roundtrip(
    saved_ensemble, tmp_path, monkeypatch
):
    from experiments.YH012.analyze_ensemble import analyze
    from experiments.YH012.archive_ensemble import archive
    from experiments.YH012 import plot

    monkeypatch.setattr(plot, "plot_ensemble", lambda *args, **kwargs: None)
    output = tmp_path / "report"
    result = analyze(saved_ensemble, output)
    assert result["n_seeds"] == 2
    assert result["tail"]["mean"] == 2
    assert result["tail"]["sd"] == pytest.approx(np.sqrt(8))
    assert result["tail"]["per_seed_time_mean"] == [0, 4]
    data = np.load(output / "ensemble_paths.npz")
    assert data["mean"][6] == 0
    assert data["sd"][6] == pytest.approx(np.sqrt(8))
    manifest = archive(saved_ensemble, output)
    for item in manifest["seeds"]:
        with tarfile.open(output / item["path"], "r:gz") as tar:
            for name in tar.getnames():
                assert (
                    tar.extractfile(name).read() == (saved_ensemble / name).read_bytes()
                )


def test_reanalysis_stops_on_corrupt_seed_before_writing_aggregate(
    saved_ensemble, tmp_path
):
    from experiments.YH012.analyze_ensemble import analyze

    path = saved_ensemble / "seed0001/factual.bin"
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA-256"):
        analyze(saved_ensemble, tmp_path / "report")
    assert not (tmp_path / "report").exists()


def test_incomplete_ensemble_cannot_produce_a_partial_mean(saved_ensemble, tmp_path):
    from experiments.YH012.analyze_ensemble import analyze

    (saved_ensemble / "progress.json").write_text(
        json.dumps({"status": "STOP", "completed": [0]})
    )
    with pytest.raises(ValueError, match="incomplete or stopped"):
        analyze(saved_ensemble, tmp_path / "report")
    assert not (tmp_path / "report").exists()


@pytest.fixture
def liquidity_diagnostic(tmp_path):
    from pathlib import Path
    from lobcore import ExperimentMeta, LOG_DTYPE, write_log_file
    from experiments.YH012 import run_ensemble

    source = Path(run_ensemble.__file__).parent
    config = {"end_time": 12, "impact": {"t0": 5, "t1": 7, "qty": 200}}
    provenance = {
        "model_source_sha256": {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in ("agents.py", "experiment.py")
        }
    }
    (tmp_path / "provenance.json").write_text(json.dumps(provenance))
    # Seed 13 is deliberately eligible: selection must depend on the quote,
    # never on the identity of the previously observed outlier.
    for seed, ask_qty in ((7, 0), (13, 1), (21, 2)):
        directory = tmp_path / f"seed{seed:04d}"
        directory.mkdir()
        quotes = np.array(
            [[1, 99, 1, 101, 1], [5, 99, 1, 101 if ask_qty else 0, ask_qty]]
        )
        path = directory / "native_quotes.npz"
        np.savez_compressed(path, quotes=quotes)
        log = np.zeros(1, dtype=LOG_DTYPE)
        meta = ExperimentMeta(
            seed,
            "price_time",
            2,
            1,
            6,
            "a" * 40,
            agent_config={"config": {**config, "seed": seed, "end_time": 6}},
        )
        write_log_file(directory / "background.bin", meta, log)
        summary = {
            "log": {
                "meta": asdict(meta),
                "n_records": 1,
                "log_sha256": hashlib.sha256(log.tobytes()).hexdigest(),
            },
            "native_quotes_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "at_t0": {
                "time": 5,
                "bid_price": 99,
                "bid_qty": 1,
                "ask_price": 101 if ask_qty else None,
                "ask_qty": ask_qty,
            },
        }
        (directory / "summary.json").write_text(json.dumps(summary))
    return tmp_path, config


def test_eligibility_uses_native_ask_at_fixed_time_not_seed_number(
    liquidity_diagnostic,
):
    from experiments.YH012.run_ensemble import select_eligible_seeds

    directory, config = liquidity_diagnostic
    selected, certificate = select_eligible_seeds(directory, [7, 13, 21], config)
    assert selected == [13, 21]
    assert certificate["excluded_seeds"] == [7]
    assert certificate["candidate_seeds"] == [7, 13, 21]
    assert len(certificate["observations"]) == 3


def test_eligibility_rejects_corrupt_native_quotes(liquidity_diagnostic):
    from experiments.YH012.run_ensemble import select_eligible_seeds

    directory, config = liquidity_diagnostic
    path = directory / "seed0013/native_quotes.npz"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="Native quotes SHA-256"):
        select_eligible_seeds(directory, [7, 13, 21], config)


def test_eligibility_rejects_different_experiment_configuration(liquidity_diagnostic):
    from experiments.YH012.run_ensemble import select_eligible_seeds

    directory, config = liquidity_diagnostic
    config["impact"]["t0"] = 4
    with pytest.raises(ValueError, match="configuration mismatch"):
        select_eligible_seeds(directory, [7, 13, 21], config)
