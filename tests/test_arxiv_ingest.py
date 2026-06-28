"""Tests for the arxiv ingestion pipeline.

Network is NOT called: arxiv API queries and Groq extractions are exercised
via dry-run payloads and direct DB inserts.
"""
from __future__ import annotations

import tempfile

import pytest

from fingerprint_atlas.arxiv_ingest import (
    EXTRACTION_SYSTEM_PROMPT, _coerce_relevance, extract_paper_structured,
)
from fingerprint_atlas.db import (
    ensure_literature_schema, load_literature,
    update_literature_extraction, upsert_literature_metadata,
)


def _tmpdb():
    return tempfile.NamedTemporaryFile(suffix=".db", delete=False).name


# ---- schema + upsert -------------------------------------------------------

def test_literature_schema_idempotent():
    db = _tmpdb()
    ensure_literature_schema(db)
    ensure_literature_schema(db)  # second call is a no-op
    rows = load_literature(db)
    assert rows == []


def test_upsert_is_idempotent_on_arxiv_id():
    db = _tmpdb()
    ensure_literature_schema(db)
    id1 = upsert_literature_metadata(
        db, arxiv_id="2412.99999", title="A test paper", authors="Smith, Jones",
        year=2024, published_date="2024-12-15T00:00:00Z",
        primary_category="q-fin.TR", abstract="abs body",
    )
    id2 = upsert_literature_metadata(
        db, arxiv_id="2412.99999", title="Updated title",  # ignored on dup
        authors="Smith, Jones", year=2024,
        published_date="2024-12-15T00:00:00Z",
        primary_category="q-fin.TR", abstract="abs body",
    )
    assert id1 == id2
    rows = load_literature(db)
    assert len(rows) == 1
    assert rows[0]["title"] == "A test paper"   # original kept


# ---- LLM extraction (dry-run) ---------------------------------------------

def test_extract_paper_structured_dry_run():
    paper = {
        "title": "Heterogeneous LLM Agents in Continuous Double Auctions",
        "abstract": "We propose a hybrid market simulation in which LLM-driven "
                    "agents trade against a noise baseline. We show that "
                    "endogenous sentiment shocks produce fat tails and "
                    "volatility clustering consistent with empirical returns.",
    }
    fake = {
        "mechanism_summary": "LLM-driven agents in a CDA with sentiment shocks.",
        "mechanism_tags": ["LLM-agent", "order-book", "sentiment"],
        "stylized_facts_targeted": ["fat-tails", "vol-clustering"],
        "novelty_signal": "First use of in-context LLM reasoning to generate "
                          "order book proposals.",
        "relevance_score": 0.85,
    }
    ext = extract_paper_structured(paper, model="llama-3.3-70b-versatile",
                                    dry_run_response=fake)
    assert ext["mechanism_summary"].startswith("LLM-driven")
    assert "LLM-agent" in ext["mechanism_tags"]
    assert ext["relevance_score"] == 0.85
    assert ext["extracted_by_model"] == "llama-3.3-70b-versatile"


def test_extract_coerces_string_tags():
    """Llama sometimes returns comma-separated strings instead of lists."""
    paper = {"title": "T", "abstract": "A"}
    fake = {
        "mechanism_summary": "x", "mechanism_tags": "herding, momentum",
        "stylized_facts_targeted": "fat-tails, vol-clustering",
        "novelty_signal": None, "relevance_score": "0.7",
    }
    ext = extract_paper_structured(paper, dry_run_response=fake)
    assert ext["mechanism_tags"] == ["herding", "momentum"]
    assert ext["stylized_facts_targeted"] == ["fat-tails", "vol-clustering"]
    assert ext["relevance_score"] == 0.7


def test_coerce_relevance_clamps_and_handles_garbage():
    assert _coerce_relevance(0.5) == 0.5
    assert _coerce_relevance(2.0) == 1.0
    assert _coerce_relevance(-1.0) == 0.0
    assert _coerce_relevance("not-a-number") is None
    assert _coerce_relevance(None) is None


# ---- update_literature_extraction round-trip ------------------------------

def test_update_extraction_roundtrip():
    db = _tmpdb()
    ensure_literature_schema(db)
    upsert_literature_metadata(
        db, arxiv_id="2412.00001", title="t", authors="a",
        year=2024, published_date="2024-12-01T00:00:00Z",
        primary_category=None, abstract="x",
    )
    update_literature_extraction(
        db, "2412.00001", mechanism_summary="m",
        mechanism_tags=["a", "b"], stylized_facts_targeted=["fat-tails"],
        novelty_signal="n", relevance_score=0.42,
        extracted_by_model="llama-test",
    )
    r = load_literature(db)[0]
    assert r["mechanism_summary"] == "m"
    assert r["mechanism_tags"] == ["a", "b"]
    assert r["stylized_facts_targeted"] == ["fat-tails"]
    assert r["relevance_score"] == pytest.approx(0.42)
    assert r["extracted_by_model"] == "llama-test"
    assert r["extraction_attempts"] == 1


def test_update_extraction_increments_attempts():
    db = _tmpdb()
    ensure_literature_schema(db)
    upsert_literature_metadata(
        db, arxiv_id="2412.00002", title="t", authors="a", year=2024,
        published_date="2024-12-01T00:00:00Z",
        primary_category=None, abstract="x",
    )
    for _ in range(3):
        update_literature_extraction(
            db, "2412.00002", mechanism_summary="x",
            mechanism_tags=[], stylized_facts_targeted=[],
            novelty_signal=None, relevance_score=0.3,
            extracted_by_model="m",
        )
    r = load_literature(db)[0]
    assert r["extraction_attempts"] == 3


# ---- load_literature filters -----------------------------------------------

def test_load_literature_filters_by_relevance_and_tag():
    db = _tmpdb()
    ensure_literature_schema(db)
    for i, (rel, tags) in enumerate([(0.9, ["herding"]),
                                      (0.2, ["herding"]),
                                      (0.8, ["LLM-agent"])]):
        aid = f"2412.0{i:04d}"
        upsert_literature_metadata(
            db, arxiv_id=aid, title=f"p{i}", authors="a", year=2024,
            published_date="2024-12-01T00:00:00Z",
            primary_category="q-fin.TR", abstract="x",
        )
        update_literature_extraction(
            db, aid, mechanism_summary="x", mechanism_tags=tags,
            stylized_facts_targeted=[], novelty_signal=None,
            relevance_score=rel, extracted_by_model="m",
        )
    # min_relevance=0.5 keeps p0 and p2
    high = load_literature(db, min_relevance=0.5)
    assert {r["arxiv_id"] for r in high} == {"2412.00000", "2412.00002"}
    # tag filter
    herd = load_literature(db, tag="herding")
    assert {r["arxiv_id"] for r in herd} == {"2412.00000", "2412.00001"}


# ---- Integration: literature gets surfaced into propose context -----------

def test_summarize_corpus_includes_literature():
    """Tests that summarize_corpus pulls high-relevance literature into context."""
    from fingerprint_atlas.adapters import build_model, series_for_fingerprint
    from fingerprint_atlas.db import ensure_runs_schema, insert_run
    from fingerprint_atlas.fingerprint import fingerprint
    from fingerprint_atlas.methods import seed_methods
    from fingerprint_atlas.propose import summarize_corpus

    db = _tmpdb()
    ensure_runs_schema(db)
    ensure_literature_schema(db)
    seed_methods(db)
    # one tiny run so atlas_state isn't empty
    m = build_model("cont_bouchaud", dict(N=500, c=0.9, T=400, report_every=10**9))
    res = m.run(seed=1)
    series, kind = series_for_fingerprint("cont_bouchaud", res)
    fp = fingerprint(series, compute_hill=(kind == "returns"))
    insert_run(db, model_name="cont_bouchaud", params={}, seed=1,
               fingerprint_vec=fp, series_kind=kind, series_length=len(series),
               provenance={"git_commit": "test"},
               created_at="2026-06-27T00:00:00Z", origin="abm")

    # high-relevance paper
    upsert_literature_metadata(
        db, arxiv_id="2412.10000", title="LLM herding mechanism",
        authors="A", year=2024, published_date="2024-12-01T00:00:00Z",
        primary_category="q-fin.TR", abstract="abs",
    )
    update_literature_extraction(
        db, "2412.10000",
        mechanism_summary="LLM-driven herding via sentiment shocks.",
        mechanism_tags=["LLM-agent", "herding"],
        stylized_facts_targeted=["fat-tails"],
        novelty_signal="In-context LLM trading", relevance_score=0.85,
        extracted_by_model="m",
    )
    # low-relevance, will be dropped from context
    upsert_literature_metadata(
        db, arxiv_id="2412.10001", title="Off-topic paper", authors="B", year=2023,
        published_date="2023-06-01T00:00:00Z",
        primary_category="hep-th", abstract="off-topic",
    )
    update_literature_extraction(
        db, "2412.10001", mechanism_summary="off-topic", mechanism_tags=[],
        stylized_facts_targeted=[], novelty_signal=None,
        relevance_score=0.1, extracted_by_model="m",
    )

    ctx = summarize_corpus(db)
    assert "literature" in ctx
    assert "priceless_models" in ctx
    assert "minority_game" in ctx["priceless_models"]
    assert "feature_typical_ranges_pct_10_50_90" in ctx
    # the LLM paper should rank above the off-topic one
    lit_ids = [p["arxiv_id"] for p in ctx["literature"]]
    assert "2412.10000" in lit_ids
    # off-topic paper has rel=0.1 but no min_relevance filter in
    # _select_literature_for_context, so both appear. Order matters:
    assert lit_ids.index("2412.10000") < lit_ids.index("2412.10001")
    assert ctx["n_literature_total"] == 2


# ---- code_url extraction (regex only; PWC fetch is network-bound) -------

def test_extract_github_from_text_finds_canonical_url():
    from fingerprint_atlas.code_links import extract_github_from_text
    abstract = (
        "We propose TRIBE, an LLM-augmented bond-market ABM. "
        "Source code available at https://github.com/Alicia-V/TRIBE-bond ."
    )
    assert extract_github_from_text(abstract) == "https://github.com/Alicia-V/TRIBE-bond"


def test_extract_github_strips_trailing_punctuation_and_git_suffix():
    from fingerprint_atlas.code_links import extract_github_from_text
    assert (extract_github_from_text("Code: https://github.com/foo/bar.git).")
            == "https://github.com/foo/bar")
    assert (extract_github_from_text("see (https://github.com/foo/bar-baz),")
            == "https://github.com/foo/bar-baz")


def test_extract_github_returns_none_on_no_match():
    from fingerprint_atlas.code_links import extract_github_from_text
    assert extract_github_from_text(None) is None
    assert extract_github_from_text("") is None
    assert extract_github_from_text("no github link here, https://example.com/foo") is None


def test_set_literature_code_url_roundtrip():
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata,
        load_literature, set_literature_code_url,
    )
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/lit.db"
        ensure_literature_schema(db)
        upsert_literature_metadata(
            db, arxiv_id="2503.99999v1", title="x", authors="A",
            year=2025, published_date="2025-03-01T00:00:00Z",
            primary_category="q-fin.TR", abstract="see https://github.com/foo/bar",
        )
        set_literature_code_url(db, "2503.99999v1",
                                code_url="https://github.com/foo/bar",
                                source="abstract")
        rows = load_literature(db)
        assert rows[0]["code_url"] == "https://github.com/foo/bar"
        assert rows[0]["code_url_source"] == "abstract"


def test_code_snapshot_roundtrip_and_load_by_arxiv_ids():
    from fingerprint_atlas.db import (
        ensure_code_snapshot_schema, upsert_code_snapshot, load_code_snapshots,
    )
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/lit.db"
        ensure_code_snapshot_schema(db)
        upsert_code_snapshot(
            db, arxiv_id="2503.99999v1",
            code_url="https://github.com/foo/bar",
            readme_excerpt="# bar\n\nA cool project.",
            file_tree="src/\nREADME.md\nsetup.py",
            status="ok",
        )
        upsert_code_snapshot(  # second row, will be excluded by filter
            db, arxiv_id="2410.00001v1",
            code_url="https://github.com/baz/qux",
            readme_excerpt="qux", file_tree=None, status="ok",
        )
        snaps = load_code_snapshots(db, ["2503.99999v1"])
        assert set(snaps) == {"2503.99999v1"}
        assert "A cool project" in snaps["2503.99999v1"]["readme_excerpt"]
        # update overwrites
        upsert_code_snapshot(
            db, arxiv_id="2503.99999v1",
            code_url="https://github.com/foo/bar",
            readme_excerpt="new readme", file_tree=None, status="no_readme",
        )
        snaps = load_code_snapshots(db, ["2503.99999v1"])
        assert snaps["2503.99999v1"]["status"] == "no_readme"
        assert snaps["2503.99999v1"]["readme_excerpt"] == "new readme"


def test_make_plan_injects_code_snapshots_into_payload():
    """When a candidate paper has a cached snapshot, plan payload should
    expose candidate_literature_code so the LLM can reference real
    file/class structure."""
    from fingerprint_atlas.db import (
        ensure_code_snapshot_schema, upsert_code_snapshot,
    )
    from fingerprint_atlas.idea_plan import make_plan
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/p.db"
        ensure_code_snapshot_schema(db)
        upsert_code_snapshot(
            db, arxiv_id="2503.00320v2",
            code_url="https://github.com/example/tribe",
            readme_excerpt="# TRIBE\n\nA bond-market ABM.",
            file_tree="tribe/\nREADME.md",
            status="ok",
        )
        captured = {}

        def fake_make_plan_response(*_a, **_kw):
            return {"implementation_type": "param_sweep",
                    "param_sweep": {}, "references": []}

        # Monkey-patch _call_groq to capture payload, then return fake plan.
        from fingerprint_atlas import idea_plan
        orig = idea_plan._call_groq

        def spy(_prompt, payload, _model, **_kw):
            captured["payload"] = payload
            return fake_make_plan_response()

        idea_plan._call_groq = spy
        try:
            make_plan(
                db, "tribe-style idea",
                {
                    "aspects": {}, "verdict": {},
                    "matches": {
                        "methods": [],
                        "literature": [{
                            "arxiv_id": "2503.00320v2",
                            "title": "TRIBE",
                            "code_url": "https://github.com/example/tribe",
                        }],
                        "proposals": [],
                    },
                },
            )
        finally:
            idea_plan._call_groq = orig
        clc = captured["payload"]["candidate_literature_code"]
        assert len(clc) == 1
        assert clc[0]["arxiv_id"] == "2503.00320v2"
        assert "TRIBE" in (clc[0]["readme_excerpt"] or "")


def test_resolve_code_url_uses_comment_when_abstract_misses():
    from fingerprint_atlas.code_links import resolve_code_url
    url, src = resolve_code_url(
        "2503.99999v1",
        abstract="A study of X with no link.",
        comment="14 pages, code at https://github.com/foo/bar",
    )
    assert url == "https://github.com/foo/bar"
    assert src == "comment"


def test_set_arxiv_comment_roundtrip():
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata, load_literature,
        set_arxiv_comment,
    )
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/lit.db"
        ensure_literature_schema(db)
        upsert_literature_metadata(
            db, arxiv_id="2503.99999v1", title="x", authors="A",
            year=2025, published_date="2025-03-01T00:00:00Z",
            primary_category="q-fin.TR", abstract="no link",
        )
        set_arxiv_comment(db, "2503.99999v1",
                          "14 pages, code at https://github.com/foo/bar")
        rows = load_literature(db)
        assert "github.com/foo/bar" in rows[0]["arxiv_comment"]


def test_extract_github_matches_bare_no_protocol():
    """PDFs and arxiv comments often print 'Code: github.com/foo/bar'
    without the https:// prefix."""
    from fingerprint_atlas.code_links import extract_github_from_text
    assert (extract_github_from_text("Code available at github.com/foo/bar.")
            == "https://github.com/foo/bar")


def test_extract_github_repairs_pdf_linewraps():
    """pypdf-extracted text often splits long URLs across two lines."""
    from fingerprint_atlas.code_links import extract_github_from_text
    wrapped = "Code: https://github.com/Alicia/\nTRIBE-bond\nfor source."
    assert (extract_github_from_text(wrapped)
            == "https://github.com/Alicia/TRIBE-bond")
    hyphenated = "see https://github.com/foo/very-long-\nrepo-name (paper §3)"
    assert (extract_github_from_text(hyphenated)
            == "https://github.com/foo/very-long-repo-name")


def test_extract_github_prefers_authors_own_repo_over_tool_citation():
    """A paper that cites Baichuan as its base model and ALSO releases its
    own code should surface the OWN repo, not the base-model link, even
    though the base-model citation appears first in document order."""
    from fingerprint_atlas.code_links import extract_github_from_text
    text = (
        "We fine-tune Baichuan (https://github.com/baichuan-inc/Baichuan-13B) "
        "on financial dialogue. "
        "Our code is available at https://github.com/the-authors/finance-paper."
    )
    assert (extract_github_from_text(text)
            == "https://github.com/the-authors/finance-paper")


def test_extract_github_proximity_phrases():
    """Various phrasings that should pick the URL right after them."""
    from fingerprint_atlas.code_links import extract_github_from_text
    for prefix in (
        "Source code: https://github.com/x/y",
        "We release https://github.com/x/y .",
        "Implementation is available at https://github.com/x/y",
        "Open-source at https://github.com/x/y",
    ):
        assert extract_github_from_text(prefix) == "https://github.com/x/y", prefix


def test_extract_github_falls_back_when_no_authors_hint():
    """If no 'code available' phrase exists, return the first match."""
    from fingerprint_atlas.code_links import extract_github_from_text
    text = "We use https://github.com/foo/bar for stuff."
    assert extract_github_from_text(text) == "https://github.com/foo/bar"
