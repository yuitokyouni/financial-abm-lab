"""Experiment inputs resolve independently of the launch directory."""
from pathlib import Path

from yh010g.paths import EXPERIMENT_ROOT, RAW_DIR, OUT_DIR, FIXTURE_DIR
from yh010g.validate_policy import GROUND_TRUTH


def test_paths_are_experiment_owned():
    expected = Path(__file__).resolve().parents[1]
    assert EXPERIMENT_ROOT == expected
    assert RAW_DIR == expected / "data/raw"
    assert OUT_DIR == expected / "data/processed"
    assert FIXTURE_DIR == expected / "data/fixtures"


def test_ground_truth_is_available_from_other_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert GROUND_TRUTH.is_file()
    assert GROUND_TRUTH.parent == FIXTURE_DIR
    assert GROUND_TRUTH.read_text(encoding="utf-8").splitlines()[0].startswith("key,sec_code,")
