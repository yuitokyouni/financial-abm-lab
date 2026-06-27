"""Tests for the proposal pipeline.

Covers:
  1. proposals schema migration is idempotent.
  2. insert/load round-trip for a single proposal.
  3. status update transitions and the executed_run_id link.
  4. summarize_corpus produces a valid context dict (after populating the DB).
  5. propose_from_corpus(dry_run_payload=...) validates + stores proposals
     without calling the network.
  6. Validation rejects malformed proposals.
  7. execute path closes the loop on a real param_sweep:
       summarize → fake LLM response → store proposal → execute → measure.
"""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from fingerprint_atlas.adapters import build_model, series_for_fingerprint
from fingerprint_atlas.db import (
    ensure_proposals_schema, ensure_runs_schema, insert_proposal, insert_run,
    load_proposals, load_runs, update_proposal_status,
)
from fingerprint_atlas.fingerprint import FEATURE_NAMES, fingerprint
from fingerprint_atlas.methods import seed_methods
from fingerprint_atlas.propose import (
    _validate_proposal, propose_from_corpus, summarize_corpus,
)


def _populate_minimal_db() -> str:
    """Build a tmp DB with a tiny abm run population + methods seeded."""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    ensure_runs_schema(db)
    seed_methods(db)
    # Run two ABMs at small sizes to populate enough fingerprints for centroids.
    for name in ("speculation_game", "cont_bouchaud"):
        for i, seed in enumerate([1, 2]):
            if name == "speculation_game":
                m = build_model(name, dict(N=80, M=2, S=2, T=400))
            else:
                m = build_model(name, dict(N=500, c=0.9, T=400, report_every=10**9))
            res = m.run(seed=seed)
            series, kind = series_for_fingerprint(name, res)
            fp = fingerprint(series, compute_hill=(kind == "returns"))
            insert_run(
                db, model_name=name, params={"i": i}, seed=seed,
                fingerprint_vec=fp, series_kind=kind,
                series_length=int(len(series)),
                provenance={"git_commit": "test"},
                created_at="2026-06-27T00:00:00Z",
                origin="abm",
            )
    return db


# ----- 1. schema + 2. round-trip -------------------------------------------

def test_proposals_schema_idempotent():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    ensure_proposals_schema(db)
    ensure_proposals_schema(db)
    rows = load_proposals(db)
    assert rows == []


def test_insert_load_proposal_roundtrip():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    ensure_proposals_schema(db)
    fp_pred = {name: 0.1 for name in FEATURE_NAMES}
    rid = insert_proposal(
        db, proposal_type="param_sweep", target_model="speculation_game",
        params={"N": 300, "M": 3, "S": 2, "T": 2000, "B": 9, "C": 3.0},
        rationale="test rationale",
        predicted_fingerprint=fp_pred, predicted_novelty_distance=1.7,
        references=["arXiv:test"], llm_model="llama-3.3-70b-versatile",
    )
    rows = load_proposals(db)
    assert len(rows) == 1
    p = rows[0]
    assert p["id"] == rid
    assert p["target_model"] == "speculation_game"
    assert p["status"] == "proposed"
    assert p["predicted_fingerprint"]["volatility"] == 0.1
    assert p["predicted_novelty_distance"] == pytest.approx(1.7)


# ----- 3. status transitions ------------------------------------------------

def test_status_transitions_and_post_execute_fields():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    ensure_proposals_schema(db)
    pid = insert_proposal(
        db, proposal_type="param_sweep", target_model="cont_bouchaud",
        params={"N": 1000, "c": 0.9, "a": 0.01, "lam": 1.0, "T": 500},
        rationale="x", predicted_fingerprint=None,
        predicted_novelty_distance=None, references=[],
        llm_model="m",
    )
    update_proposal_status(db, pid, "approved")
    p = load_proposals(db)[0]
    assert p["status"] == "approved"
    update_proposal_status(
        db, pid, "executed", executed_run_id=42,
        actual_fingerprint={n: 0.5 for n in FEATURE_NAMES},
        actual_novelty_distance=1.23, prediction_error=0.45,
    )
    p = load_proposals(db, status="executed")[0]
    assert p["executed_run_id"] == 42
    assert p["prediction_error"] == pytest.approx(0.45)
    assert p["actual_fingerprint"]["leverage"] == 0.5


# ----- 4. summarize_corpus --------------------------------------------------

def test_summarize_corpus_has_expected_keys():
    db = _populate_minimal_db()
    ctx = summarize_corpus(db)
    assert set(ctx.keys()) >= {
        "implemented_methods", "parameter_bounds", "atlas_state",
        "feature_names", "sparse_regions",
    }
    assert ctx["feature_names"] == FEATURE_NAMES
    # both populated families present
    centroids = ctx["atlas_state"]["per_family_centroids_in_standardised_space"]
    assert "speculation_game" in centroids
    assert "cont_bouchaud" in centroids
    # parameter_bounds carries every REGISTRY model
    from abm_models import REGISTRY
    assert set(ctx["parameter_bounds"]).issuperset(set(REGISTRY))


# ----- 5. dry-run propose_from_corpus --------------------------------------

def _fake_groq_response(target_model: str, params: dict) -> dict:
    return {
        "proposals": [{
            "type": "param_sweep",
            "target_model": target_model,
            "params": params,
            "rationale": "テスト用提案: acf_absret_long を 0.2 程度に伸ばし leverage 効果 -0.1 を狙う。",
            "predicted_fingerprint": {n: 0.0 for n in FEATURE_NAMES},
            "predicted_novelty_distance": 2.0,
            "references": ["arXiv:test"],
        }]
    }


def test_propose_from_corpus_dry_run_stores_valid_proposal():
    db = _populate_minimal_db()
    payload = _fake_groq_response(
        "lux_marchesi",
        {"n_integer_steps": 2500, "steps_per_unit": 100, "n_c_init": 80},
    )
    res = propose_from_corpus(db, n=1, dry_run_payload=payload)
    summary = res[0]
    assert len(summary["accepted"]) == 1
    assert summary["accepted"][0]["target_model"] == "lux_marchesi"
    rows = load_proposals(db)
    assert len(rows) == 1
    assert rows[0]["rationale"].startswith("テスト用提案")


def test_propose_from_corpus_drops_invalid_target():
    db = _populate_minimal_db()
    payload = _fake_groq_response("totally_unknown_model", {"x": 1})
    res = propose_from_corpus(db, n=1, dry_run_payload=payload)
    assert len(res[0]["accepted"]) == 0
    assert "unknown target_model" in res[0]["rejected"][0]["error"]


def test_propose_from_corpus_drops_wrong_type():
    db = _populate_minimal_db()
    payload = {"proposals": [{
        "type": "mechanism_combo",
        "target_model": "speculation_game",
        "params": {"x": 1},
        "rationale": "x",
    }]}
    res = propose_from_corpus(db, n=1, dry_run_payload=payload)
    assert len(res[0]["accepted"]) == 0
    assert "unsupported type" in res[0]["rejected"][0]["error"]


# ----- 6. validator unit ---------------------------------------------------

def test_validator_catches_missing_required_keys():
    ok, err = _validate_proposal({"type": "param_sweep"}, len(FEATURE_NAMES))
    assert not ok and "missing key" in err


def test_validator_catches_bad_predicted_fingerprint():
    ok, err = _validate_proposal({
        "type": "param_sweep", "target_model": "speculation_game",
        "params": {"N": 300, "M": 3, "S": 2, "T": 2000, "B": 9, "C": 3.0},
        "rationale": "volatility 0.01 程度を想定したテスト用 rationale (hill α=3 狙い)",
        "predicted_fingerprint": {"volatility": 0.1},  # missing the rest
    }, len(FEATURE_NAMES))
    assert not ok and "missing keys" in err


def test_validator_accepts_well_formed():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    ok, err = _validate_proposal({
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "尖度を抑えつつ leverage 効果 -0.1 を狙うパラメータ調整。",
        "predicted_fingerprint": fp,
    }, len(FEATURE_NAMES))
    assert ok, err


def test_validator_rejects_empty_rationale():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    ok, err = _validate_proposal({
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "", "predicted_fingerprint": fp,
    }, len(FEATURE_NAMES))
    assert not ok and "empty" in err


def test_validator_rejects_too_short_rationale():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    ok, err = _validate_proposal({
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "x", "predicted_fingerprint": fp,
    }, len(FEATURE_NAMES))
    assert not ok and "too short" in err


def test_validator_rejects_template_rationale():
    """A rationale containing one of the LLM's default template phrases is rejected."""
    fp = {n: 0.0 for n in FEATURE_NAMES}
    p = {
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "このパラメータスイープは、エージェントとダイナミクスの関係を調べることを目的としています。",
        "predicted_fingerprint": fp,
    }
    ok, err = _validate_proposal(p, len(FEATURE_NAMES))
    assert not ok
    assert "template phrase" in err


def test_validator_rejects_concrete_less_rationale():
    """A rationale with no feature name, no arxiv id, and no number is rejected
    even if it doesn't hit a template blacklist."""
    fp = {n: 0.0 for n in FEATURE_NAMES}
    p = {
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "市場が複雑である理由を考察する。何か新しいことが起こるはず。",  # vague
        "predicted_fingerprint": fp,
    }
    ok, err = _validate_proposal(p, len(FEATURE_NAMES))
    assert not ok
    assert "concrete signal" in err


def test_validator_accepts_rationale_with_feature_keyword():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    p = {
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "Tc を大きくして長期記憶 acf_absret_long を 0.25 まで伸ばす狙い。",
        "predicted_fingerprint": fp,
    }
    ok, err = _validate_proposal(p, len(FEATURE_NAMES))
    assert ok, err


def test_validator_accepts_rationale_with_arxiv_citation():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    p = {
        "type": "param_sweep", "target_model": "lux_marchesi",
        "params": {"n_integer_steps": 2000, "steps_per_unit": 100, "n_c_init": 80},
        "rationale": "arXiv:2606.21784 の高速 ABM 実装に着想を得て、規模を上げる。",
        "predicted_fingerprint": fp,
    }
    ok, err = _validate_proposal(p, len(FEATURE_NAMES))
    assert ok, err


def test_validator_rejects_missing_required_param_keys():
    fp = {n: 0.0 for n in FEATURE_NAMES}
    ok, err = _validate_proposal({
        "type": "param_sweep", "target_model": "cont_bouchaud",
        "params": {"N": 3000},  # missing c, a, lam, T
        "rationale": "valid-looking rationale",
        "predicted_fingerprint": fp,
    }, len(FEATURE_NAMES))
    assert not ok and "missing required keys" in err


# ----- 7. end-to-end execute path -----------------------------------------

def test_end_to_end_execute_links_run_and_records_error():
    """Generate a proposal via dry-run, then drive the execute logic
    directly without going through the CLI argparser."""
    db = _populate_minimal_db()
    payload = _fake_groq_response(
        "cont_bouchaud",
        {"N": 800, "c": 0.85, "a": 0.012, "lam": 1.0, "T": 500},
    )
    propose_from_corpus(db, n=1, dry_run_payload=payload)
    pid = load_proposals(db)[0]["id"]

    # Simulate the CLI execute path inline.
    from fingerprint_atlas.adapters import build_model
    p = load_proposals(db)[0]
    model = build_model(p["target_model"], p["params"])
    res = model.run(seed=12345)
    series, kind = series_for_fingerprint(p["target_model"], res)
    fp = fingerprint(series, compute_hill=(kind == "returns"))
    rid = insert_run(
        db, model_name=p["target_model"], params=p["params"], seed=12345,
        fingerprint_vec=fp, series_kind=kind, series_length=len(series),
        provenance={"source": "test_execute", "proposal_id": p["id"]},
        created_at="2026-06-27T00:00:00Z", origin="abm",
    )
    update_proposal_status(
        db, pid, "executed", executed_run_id=rid,
        actual_fingerprint={n: float(v) for n, v in zip(FEATURE_NAMES, fp)},
        prediction_error=1.0,
    )
    final = load_proposals(db)[0]
    assert final["status"] == "executed"
    assert final["executed_run_id"] == rid
    assert final["prediction_error"] == 1.0
