"""provenance: prov.json 構築・命名・round-trip(§13.1 / CLAUDE.md 命名規約)。"""

from __future__ import annotations

import json
from pathlib import Path

from provabm.provenance import (
    ProvenanceRecorder,
    config_hash,
    new_uuid7,
    output_basename,
    output_sha256,
    prov_path_for,
    seed_dict,
)
from provabm.validator import validate_provenance


def test_config_hash_deterministic() -> None:
    assert config_hash("a: 1\nb: 2\n") == config_hash("a: 1\nb: 2\n")
    assert config_hash("a: 1") != config_hash("a: 2")


def test_output_sha256(tmp_path: Path) -> None:
    f = tmp_path / "out.bin"
    f.write_bytes(b"hello")
    # sha256("hello")
    assert output_sha256(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_uuid7_unique_and_sortable() -> None:
    ids = [new_uuid7() for _ in range(50)]
    assert len(set(ids)) == 50  # 一意
    # uuid7 は時刻順なので生成順で概ね昇順(strict は保証しないが単調性を確認)。
    assert ids == sorted(ids)


def test_output_basename_naming() -> None:
    name = output_basename("0123456789abcdef", 42, "uuid-xyz")
    assert name == "0123456789ab_42_uuid-xyz"


def test_prov_path_sidecar() -> None:
    assert prov_path_for("runs/abc.parquet") == Path("runs/abc.parquet.prov.json")


def test_recorder_roundtrip_passes_validator(tmp_path: Path) -> None:
    out = tmp_path / "run.parquet"
    out.write_bytes(b"fake-parquet-bytes")
    log = tmp_path / "ctx.parquet"
    log.write_bytes(b"")

    rec = ProvenanceRecorder(
        config_yaml="market:\n  N: 500\n",
        seed=seed_dict(numpy=7, python=7, torch=None),
        repo=tmp_path,
    )
    prov = rec.complete(output_path=out, ctx_log_path=log)
    prov_file = prov.write(prov_path_for(out))

    loaded = json.loads(prov_file.read_text(encoding="utf-8"))
    # v0 の prov.json は validator を通る(reach_claim=reported、全必須フィールド有り)。
    validate_provenance(loaded)
    assert loaded["reach_claim"] == "reported"
    assert loaded["output_sha256"] == output_sha256(out)
    assert loaded["seed"]["numpy"] == 7
