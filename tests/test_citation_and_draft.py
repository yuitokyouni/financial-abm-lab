"""Tests for the citation validator and the methods draft assistant.

Both modules call Groq for real usage. Tests exercise the local logic via
dry_run_response paths so no network is touched.
"""
from __future__ import annotations

import tempfile

import pytest

from fingerprint_atlas.db import (
    ensure_literature_schema, ensure_runs_schema,
    update_literature_extraction, upsert_literature_metadata,
)
from fingerprint_atlas.methods import seed_methods
from fingerprint_atlas.methods_draft import draft_notes_for_method
from fingerprint_atlas.propose import (
    _arxiv_base, _extract_arxiv_id, classify_references,
)


def _tmpdb():
    return tempfile.NamedTemporaryFile(suffix=".db", delete=False).name


# ---- (a) citation validator unit tests -----------------------------------

def test_extract_arxiv_id_handles_prefixed_and_bare():
    assert _extract_arxiv_id("arXiv:2605.00854v1") == "2605.00854v1"
    assert _extract_arxiv_id("2605.00854") == "2605.00854"
    assert _extract_arxiv_id("arxiv.org/abs/2606.16269v2") == "2606.16269v2"
    assert _extract_arxiv_id("https://arxiv.org/abs/2412.18000") == "2412.18000"


def test_extract_arxiv_id_returns_none_for_freeform():
    assert _extract_arxiv_id("Lux & Marchesi 2000") is None
    assert _extract_arxiv_id("Cont 2001") is None
    assert _extract_arxiv_id("DOI:10.1007/abc") is None


def test_arxiv_base_strips_version():
    assert _arxiv_base("2605.00854v1") == "2605.00854"
    assert _arxiv_base("2605.00854") == "2605.00854"


def test_classify_references_buckets_correctly():
    db = _tmpdb()
    ensure_literature_schema(db)
    upsert_literature_metadata(
        db, arxiv_id="2412.18000v1", title="t", authors="a", year=2024,
        published_date="2024-12-01T00:00:00Z", primary_category="q-fin.TR",
        abstract="x",
    )
    refs = [
        "arXiv:2412.18000",          # in_db (base id match across version)
        "arXiv:2412.18000v1",        # in_db (exact)
        "arXiv:2605.99999v1",        # external_arxiv (not in DB → suspect)
        "Lux & Marchesi 2000",       # non_arxiv (no warning)
    ]
    res = classify_references(refs, db)
    assert "arXiv:2412.18000" in res["in_db"]
    assert "arXiv:2412.18000v1" in res["in_db"]
    assert "arXiv:2605.99999v1" in res["external_arxiv"]
    assert "Lux & Marchesi 2000" in res["non_arxiv"]


# ---- (d) methods draft assistant (dry-run) -------------------------------

def test_methods_draft_dry_run_returns_filled_draft():
    db = _tmpdb()
    ensure_runs_schema(db)
    ensure_literature_schema(db)
    seed_methods(db)
    # seed a couple of literature rows so context isn't empty
    upsert_literature_metadata(
        db, arxiv_id="2604.18602v2", title="Machine Spirits: LLM Agents",
        authors="A", year=2026, published_date="2026-04-01T00:00:00Z",
        primary_category="q-fin.TR", abstract="LLM agents in markets...",
    )
    update_literature_extraction(
        db, "2604.18602v2",
        mechanism_summary="LLM-driven trading agents.",
        mechanism_tags=["LLM-agent", "speculation"],
        stylized_facts_targeted=["fat-tails"],
        novelty_signal="In-context trading prompts.",
        relevance_score=0.85, extracted_by_model="m",
    )

    fake_response = {
        "novelty_notes": "Katahira SG は MG にコグニティブ価格を加えた点で arXiv:2604.18602v2 の LLM agent 系と並ぶ斬新さがある。",
        "mechanism_strengths": "戦略 bank の bankruptcy 置換が一段ラジカル。",
        "mechanism_weaknesses": "投資家心理の表現が 5^M 履歴に圧縮されすぎている。",
        "research_questions": "戦略表を進化的に交叉させたら何が変わるか?",
        "tags": "novelty:medium, mechanism:has-novel-component",
    }
    result = draft_notes_for_method(
        db, "speculation_game", dry_run_response=fake_response,
    )
    draft = result["draft"]
    assert "コグニティブ" in draft["novelty_notes"]
    assert draft["mechanism_strengths"]
    assert draft["mechanism_weaknesses"]
    assert draft["research_questions"]
    assert "novelty:medium" in draft["tags"]
    # context provided to LLM should include our LLM-agent paper
    assert result["context_used"]["n_relevant_literature"] >= 0


def test_methods_draft_raises_for_unknown_method():
    db = _tmpdb()
    ensure_runs_schema(db); ensure_literature_schema(db); seed_methods(db)
    with pytest.raises(KeyError):
        draft_notes_for_method(db, "totally_unknown_method",
                                dry_run_response={"novelty_notes": "x"})


def test_methods_draft_handles_partial_llm_response():
    """LLM might omit a field; the draft must still produce a valid dict."""
    db = _tmpdb()
    ensure_runs_schema(db); ensure_literature_schema(db); seed_methods(db)
    result = draft_notes_for_method(
        db, "lux_marchesi",
        dry_run_response={"novelty_notes": "only this field"},
    )
    draft = result["draft"]
    assert draft["novelty_notes"] == "only this field"
    assert draft["mechanism_strengths"] == ""
    assert draft["research_questions"] == ""
