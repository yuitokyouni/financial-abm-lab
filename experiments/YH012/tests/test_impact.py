from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from lobcore import (
    Agent,
    Context,
    Experiment,
    ExperimentMeta,
    ExperimentPairResult,
    ExperimentResult,
    LOG_DTYPE,
    logs_byte_equal,
    read_log_file,
    write_log_file,
)
from lobcore.agent import LevelView, MarketView, View

from experiments.YH012.agents import ImpactAgent
from experiments.YH012.experiment import ImpactExperiment, _kernel_log
from experiments.YH012.impact import (
    CounterfactualMismatch,
    align_mid_series,
    assert_pre_intervention_equal,
    time_mean_delta,
)
from experiments.YH012.version import default_lobcore_root


def test_impact_waits_then_submits_one_aggressive_buy():
    agent = ImpactAgent(t0=10, qty=12, price_offset=2)
    market = MarketView(LevelView(99, 10), LevelView(101, 5))
    before = Context(3, 1)
    agent.on_wakeup(View(1, [market]), before)
    assert not before.orders
    assert before.next_wakeup == 10
    at = Context(3, 10)
    agent.on_wakeup(View(10, [market]), at)
    assert len(at.orders) == 1
    order = at.orders[0].msg
    assert (order.price, order.qty, order.id) == (103, 12, (3 << 32) + 1)
    assert at.next_wakeup is None
    later = Context(3, 11)
    agent.on_wakeup(View(11, [market]), later)
    assert not later.orders


def test_impact_fails_explicitly_without_ask():
    agent = ImpactAgent(t0=10, qty=12, price_offset=2)
    with pytest.raises(RuntimeError, match="ask"):
        agent.on_wakeup(View(10, [MarketView(None, None)]), Context(3, 10))


def _log(times, bids, asks):
    result = np.zeros(len(times), dtype=LOG_DTYPE)
    result["received_at"] = times
    result["best_bid_price"] = bids
    result["best_ask_price"] = asks
    result["best_bid_qty"] = result["best_ask_qty"] = 1
    return result


def test_alignment_keeps_unmatched_times_and_last_same_time_snapshot():
    f = _log([2, 4, 4, 8], [99, 99, 101, 103], [101, 101, 103, 105])
    b = _log([3, 5, 9], [99, 99, 99], [101, 101, 101])
    series = align_mid_series(f, b, boundaries=(1, 10))
    assert series.times.tolist() == [1, 2, 3, 4, 5, 8, 9, 10]
    assert np.isnan(series.delta[:2]).all()  # no look-ahead before both observations
    np.testing.assert_equal(series.delta[2:], [0, 2, 2, 4, 4, 4])
    assert time_mean_delta(series, t0=3, t1=10) == pytest.approx(16 / 7)


def test_missing_mid_window_is_rejected():
    f = _log([3], [99], [101])
    series = align_mid_series(f, f, boundaries=(1, 10))
    with pytest.raises(ValueError, match="coverage"):
        time_mean_delta(series, t0=1, t1=10)


def test_empty_book_does_not_carry_a_stale_mid():
    f = _log([2, 4, 6], [99, 0, 99], [101, 0, 101])
    f["best_bid_qty"][1] = f["best_ask_qty"][1] = 0
    b = _log([2, 4, 6], [99, 99, 99], [101, 101, 101])
    series = align_mid_series(f, b, boundaries=(2, 8))
    assert np.isnan(series.delta[1])
    with pytest.raises(ValueError, match="coverage"):
        time_mean_delta(series, t0=2, t1=8)


def test_prefix_gate_rejects_changed_fields_and_padding():
    f = _log([2, 4], [99, 99], [101, 101])
    b = np.frombuffer(f.tobytes(), dtype=LOG_DTYPE)
    assert_pre_intervention_equal(f, b, t0=4)
    changed = bytearray(f.tobytes())
    changed[11] ^= 1  # aligned LogRecord padding; np.array_equal alone misses this
    b = np.frombuffer(changed, dtype=LOG_DTYPE)
    assert logs_byte_equal(f, b)
    with pytest.raises(CounterfactualMismatch, match="byte"):
        assert_pre_intervention_equal(f, b, t0=4)
    b = _log([2, 4], [98, 99], [101, 101])
    with pytest.raises(CounterfactualMismatch):
        assert_pre_intervention_equal(f, b, t0=4)


class _Quotes(Agent):
    def __init__(self):
        self.started = False

    def on_wakeup(self, view, ctx):
        if view.now == 1 and not self.started:
            ctx.submit(0, "buy", 99, 100)
            ctx.submit(0, "sell", 101, 5)
            ctx.submit(0, "sell", 103, 100)
            self.started = True
        if view.now < 20:
            # A harmless deep bid supplies post-intervention snapshots.
            ctx.submit(0, "buy", 90, 1)
            ctx.schedule_wakeup(view.now + 1)


def _config():
    return {
        "seed": 42,
        "end_time": 20,
        "agents": {"n_fundamentalist": 1, "n_chartist": 0, "n_noise": 0},
        "impact": {"t0": 10, "t1": 20, "qty": 6, "price_offset": 0},
    }


def test_pair_fresh_agents_auto_ids_and_metadata(monkeypatch, tmp_path):
    import experiments.YH012.experiment as module

    monkeypatch.setattr(module, "build_world_agents", lambda **kwargs: [_Quotes()])
    exp = ImpactExperiment(_config())
    assert ImpactExperiment.run_pair is Experiment.run_pair
    pair = exp.run_pair(suppress_agent_ids=[exp.impact_id])
    assert_pre_intervention_equal(pair.factual.log, pair.baseline.log, t0=10)
    adds = pair.factual.log[pair.factual.log["kind"] == 0]
    assert len(np.unique(adds["order_id"])) == len(adds)
    assert not np.any(pair.factual.log["kind"] == 3)
    impact = adds[adds["order_id"] >> 32 == exp.impact_id]
    assert len(impact) == 1
    assert int(impact[0]["decided_at"]) == 10
    assert int(impact[0]["received_at"]) == 11
    assert not np.any(pair.baseline.log["order_id"] >> 32 == exp.impact_id)
    series = align_mid_series(pair.factual.log, pair.baseline.log, boundaries=(10, 20))
    assert time_mean_delta(series, t0=10, t1=20) > 0
    expected = subprocess.check_output(
        ["git", "-C", str(default_lobcore_root()), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    for label, result in (("f", pair.factual), ("b", pair.baseline)):
        assert result.meta.lobcore_version == expected
        path = tmp_path / f"{label}.bin"
        write_log_file(str(path), result.meta, result.log)
        meta, log = read_log_file(str(path))
        assert meta.lobcore_version == expected
        assert logs_byte_equal(log, result.log)
    again = exp.run_pair(suppress_agent_ids=[exp.impact_id])
    for first, second in (
        (pair.factual, again.factual),
        (pair.baseline, again.baseline),
    ):
        assert first.log.tobytes() == second.log.tobytes()
        assert first.state_hash == second.state_hash


def test_native_log_capture_preserves_all_bytes():
    raw = bytearray(LOG_DTYPE.itemsize)
    raw[11:16] = b"abcde"

    class FakeKernel:
        def log_bytes(self):
            return bytes(raw)

    assert _kernel_log(FakeKernel()).tobytes() == raw


def test_cli_stops_before_metrics_or_plot_on_prefix_mismatch(monkeypatch, tmp_path):
    from experiments.YH012 import run_impact

    meta = ExperimentMeta(42, "price_time", 2, 1, 20, lobcore_version="a" * 40)
    f = ExperimentResult(_log([2, 11], [99, 100], [101, 102]), meta, 1)
    b = ExperimentResult(_log([2, 11], [98, 99], [101, 101]), meta, 2)
    exp = SimpleNamespace(
        seed=42,
        impact_id=1,
        qty=6,
        t0=10,
        t1=20,
        price_offset=0,
        run_pair=lambda **kwargs: ExperimentPairResult(f, b, (1,)),
    )
    monkeypatch.setattr(run_impact.ImpactExperiment, "from_yaml", lambda path: exp)

    def forbidden(*args, **kwargs):
        pytest.fail("Analysis ran after a failed prefix gate")

    monkeypatch.setattr(run_impact, "align_mid_series", forbidden)
    monkeypatch.setattr(sys, "argv", ["run_impact", "--out-dir", str(tmp_path)])
    assert run_impact.main() == 2
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["prefix"]["byte_equal"] is False
    assert "mean_delta" not in summary
    assert not (tmp_path / "impact.png").exists()


@pytest.mark.parametrize(
    "override", [{"t0": 1}, {"t1": 10}, {"t1": 21}, {"qty": 0}, {"price_offset": -1}]
)
def test_invalid_impact_config_is_rejected(override):
    config = _config()
    config["impact"].update(override)
    with pytest.raises(ValueError):
        ImpactExperiment(config)
