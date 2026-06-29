"""Tests for canon_ingest — OpenAlex-only canon row insertion.
Network monkeypatched."""
from __future__ import annotations


def test_reconstruct_abstract_from_inverted_index():
    from fingerprint_atlas.openalex import _reconstruct_abstract
    inverted = {"the": [0, 2], "cat": [1], "sat": [3]}
    assert _reconstruct_abstract(inverted) == "the cat the sat"


def test_reconstruct_abstract_empty_inputs():
    from fingerprint_atlas.openalex import _reconstruct_abstract
    assert _reconstruct_abstract(None) == ""
    assert _reconstruct_abstract({}) == ""
    # malformed positions are silently dropped
    assert _reconstruct_abstract({"foo": "bad"}) == ""


def test_synthetic_arxiv_id():
    from fingerprint_atlas.canon_ingest import _synthetic_arxiv_id
    assert _synthetic_arxiv_id("https://openalex.org/W2091653681") == "oa:W2091653681"
    assert _synthetic_arxiv_id("W12345") == "oa:W12345"
    assert _synthetic_arxiv_id("not-an-id") is None


def test_is_openalex_synthetic_id():
    from fingerprint_atlas.canon_ingest import is_openalex_synthetic_id
    assert is_openalex_synthetic_id("oa:W12345") is True
    assert is_openalex_synthetic_id("2412.01234") is False
    assert is_openalex_synthetic_id("cond-mat/9708006") is False
    assert is_openalex_synthetic_id(None) is False
    assert is_openalex_synthetic_id("") is False


def test_ingest_canon_via_oa_inserts_rows(tmp_path, monkeypatch):
    from fingerprint_atlas import canon_ingest
    from fingerprint_atlas.db import load_literature

    db = str(tmp_path / "test.db")

    fake_works = {
        "W001": {
            "oa_paper_id": "https://openalex.org/W001",
            "title": "Why Does Stock Market Volatility Change Over Time?",
            "authors": "G. William Schwert",
            "year": 1989,
            "published_date": "1989-12-01",
            "doi": "10.1111/j.1540-6261.1989.tb02647.x",
            "abstract": "This paper analyzes time-varying volatility.",
            "cited_by_count": 3555,
            "concepts": ["Volatility", "Econometrics"],
            "arxiv_id": None,
        },
        "W002": {
            "oa_paper_id": "https://openalex.org/W002",
            "title": "Common risk factors in the returns on stocks and bonds",
            "authors": "Eugene F. Fama, Kenneth R. French",
            "year": 1993,
            "published_date": "1993-02-01",
            "doi": "10.1016/0304-405X(93)90023-5",
            "abstract": "Fama-French three-factor model.",
            "cited_by_count": 18000,
            "concepts": ["Asset pricing", "Risk factor"],
            "arxiv_id": None,
        },
    }

    def fake_fetch(oa_id):
        import re
        m = re.search(r"W\d+", oa_id)
        return fake_works.get(m.group(0)) if m else None

    monkeypatch.setattr(canon_ingest, "fetch_work_full", fake_fetch)
    monkeypatch.setattr(canon_ingest, "sleep_for_rate_limit", lambda s: None)

    summary = canon_ingest.ingest_canon_via_oa(
        db, ["https://openalex.org/W001", "https://openalex.org/W002"],
        sleep=0,
    )
    assert summary["added"] == 2
    assert summary["skipped"] == 0
    assert summary["errors"] == []

    rows = load_literature(db)
    assert len(rows) == 2
    by_id = {r["arxiv_id"]: r for r in rows}
    assert "oa:W001" in by_id and "oa:W002" in by_id
    schwert = by_id["oa:W001"]
    assert schwert["title"].startswith("Why Does Stock Market")
    assert schwert["year"] == 1989
    assert schwert["oa_cited_by_count"] == 3555
    assert "Volatility" in (schwert["oa_concepts"] or "")
    assert schwert["source_kind"] == "openalex"


def test_ingest_canon_via_oa_idempotent(tmp_path, monkeypatch):
    """Re-running on the same ids must be a no-op."""
    from fingerprint_atlas import canon_ingest

    db = str(tmp_path / "test.db")
    fake_work = {
        "oa_paper_id": "https://openalex.org/W001",
        "title": "Sample", "authors": "A. Author", "year": 2000,
        "published_date": "2000-01-01", "doi": None,
        "abstract": "sample abstract", "cited_by_count": 100,
        "concepts": ["X"], "arxiv_id": None,
    }
    monkeypatch.setattr(canon_ingest, "fetch_work_full",
                         lambda oa: fake_work)
    monkeypatch.setattr(canon_ingest, "sleep_for_rate_limit", lambda s: None)

    s1 = canon_ingest.ingest_canon_via_oa(db, ["W001"], sleep=0)
    s2 = canon_ingest.ingest_canon_via_oa(db, ["W001"], sleep=0)
    assert s1["added"] == 1 and s1["skipped"] == 0
    assert s2["added"] == 0 and s2["skipped"] == 1


def test_ingest_canon_via_oa_handles_missing_metadata(tmp_path, monkeypatch):
    """Works missing required fields (title/year) must be reported in errors."""
    from fingerprint_atlas import canon_ingest

    db = str(tmp_path / "test.db")
    bad_work = {"oa_paper_id": "https://openalex.org/W001",
                "title": None, "year": None,  # missing!
                "authors": "", "abstract": "", "concepts": []}
    monkeypatch.setattr(canon_ingest, "fetch_work_full",
                         lambda oa: bad_work)
    monkeypatch.setattr(canon_ingest, "sleep_for_rate_limit", lambda s: None)

    summary = canon_ingest.ingest_canon_via_oa(db, ["W001"], sleep=0)
    assert summary["added"] == 0
    assert len(summary["errors"]) == 1
    assert "missing required field" in summary["errors"][0]["why"]


def test_ingest_canon_via_oa_handles_empty_abstract(tmp_path, monkeypatch):
    """No abstract → synthesized placeholder so NOT NULL constraint holds."""
    from fingerprint_atlas import canon_ingest
    from fingerprint_atlas.db import load_literature

    db = str(tmp_path / "test.db")
    no_abs_work = {
        "oa_paper_id": "https://openalex.org/W007",
        "title": "Old paper without indexed abstract",
        "authors": "X. Y.", "year": 1985,
        "published_date": "1985-01-01", "doi": None,
        "abstract": "", "cited_by_count": 200,
        "concepts": [], "arxiv_id": None,
    }
    monkeypatch.setattr(canon_ingest, "fetch_work_full",
                         lambda oa: no_abs_work)
    monkeypatch.setattr(canon_ingest, "sleep_for_rate_limit", lambda s: None)

    summary = canon_ingest.ingest_canon_via_oa(db, ["W007"], sleep=0)
    assert summary["added"] == 1
    rows = load_literature(db)
    assert "[no abstract available" in rows[0]["abstract"]
