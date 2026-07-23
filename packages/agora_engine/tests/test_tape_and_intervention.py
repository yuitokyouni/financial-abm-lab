import json

import pytest

from agora_engine import DecisionMatrix, Intervention, build_matrix_sidecar, load_sidecar, sha256_file, write_sidecar


def test_intervention_round_trip_and_unknown_type_warns():
    iv = Intervention(t=3, type="advisor_correlation", target="market", params={"n_advisors": 1})
    assert Intervention.from_dict(iv.to_dict()) == iv
    with pytest.warns(UserWarning, match="unknown intervention type"):
        Intervention(t=0, type="not_a_type", target="x")


def test_sidecar_build_write_load(tmp_path):
    dm = DecisionMatrix.from_long([("m1", "p1", 1.0), ("m2", "p1", -1.0)])
    src_file = tmp_path / "raw.xlsx"
    src_file.write_bytes(b"dummy")
    sources = [{
        "manager": "m1", "url": "https://example.com/raw.xlsx",
        "retrieved_at": "2026-07-23T03:00:00Z", "format": "xlsx",
        "parser": "dummy", "file_sha256": sha256_file(src_file),
    }]
    side = build_matrix_sidecar(
        "yh010g-A-test", sources, dm, extra={"coverage": {"meetings": 1}}
    )
    out = tmp_path / "side.json"
    write_sidecar(out, side)
    loaded = load_sidecar(out)
    assert loaded["matrix_id"] == "yh010g-A-test"
    assert loaded["coverage"]["managers"] == 2
    assert loaded["coverage"]["meetings"] == 1
    assert loaded["coverage"]["cells_observed"] == 2
    assert loaded["provenance"]["verified"] is False
    # sha256 は安定
    assert sources[0]["file_sha256"] == sha256_file(src_file)


def test_sidecar_missing_keys_rejected(tmp_path):
    with pytest.raises(ValueError, match="missing required"):
        write_sidecar(tmp_path / "bad.json", {"matrix_id": "x"})
    good = tmp_path / "good.json"
    dm = DecisionMatrix.from_long([("m", "p", 1.0)])
    write_sidecar(good, build_matrix_sidecar("id", [], dm))
    broken = json.loads(good.read_text())
    del broken["encoding"]
    bad = tmp_path / "b2.json"
    bad.write_text(json.dumps(broken))
    with pytest.raises(ValueError, match="missing required"):
        load_sidecar(bad)
