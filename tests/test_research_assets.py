from __future__ import annotations

import hashlib
import json

import pytest

from tools.research_assets import find_ref, load_catalog, sha256


def test_catalog_load_and_find(tmp_path):
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps({
        "schema_version": 1,
        "references": [{"id": "katahira2019", "drive_file_id": "abc"}],
    }))
    doc = load_catalog(p)
    assert find_ref(doc, "katahira2019")["drive_file_id"] == "abc"


def test_catalog_rejects_unknown_schema(tmp_path):
    p = tmp_path / "catalog.json"
    p.write_text('{"schema_version": 99, "references": []}')
    with pytest.raises(SystemExit):
        load_catalog(p)


def test_sha256(tmp_path):
    p = tmp_path / "x"
    p.write_bytes(b"abc")
    assert sha256(p) == hashlib.sha256(b"abc").hexdigest()


def test_find_ref_unknown():
    with pytest.raises(SystemExit):
        find_ref({"references": []}, "missing")
