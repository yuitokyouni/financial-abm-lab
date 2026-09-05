from dataclasses import asdict
import hashlib

import numpy as np
import pytest
from lobcore import ExperimentMeta, LOG_DTYPE, write_log_file

from experiments.YH012.impact import ImpactSeries
from experiments.YH012.inspect_saved_pair import read_verified_log, time_structure


def test_saved_reader_preserves_padding_and_rejects_corruption(tmp_path):
    raw = bytearray(LOG_DTYPE.itemsize)
    raw[11:16] = b"abcde"
    log = np.frombuffer(raw, dtype=LOG_DTYPE)
    meta = ExperimentMeta(42, "price_time", 2, 1, 20, "a" * 40)
    path = tmp_path / "factual.bin"
    write_log_file(str(path), meta, log)
    expected = {
        "meta": asdict(meta),
        "log_sha256": hashlib.sha256(raw).hexdigest(),
        "n_records": 1,
    }
    restored_meta, restored = read_verified_log(path, expected)
    assert restored.tobytes() == raw
    assert restored_meta == meta
    corrupted = bytearray(path.read_bytes())
    corrupted[-1] ^= 1
    path.write_bytes(corrupted)
    with pytest.raises(ValueError, match="SHA-256"):
        read_verified_log(path, expected)


def test_zero_return_is_distinct_from_later_persistent_zero():
    series = ImpactSeries(
        np.array([0, 2, 4, 6, 8, 10]), np.array([0, 1, 0, -2, 0, 0]), np.zeros(6)
    )
    result = time_structure(series, t0=1, t1=3, end_time=10, tail_start=8)
    assert result["onset"] == {"time": 2, "delta": 1.0}
    assert result["first_zero_after_onset"] == 4
    assert result["zero_through_end_since"] == 8
    assert result["late_window"]["time_mean_delta"] == 0
    assert result["full_post_time_mean_delta"] == pytest.approx(-2 / 9)


def test_nonzero_tail_is_not_reported_as_a_zero_return():
    series = ImpactSeries(np.array([0, 2, 10]), np.array([0, 1, 1]), np.zeros(3))
    result = time_structure(series, t0=1, t1=3, end_time=10, tail_start=8)
    assert result["zero_through_end_since"] is None
    assert result["first_zero_after_onset"] is None
    assert result["late_window"]["time_mean_delta"] == 1


def test_missing_tail_is_not_reported_as_zero():
    series = ImpactSeries(
        np.array([0, 2, 8, 10]), np.array([0, 1, np.nan, np.nan]), np.zeros(4)
    )
    with pytest.raises(ValueError, match="coverage"):
        time_structure(series, t0=1, t1=3, end_time=10, tail_start=8)
