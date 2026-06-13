"""共有 provenance パッケージの round-trip + 後方互換テスト (spec 001 O5)。

capital-allocation/prov_record.py と同一の record 構造を保つことを確認する
(cap-alloc を壊さず移行できる前提)。
"""

from __future__ import annotations

import json

from provenance import emit_prov


def test_emit_prov_roundtrip(tmp_path):
    ein = {"id": "data:pre", "sha256": "abc"}
    eout = {"id": "data:weights", "sha256": "def"}
    rec = emit_prov("calibrate", ein, eout, agent="pipeline", run_id="r1",
                    prov_dir=str(tmp_path))

    path = tmp_path / "calibrate_r1.json"
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk == rec


def test_emit_prov_record_structure_backward_compat():
    """元 prov_record.py が出していたキー構造を保持。"""
    rec = emit_prov("act", {"id": "e_in"}, {"id": "e_out"}, prov_dir="prov_test_tmp")
    assert set(rec) == {
        "prov:activity",
        "prov:entity_in",
        "prov:entity_out",
        "prov:used",
        "prov:wasAssociatedWith",
        "prov:wasGeneratedBy",
    }
    assert rec["prov:activity"]["id"] == "act"
    assert rec["prov:used"]["entity"] == "e_in"
    assert rec["prov:wasGeneratedBy"]["entity"] == "e_out"
    import shutil
    shutil.rmtree("prov_test_tmp", ignore_errors=True)
