"""Full-fidelity literature snapshot round-trip (dump -> json -> restore)."""
from __future__ import annotations

import json


def test_snapshot_roundtrip_is_lossless(tmp_path):
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata,
        update_literature_extraction, set_literature_code_url,
        dump_literature_snapshot, restore_literature_snapshot,
    )
    src = str(tmp_path / "src.db")
    dst = str(tmp_path / "dst.db")
    ensure_literature_schema(src)
    # a row exercising every column class: commas in text, enrichment,
    # multi-value tag/fact columns, an oa: synthetic id
    upsert_literature_metadata(
        src, arxiv_id="oa:W123", title="A title, with commas",
        authors="X, Y", year=2024, published_date="2024-01-01",
        primary_category=None, abstract="abstract text",
        source_kind="openalex")
    update_literature_extraction(
        src, "oa:W123", mechanism_summary="mech",
        mechanism_tags=["order-book", "herding"],
        stylized_facts_targeted=["fat-tails", "leverage"],
        novelty_signal="novel", relevance_score=0.77,
        extracted_by_model="test-model")
    set_literature_code_url(src, "oa:W123",
                             code_url="https://github.com/a/b", source="abstract")

    snap = dump_literature_snapshot(src)
    # survive a real JSON serialise/deserialise
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap, ensure_ascii=False, default=str))
    reloaded = json.loads(p.read_text())

    n = restore_literature_snapshot(dst, reloaded)
    assert n == 1
    src_row = dump_literature_snapshot(src)[0]
    dst_row = dump_literature_snapshot(dst)[0]
    assert src_row == dst_row, "snapshot round-trip is not lossless"
    # enrichment columns specifically survived (the old restore dropped them)
    assert dst_row["code_url"] == "https://github.com/a/b"
    assert dst_row["source_kind"] == "openalex"
    assert dst_row["title"] == "A title, with commas"


def test_snapshot_restore_is_idempotent(tmp_path):
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata,
        dump_literature_snapshot, restore_literature_snapshot,
    )
    src = str(tmp_path / "s.db")
    ensure_literature_schema(src)
    upsert_literature_metadata(
        src, arxiv_id="2401.1", title="T", authors="A", year=2024,
        published_date="2024-01-01", primary_category="q-fin.TR",
        abstract="a", source_kind="arxiv")
    snap = dump_literature_snapshot(src)
    dst = str(tmp_path / "d.db")
    restore_literature_snapshot(dst, snap)
    restore_literature_snapshot(dst, snap)  # twice
    assert len(dump_literature_snapshot(dst)) == 1  # no duplicate


def test_snapshot_cli_handlers_round_trip(tmp_path):
    # Drive the actual CLI command handlers (not just the db-layer helpers).
    # Regression guard: the handlers import os locally, and a missing import
    # there fails only through this argparse dispatch path, not the db tests.
    from argparse import Namespace
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata,
    )
    from fingerprint_atlas.arxiv_cli import cmd_snapshot_save, cmd_snapshot_restore

    src = str(tmp_path / "src.db")
    ensure_literature_schema(src)
    upsert_literature_metadata(
        src, arxiv_id="2401.9", title="Row, with comma", authors="A",
        year=2024, published_date="2024-01-01", primary_category="q-fin.TR",
        abstract="a", source_kind="arxiv")

    out = str(tmp_path / "nested" / "snap.json")  # parent dir must be created
    assert cmd_snapshot_save(Namespace(db=src, out=out)) == 0

    dst = str(tmp_path / "dst.db")
    rc = cmd_snapshot_restore(Namespace(db=dst, snapshot=out, no_replace=False))
    assert rc == 0

    from fingerprint_atlas.db import dump_literature_snapshot
    assert dump_literature_snapshot(dst)[0]["title"] == "Row, with comma"


def test_snapshot_save_warns_and_fails_on_empty_db(tmp_path):
    from argparse import Namespace
    from fingerprint_atlas.db import ensure_literature_schema
    from fingerprint_atlas.arxiv_cli import cmd_snapshot_save
    empty = str(tmp_path / "empty.db")
    ensure_literature_schema(empty)
    out = str(tmp_path / "snap.json")
    # 0 rows -> non-zero exit so a mis-pointed --db can't silently overwrite
    # a good snapshot with an empty one.
    assert cmd_snapshot_save(Namespace(db=empty, out=out)) == 1
