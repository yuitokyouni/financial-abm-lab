"""Tests for the idea → judge → plan → scaffold pipeline.

Network is never touched: every LLM call is bypassed via dry_run hooks.
The scaffold tests write to a tmp packages tree so they don't pollute the
real workspace.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from fingerprint_atlas.adapters import build_model, series_for_fingerprint
from fingerprint_atlas.db import (
    ensure_ideas_schema, ensure_proposals_schema, ensure_runs_schema,
    insert_idea, insert_run, load_ideas, load_proposals, update_idea,
)
from fingerprint_atlas.fingerprint import FEATURE_NAMES, fingerprint
from fingerprint_atlas.idea_judge import (
    _tokens, rank_methods, rank_literature, rank_proposals, judge_idea,
)
from fingerprint_atlas.idea_plan import (
    make_plan, scaffold, scaffold_mechanism_combo, scaffold_new_method,
    scaffold_param_sweep, _camel_to_snake,
)
from fingerprint_atlas.methods import seed_methods


def _tmpdb():
    return tempfile.NamedTemporaryFile(suffix=".db", delete=False).name


def _populate_minimal(tmpdir: str) -> str:
    db = os.path.join(tmpdir, "t.db")
    ensure_runs_schema(db)
    ensure_ideas_schema(db)
    ensure_proposals_schema(db)
    seed_methods(db)
    # one SG run for rank_proposals to have a target
    m = build_model("speculation_game", dict(N=80, M=2, S=2, T=400))
    res = m.run(seed=1)
    series, kind = series_for_fingerprint("speculation_game", res)
    fp = fingerprint(series, compute_hill=True)
    insert_run(db, model_name="speculation_game", params={}, seed=1,
               fingerprint_vec=fp, series_kind=kind,
               series_length=len(series),
               provenance={"git_commit": "test"},
               created_at="2026-06-27T00:00:00Z", origin="abm")
    return db


# ---- ideas schema --------------------------------------------------------

def test_ideas_schema_idempotent():
    db = _tmpdb()
    ensure_ideas_schema(db)
    ensure_ideas_schema(db)
    assert load_ideas(db) == []


def test_insert_load_idea_roundtrip():
    db = _tmpdb()
    ensure_ideas_schema(db)
    aspects = {"agent_types": ["LLM-trader"], "key_keywords": ["sentiment"]}
    judgment = {"verdict": {"category": "incremental_novelty"}}
    rid = insert_idea(db, idea_text="my idea", aspects=aspects,
                     judgment=judgment, judgment_llm_model="m", status="judged")
    rows = load_ideas(db)
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["aspects"]["agent_types"] == ["LLM-trader"]
    assert rows[0]["judgment"]["verdict"]["category"] == "incremental_novelty"


def test_update_idea_partial():
    db = _tmpdb()
    ensure_ideas_schema(db)
    rid = insert_idea(db, idea_text="x")
    update_idea(db, rid, status="planned", plan={"implementation_type": "param_sweep"})
    rows = load_ideas(db)
    assert rows[0]["status"] == "planned"
    assert rows[0]["plan"]["implementation_type"] == "param_sweep"
    # idea_text untouched
    assert rows[0]["idea_text"] == "x"


# ---- ranking helpers -----------------------------------------------------

def test_tokens_normalises_and_filters_short_words():
    assert _tokens("Order-Book + LLM agents") >= {"order-book", "llm", "agents"}
    assert "+" not in _tokens("a + b")


def test_rank_methods_returns_top_k_with_score():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        aspects = {"key_keywords": ["minority", "strategy", "switching"],
                   "agent_types": ["adaptive"],
                   "target_stylized_facts": [], "switching_mechanism": None,
                   "price_formation": None, "novelty_claim": ""}
        out = rank_methods(db, aspects, k=3)
        assert len(out) <= 3
        # minority_game should be in there given the keywords
        names = {r["name"] for r in out}
        assert "minority_game" in names or "speculation_game" in names


def test_rank_proposals_empty_when_no_proposals():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        out = rank_proposals(db, {"key_keywords": ["foo"]}, k=5)
        assert out == []


def test_rank_proposals_skips_rejected_rows():
    """Rejected proposals should not surface in idea_judge context."""
    from fingerprint_atlas.db import insert_proposal, update_proposal_status
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        kept_id = insert_proposal(
            db, proposal_type="param_sweep",
            target_model="minority_game", params={"N": 101},
            predicted_fingerprint={n: 0.0 for n in FEATURE_NAMES},
            predicted_novelty_distance=1.0,
            rationale="minority game N sweep — investigate kurtosis",
            references=[], llm_model="m",
        )
        dropped_id = insert_proposal(
            db, proposal_type="param_sweep",
            target_model="minority_game", params={"N": 51},
            predicted_fingerprint={n: 0.0 for n in FEATURE_NAMES},
            predicted_novelty_distance=1.0,
            rationale="minority game N sweep — investigate kurtosis",
            references=[], llm_model="m",
        )
        update_proposal_status(db, dropped_id, status="rejected")
        out = rank_proposals(db, {"key_keywords": ["minority", "kurtosis"]}, k=5)
        ids = {r["id"] for r in out}
        assert kept_id in ids
        assert dropped_id not in ids


def test_rank_proposals_handles_empty_rationale():
    """Regression: an empty-string rationale used to IndexError on
    `"".splitlines()[0]` because splitlines("") is [] (not [""])."""
    from fingerprint_atlas.db import insert_proposal
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        insert_proposal(
            db, proposal_type="param_sweep",
            target_model="minority_game", params={"N": 101},
            predicted_fingerprint={n: 0.0 for n in FEATURE_NAMES},
            predicted_novelty_distance=1.0,
            rationale="",  # the trigger
            references=[], llm_model="m",
        )
        # Just reaching this line (not raising IndexError) is the test;
        # the keyword overlap filter may still drop the row.
        rank_proposals(db, {"key_keywords": ["minority_game"]}, k=5)


def test_rank_literature_returns_empty_when_no_literature():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        out = rank_literature(db, {"key_keywords": ["foo"]}, k=5)
        assert out == []


# ---- judge_idea (dry-run) ------------------------------------------------

def test_judge_idea_dry_run_persists_nothing_until_caller_inserts():
    """judge_idea returns aspects+matches+verdict but does NOT insert into DB
    by itself (the CLI is responsible for persistence)."""
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        fake_aspects = {
            "agent_types": ["LLM-trader"],
            "switching_mechanism": "sentiment-driven role switching",
            "price_formation": "aggregate excess demand",
            "target_stylized_facts": ["vol-clustering", "fat-tails"],
            "novelty_claim": "use of news LLM sentiment for role switching",
            "key_keywords": ["LLM", "sentiment", "switching", "minority", "game"],
        }
        fake_verdict = {
            "category": "incremental_novelty",
            "closest_method": "minority_game",
            "closest_literature_arxiv_ids": [],
            "closest_proposal_id": None,
            "covered_aspects": ["switching"],
            "novel_aspects": ["LLM sentiment input"],
            "differentiation_suggestions": ["arXiv の LLM-agent 文献と比較"],
            "confidence": 0.7,
            "summary_ja": "LLM経由のセンチメント切替は incremental novel。",
        }
        result = judge_idea(db, "test idea using LLM sentiment",
                            dry_run_aspects=fake_aspects,
                            dry_run_verdict=fake_verdict)
        assert result["aspects"]["agent_types"] == ["LLM-trader"]
        assert result["verdict"]["category"] == "incremental_novelty"
        assert "methods" in result["matches"]
        # DB itself stays empty (no idea row written)
        assert load_ideas(db) == []


# ---- make_plan dry-run ---------------------------------------------------

def test_make_plan_dry_run_returns_plan_dict():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        fake_plan = {
            "implementation_type": "param_sweep",
            "based_on_method": "minority_game",
            "param_sweep": {
                "target_model": "minority_game",
                "params": {"N": 101, "M": 4, "S": 2, "T": 2500},
                "predicted_fingerprint": {n: 0.0 for n in FEATURE_NAMES},
                "predicted_novelty_distance": 2.0,
                "rationale": "M=4 を中心に MG の relevant 域を探索する (acf_absret_long 0.1 想定)",
            },
            "knowhow_techniques_to_apply": [],
            "calibration_strategy": "MG では σ²/N を見る",
            "validation_strategy": "block bootstrap",
            "references": [],
        }
        out = make_plan(db, "an MG-flavoured idea",
                        {"aspects": {}, "verdict": {}, "matches": {"methods": [], "literature": [], "proposals": []}},
                        dry_run_response=fake_plan)
        assert out["implementation_type"] == "param_sweep"


# ---- scaffold (param_sweep / combo / new) --------------------------------

def test_scaffold_param_sweep_writes_proposal_row():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        rid = insert_idea(db, idea_text="x")
        plan = {
            "implementation_type": "param_sweep",
            "param_sweep": {
                "target_model": "minority_game",
                "params": {"N": 101, "M": 4, "S": 2, "T": 2500},
                "predicted_fingerprint": {n: 0.0 for n in FEATURE_NAMES},
                "predicted_novelty_distance": 1.5,
                "rationale": "Minority Game の M=4 を試す。acf_absret_mean を見る。",
            },
            "references": [],
        }
        out = scaffold(plan, db_path=db, idea_id=rid,
                       packages_root="/tmp/_idea_test_root", llm_model="m")
        assert out["type"] == "param_sweep"
        assert "proposal_id" in out
        rows = load_proposals(db)
        assert len(rows) == 1


def test_scaffold_param_sweep_rejects_missing_keys():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal(td)
        rid = insert_idea(db, idea_text="x")
        plan = {
            "implementation_type": "param_sweep",
            "param_sweep": {
                "target_model": "minority_game",
                "params": {"N": 101},  # missing M, S, T
                "rationale": "x" * 30,
            },
            "references": [],
        }
        with pytest.raises(ValueError):
            scaffold(plan, db_path=db, idea_id=rid,
                     packages_root="/tmp/_idea_test_root", llm_model="m")


def test_scaffold_mechanism_combo_writes_python_files():
    with tempfile.TemporaryDirectory() as td:
        plan = {
            "mechanism_combo": {
                "base_method_a": "speculation_game",
                "base_method_b": "franke_westerhoff",
                "combination_strategy": "SG の戦略切替に FW の sentiment を input",
                "new_class_name": "SgFwSentimentHybrid",
                "expected_behavior": "vol clustering + sentiment dependence",
            },
        }
        out = scaffold_mechanism_combo(plan, idea_id=42, packages_root=td)
        assert out["class_name"] == "SgFwSentimentHybrid"
        assert len(out["paths"]) == 2
        for p in out["paths"]:
            assert os.path.exists(p)
        # the model file mentions the class name and import REGISTRY
        with open(out["paths"][1]) as fh:
            body = fh.read()
        assert "class SgFwSentimentHybrid" in body
        assert "REGISTRY" in body
        assert "TODO(human)" in body


def test_scaffold_new_method_writes_skeleton():
    with tempfile.TemporaryDirectory() as td:
        plan = {
            "new_method": {
                "mechanism_description": "完全に新しい機構の説明",
                "agent_types": ["a", "b"],
                "key_state_variables": ["x", "y"],
                "new_class_name": "MyNewABM",
            },
        }
        out = scaffold_new_method(plan, idea_id=99, packages_root=td)
        assert out["class_name"] == "MyNewABM"
        with open(out["paths"][1]) as fh:
            body = fh.read()
        assert "class MyNewABM" in body
        assert "TODO(human)" in body
        assert "MyNewABM" in body


def test_camel_to_snake():
    # The converter inserts `_` only between a lowercase/digit and an
    # uppercase letter; runs of uppercase (HTTPServer) stay glued together.
    # That is fine for our use case (auto-generated class names from LLM).
    assert _camel_to_snake("MyClass") == "my_class"
    assert _camel_to_snake("HTTPServer") == "httpserver"
    assert _camel_to_snake("FooBarBaz") == "foo_bar_baz"
    assert _camel_to_snake("already_snake") == "already_snake"
    assert _camel_to_snake("") == "anon"


def test_scaffold_unknown_type_raises():
    with pytest.raises(ValueError):
        scaffold({"implementation_type": "ghost"}, db_path=":memory:",
                 idea_id=1, packages_root="/tmp", llm_model="m")
