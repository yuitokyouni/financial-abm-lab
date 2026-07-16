"""Tests for the gap → proposal pipeline (LLM call mocked)."""
from __future__ import annotations

import json


_FAKE_GAP = {
    "view": "A", "row": "Prospect theory in trading",
    "col": "regime-switching", "value": 0.0, "salience": 3.89,
    "row_total": 21, "col_total": 12,
    "why": "subfield has 21 papers but 0 target regime-switching.",
}

_FAKE_FAMILIES = [
    {"key": "speculation_game", "name": "Speculation Game",
     "mechanism": "3-layer cognitive ABM ..."},
    {"key": "lux_marchesi", "name": "Lux-Marchesi",
     "mechanism": "Three-population chartist/fundamentalist ..."},
]

_FAKE_PAPERS = [
    {"arxiv_id": "1303.4321", "title": "Prospect theory and the disposition effect",
     "year": 2013, "oa_cited_by_count": 200,
     "mechanism_tags": "prospect-theory, disposition",
     "oa_concepts": "Prospect theory"},
    {"arxiv_id": "1408.5555", "title": "Loss aversion in dynamic markets",
     "year": 2014, "oa_cited_by_count": 50,
     "mechanism_tags": "loss-aversion, prospect-theory",
     "oa_concepts": ""},
]


def test_build_payload_includes_gap_axes_families_and_top_papers():
    from fingerprint_atlas.gap_propose import build_proposal_payload
    payload = build_proposal_payload(
        _FAKE_GAP, corpus_papers=_FAKE_PAPERS, families=_FAKE_FAMILIES,
    )
    assert payload["subfield_or_family"] == "Prospect theory in trading"
    assert payload["stylized_fact"] == "regime-switching"
    assert payload["row_total_papers"] == 21
    assert {f["key"] for f in payload["available_families"]} == {
        "speculation_game", "lux_marchesi"}
    titles = [p["title"] for p in payload["related_papers"]]
    assert any("Prospect theory" in t for t in titles)


def test_propose_from_gap_accepts_dry_run_response():
    from fingerprint_atlas.gap_propose import propose_from_gap
    fake = {
        "target_model": "speculation_game",
        "params": {"prospect_lambda": 2.25, "regime_threshold": 0.5},
        "rationale": "Prospect bias × regime 切替を SG layer 1 に組み込み、レジーム ごとに λ を変化させる。",
        "predicted_fingerprint": {"leverage": -0.15, "kurtosis": 8.0},
        "references": ["1303.4321"],
    }
    out = propose_from_gap(_FAKE_GAP, corpus_papers=_FAKE_PAPERS,
                            families=_FAKE_FAMILIES,
                            dry_run_response=fake)
    assert out["target_model"] == "speculation_game"
    assert out["rationale"].startswith("Prospect")
    assert out["references"] == ["1303.4321"]
    assert out["_gap"]["view"] == "A"
    assert out["_gap"]["row"] == "Prospect theory in trading"


def test_propose_from_gap_rejects_empty_rationale():
    from fingerprint_atlas.gap_propose import propose_from_gap
    bad = {"target_model": "speculation_game", "rationale": "  "}
    import pytest
    with pytest.raises(ValueError, match="empty rationale"):
        propose_from_gap(_FAKE_GAP, corpus_papers=_FAKE_PAPERS,
                          families=_FAKE_FAMILIES,
                          dry_run_response=bad)


def test_propose_from_gap_rejects_unknown_target_model():
    from fingerprint_atlas.gap_propose import propose_from_gap
    bad = {"target_model": "made_up_family",
           "rationale": "Has rationale text."}
    import pytest
    with pytest.raises(ValueError, match="not in available"):
        propose_from_gap(_FAKE_GAP, corpus_papers=_FAKE_PAPERS,
                          families=_FAKE_FAMILIES,
                          dry_run_response=bad)


def test_propose_from_gap_rejects_new_target_when_registry_required():
    """'new' was historically allowed but now rejected — executor can't
    run it, so accepting it would burn proposals."""
    from fingerprint_atlas.gap_propose import propose_from_gap
    bad = {"target_model": "new", "rationale": "x"}
    import pytest
    with pytest.raises(ValueError, match="not in available"):
        propose_from_gap(_FAKE_GAP, corpus_papers=_FAKE_PAPERS,
                          families=_FAKE_FAMILIES,
                          dry_run_response=bad)


def test_propose_from_gap_rejects_params_not_in_registry():
    """When model_bounds is provided, fabricated param keys (the user's
    actual #28 bug — memory_exponent was invented) must be rejected."""
    from fingerprint_atlas.gap_propose import propose_from_gap
    bad = {
        "target_model": "speculation_game",
        "params": {"N": 300, "memory_exponent": 0.4},  # last key is fake
        "rationale": "Has a rationale.",
        "predicted_fingerprint": {fn: 0.0 for fn in _FAKE_FEATURE_NAMES},
    }
    import pytest
    with pytest.raises(ValueError, match="not in registry"):
        propose_from_gap(
            _FAKE_GAP, corpus_papers=_FAKE_PAPERS,
            families=_FAKE_FAMILIES,
            model_bounds={"speculation_game": {"N": (200, 400),
                                                  "M": (3, 5)}},
            feature_names=_FAKE_FEATURE_NAMES,
            dry_run_response=bad,
        )


def test_propose_from_gap_rejects_null_or_missing_fingerprint():
    """The #28 bug also dropped predicted_fingerprint to all-None.
    feature_names enforcement must catch that."""
    from fingerprint_atlas.gap_propose import propose_from_gap
    import pytest
    base = {
        "target_model": "speculation_game",
        "params": {"N": 300},
        "rationale": "Has rationale.",
    }
    # null predicted_fp
    with pytest.raises(ValueError, match="predicted_fingerprint is mandatory"):
        propose_from_gap(
            _FAKE_GAP, corpus_papers=_FAKE_PAPERS,
            families=_FAKE_FAMILIES,
            model_bounds={"speculation_game": {"N": (200, 400)}},
            feature_names=_FAKE_FEATURE_NAMES,
            dry_run_response={**base, "predicted_fingerprint": None},
        )
    # partial predicted_fp (one missing)
    partial = {fn: 0.0 for fn in _FAKE_FEATURE_NAMES[:-1]}
    with pytest.raises(ValueError, match="missing values"):
        propose_from_gap(
            _FAKE_GAP, corpus_papers=_FAKE_PAPERS,
            families=_FAKE_FAMILIES,
            model_bounds={"speculation_game": {"N": (200, 400)}},
            feature_names=_FAKE_FEATURE_NAMES,
            dry_run_response={**base, "predicted_fingerprint": partial},
        )


def test_propose_from_gap_diversity_hint_surfaces_in_payload():
    """already_used_families goes through into the payload so the LLM
    can avoid the same target."""
    from fingerprint_atlas.gap_propose import build_proposal_payload
    payload = build_proposal_payload(
        _FAKE_GAP, corpus_papers=_FAKE_PAPERS, families=_FAKE_FAMILIES,
        already_used_families=["lux_marchesi", "speculation_game"],
    )
    assert payload["already_used_families"] == [
        "lux_marchesi", "speculation_game"]


def test_summarise_families_attaches_params_allowed():
    """B: model_bounds → params_allowed entry per family in the prompt."""
    from fingerprint_atlas.gap_propose import _summarise_families
    out = _summarise_families(
        _FAKE_FAMILIES,
        model_bounds={"speculation_game": {"N": (200, 400),
                                              "M": (3, 5)}},
    )
    sg = next(f for f in out if f["key"] == "speculation_game")
    assert sg["params_allowed"] == {"N": [200, 400], "M": [3, 5]}
    # family without registry entry → empty + flagged
    lm = next(f for f in out if f["key"] == "lux_marchesi")
    assert lm["params_allowed"] == {}
    assert lm.get("impl_status") == "not-in-registry"


_FAKE_FEATURE_NAMES = [
    "volatility", "kurtosis", "hill_tail_index", "acf_ret_l1",
    "acf_absret_mean", "leverage", "acf_absret_long",
    "acf_absret_decay", "agg_kurt_decay",
]


def test_insert_gap_proposal_persists_with_proposal_type_gap_mine(tmp_path):
    from fingerprint_atlas.gap_propose import insert_gap_proposal
    import sqlite3
    db = str(tmp_path / "t.db")
    proposal = {
        "target_model": "speculation_game",
        "params": {"prospect_lambda": 2.25},
        "rationale": "テスト用 rationale。",
        "predicted_fingerprint": None,
        "predicted_novelty_distance": None,
        "references": ["1303.4321"],
        "llm_model": "openai/gpt-oss-120b",
        "_gap": {"view": "A", "row": "Prospect theory in trading",
                  "col": "regime-switching", "salience": 3.89},
    }
    pid = insert_gap_proposal(db, proposal)
    assert pid > 0
    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT proposal_type, target_model, rationale, params_json "
            "FROM proposals WHERE id = ?", (pid,)
        ).fetchone()
    assert row[0] == "gap_mine"
    assert row[1] == "speculation_game"
    assert "テスト用" in row[2]
    # _gap context survives into params_json
    params = json.loads(row[3])
    assert params["_gap"]["row"] == "Prospect theory in trading"


def test_summarise_papers_tolerates_tied_cite_counts():
    """Regression: tuple-sort tie-break used to compare dicts and
    crash with 'unorderable types'."""
    from fingerprint_atlas.gap_propose import _summarise_papers
    papers = [
        {"arxiv_id": "a.1", "title": "A", "year": 2020,
         "oa_cited_by_count": 100},
        {"arxiv_id": "a.2", "title": "B", "year": 2021,
         "oa_cited_by_count": 100},  # same cite count — would crash on tie
        {"arxiv_id": "a.3", "title": "C", "year": 2022,
         "oa_cited_by_count": 100},
    ]
    out = _summarise_papers(papers, n=3)  # must not raise
    assert len(out) == 3
    assert {p["arxiv_id"] for p in out} == {"a.1", "a.2", "a.3"}


def test_scope_corpus_handles_list_valued_mechanism_tags():
    """Regression: load_literature returns mechanism_tags as list[str],
    not str. _scope_corpus_to_gap must accept either form."""
    from fingerprint_atlas.gap_propose import _scope_corpus_to_gap
    rows = [
        {"arxiv_id": "a.1", "mechanism_tags": ["prospect-theory"],
         "oa_concepts": "Prospect theory"},
        {"arxiv_id": "a.2", "mechanism_tags": "prospect-theory, disposition",
         "oa_concepts": ""},
        {"arxiv_id": "b.1", "mechanism_tags": ["herding"],
         "oa_concepts": "Herding"},
    ]
    out = _scope_corpus_to_gap(rows, "Prospect theory in trading")
    ids = {p["arxiv_id"] for p in out}
    assert ids == {"a.1", "a.2"}
    # Confirm list-valued and string-valued tags both worked


def test_propose_from_top_gaps_end_to_end(tmp_path, monkeypatch):
    """End-to-end with the LLM call stubbed: gap-mine → proposal for
    each of N gaps → inserted into the DB."""
    from fingerprint_atlas import gap_propose
    from fingerprint_atlas.fingerprint import FEATURE_NAMES
    import json as _json
    n = len(FEATURE_NAMES)
    # Real-market + a 'broken' family so view B surfaces gaps
    real = [{"model_name": "real_spx",
              "fingerprint_json": _json.dumps([0.0]*n)} for _ in range(3)]
    real += [{"model_name": "real_btc",
              "fingerprint_json": _json.dumps([0.01]*n)} for _ in range(3)]
    bad_fp = [0.0]*n
    bad_fp[FEATURE_NAMES.index("acf_ret_l1")] = 8.0
    fam = [{"model_name": "franke_westerhoff",
             "fingerprint_json": _json.dumps(bad_fp)} for _ in range(3)]

    calls = {"n": 0}

    def fake_propose_from_gap(gap, *, corpus_papers, families, llm_model,
                                model_bounds=None, feature_names=None,
                                already_used_families=None,
                                temperature=0.6, dry_run_response=None):
        calls["n"] += 1
        return {
            "target_model": "speculation_game",
            "params": {"k": 1},
            "rationale": f"For {gap['row']} × {gap['col']}, propose stub.",
            "predicted_fingerprint": None,
            "predicted_novelty_distance": None,
            "references": [],
            "llm_model": llm_model,
            "_gap": {"view": gap["view"], "row": gap["row"],
                      "col": gap["col"], "salience": gap["salience"]},
        }
    monkeypatch.setattr(gap_propose, "propose_from_gap", fake_propose_from_gap)

    db = str(tmp_path / "t.db")
    out = gap_propose.propose_from_top_gaps(
        db, rows=[], runs=real + fam, top_n=3, dry_run=False,
    )
    assert calls["n"] >= 1
    assert len(out) >= 1
    # At least one proposal got persisted
    persisted = [p for p in out if p.get("id") is not None]
    assert persisted, f"no proposals persisted: {out}"

    import sqlite3
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "SELECT proposal_type, target_model FROM proposals"
        ).fetchall()
    assert all(r[0] == "gap_mine" for r in rows)
    assert all(r[1] == "speculation_game" for r in rows)
