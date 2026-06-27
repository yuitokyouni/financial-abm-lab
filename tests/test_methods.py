"""Tests for the methodology-commentary store and CLI parsing.

  1. Schema creation is idempotent.
  2. Seeding is idempotent (re-running inserts 0 new rows).
  3. CRUD: list / get / update_method round-trips.
  4. Markdown edit-file: render → user edits → parse extracts the four
     commentary sections correctly, ignoring the read-only header.
  5. Names in SEED match the live `abm_models.REGISTRY` + the 3 synthetics
     (so the methods table is keyed the same way as runs.model_name).
"""
from __future__ import annotations

import os
import tempfile

import pytest

from abm_models import REGISTRY
from fingerprint_atlas.methods import (
    SEED, Method, ensure_methods_schema, get_method, list_methods,
    seed_methods, update_method,
)
from fingerprint_atlas.methods_cli import _parse_edit_file, _render_edit_file
from fingerprint_atlas import synthetic


def _tmpdb():
    return tempfile.NamedTemporaryFile(suffix=".db", delete=False).name


def test_schema_idempotent():
    db = _tmpdb()
    ensure_methods_schema(db)
    ensure_methods_schema(db)  # second call is a no-op
    # the table exists
    rs = list_methods(db)
    assert rs == []


def test_seed_idempotent_and_inserts_all():
    db = _tmpdb()
    res = seed_methods(db)
    assert res["inserted"] == len(SEED)
    res2 = seed_methods(db)
    assert res2["inserted"] == 0
    rs = list_methods(db)
    assert len(rs) == len(SEED)
    names = {m.name for m in rs}
    assert names == {s["name"] for s in SEED}


def test_seed_overwrite_mechanism_keeps_user_commentary():
    db = _tmpdb()
    seed_methods(db)
    update_method(db, "speculation_game",
                  novelty_notes="my note",
                  tags="novelty:high, mechanism:strong")
    seed_methods(db, overwrite_mechanism=True)
    m = get_method(db, "speculation_game")
    assert m is not None
    assert m.novelty_notes == "my note"
    assert "novelty:high" in m.tag_list


def test_update_method_only_touches_provided_fields():
    db = _tmpdb()
    seed_methods(db)
    update_method(db, "lux_marchesi", novelty_notes="a")
    m1 = get_method(db, "lux_marchesi")
    assert m1.novelty_notes == "a"
    assert m1.mechanism_strengths == ""
    update_method(db, "lux_marchesi", mechanism_strengths="b")
    m2 = get_method(db, "lux_marchesi")
    assert m2.novelty_notes == "a"   # preserved
    assert m2.mechanism_strengths == "b"


def test_update_method_raises_for_unknown_name():
    db = _tmpdb()
    seed_methods(db)
    with pytest.raises(KeyError):
        update_method(db, "no_such_method", novelty_notes="x")


def test_render_parse_roundtrip_empty_commentary():
    """Render an empty-commentary method, parse it back; all sections empty."""
    db = _tmpdb()
    seed_methods(db)
    m = get_method(db, "speculation_game")
    text = _render_edit_file(m)
    parsed = _parse_edit_file(text)
    for sec in ("novelty_notes", "mechanism_strengths",
                "mechanism_weaknesses", "research_questions", "tags"):
        assert parsed[sec] == "", f"{sec} should be empty: {parsed[sec]!r}"


def test_parse_edit_file_extracts_filled_sections():
    text = """\
# methodology notes for: speculation_game
# kind: abm     refs: arXiv:...
# mechanism: ... read-only comment ...

## novelty_notes
strategy-bank-with-cognitive-price is a fresh
angle vs plain MG

## mechanism_strengths
- captures herding via switching intensity

## mechanism_weaknesses
- chartist signal is too symmetric

## research_questions
can the cognitive price be replaced with a learned representation?

## tags
novelty:high, mechanism:medium, borrowable
"""
    parsed = _parse_edit_file(text)
    assert "strategy-bank" in parsed["novelty_notes"]
    assert "angle vs plain MG" in parsed["novelty_notes"]
    assert "captures herding" in parsed["mechanism_strengths"]
    assert "too symmetric" in parsed["mechanism_weaknesses"]
    assert "cognitive price be replaced" in parsed["research_questions"]
    assert "novelty:high" in parsed["tags"]


def test_parse_edit_file_ignores_unknown_sections():
    text = """\
## novelty_notes
something
## made_up_section
ignored content
## tags
t1, t2
"""
    parsed = _parse_edit_file(text)
    assert parsed["novelty_notes"].strip() == "something"
    assert parsed["tags"].strip() == "t1, t2"
    assert "ignored" not in parsed["novelty_notes"]


def test_parse_edit_file_strips_comment_lines_in_body():
    """The mechanism block is rendered as # comments; parse must drop them."""
    text = """\
## novelty_notes
# this is a leftover mechanism comment line
real user content
"""
    parsed = _parse_edit_file(text)
    assert parsed["novelty_notes"] == "real user content"


def test_method_names_align_with_runs_keys():
    """The 8 abm + 3 synthetic in SEED must match REGISTRY + SYNTHETIC_BOUNDS."""
    seed_names = {s["name"] for s in SEED}
    expected_abm = set(REGISTRY.keys())
    expected_synth = set(synthetic.SYNTHETIC_BOUNDS.keys())
    assert expected_abm.issubset(seed_names), (
        f"missing ABM seed for: {expected_abm - seed_names}"
    )
    assert expected_synth.issubset(seed_names), (
        f"missing synthetic seed for: {expected_synth - seed_names}"
    )
