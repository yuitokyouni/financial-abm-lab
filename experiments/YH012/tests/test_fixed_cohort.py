import json

import pytest

from experiments.YH012.rerun_fixed_cohort import load_cohort, preflight


def test_archived_cohort_preserves_nonconsecutive_seed_ids(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"seeds": [0, 1, 14, 39], "config": {}}))
    assert load_cohort(path)["seeds"] == [0, 1, 14, 39]
    path.write_text(json.dumps({"seeds": [0, 1, 1]}))
    with pytest.raises(ValueError, match="unique"):
        load_cohort(path)


def test_absent_ask_records_every_seed_then_stops_without_selection(tmp_path):
    plan = {
        "seeds": [0, 14],
        "config": {
            "end_time": 20, "impact": {"t0": 10, "t1": 20, "qty": 200},
            "agents": {"n_fundamentalist": 0, "n_chartist": 0, "n_noise": 0},
        },
    }
    from experiments.YH012.version import lobcore_git_hash
    plan["lobcore_commit"] = lobcore_git_hash()
    with pytest.raises(ValueError, match="absent ask"):
        preflight(plan, tmp_path / "check")
    result = json.loads((tmp_path / "check/summary.json").read_text())
    assert result["missing_ask_seeds"] == [0, 14]
    assert [r["seed"] for r in result["observations"]] == plan["seeds"]
    assert all((tmp_path / f"check/seed{s:04d}.bin").exists() for s in plan["seeds"])
