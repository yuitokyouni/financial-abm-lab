"""Unit tests for semantic_scholar helpers. Network monkeypatched out."""
from __future__ import annotations

import tempfile

import pytest


def test_arxiv_base_strips_version_and_whitespace():
    from fingerprint_atlas.semantic_scholar import _arxiv_base
    assert _arxiv_base("2503.00320v2") == "2503.00320"
    assert _arxiv_base("  cond-mat/9712151  ") == "cond-mat/9712151"
    assert _arxiv_base("1909.03185") == "1909.03185"


def test_fetch_paper_normalises_s2_payload(monkeypatch):
    from fingerprint_atlas import semantic_scholar as s2
    fake_payload = {
        "paperId": "abc123def456",
        "title": "TRIBE: LLM agents in bond markets",
        "year": 2025,
        "citationCount": 7,
        "influentialCitationCount": 2,
        "tldr": {"text": "An LLM-augmented ABM of bilateral bond markets."},
        "externalIds": {"DOI": "10.1234/xyz", "ArXiv": "2503.00320"},
        "openAccessPdf": {"url": "https://arxiv.org/pdf/2503.00320"},
    }
    monkeypatch.setattr(s2, "_http_get_json", lambda url, **kw: fake_payload)
    out = s2.fetch_paper("2503.00320v2")
    assert out["s2_paper_id"] == "abc123def456"
    assert out["tldr"] == "An LLM-augmented ABM of bilateral bond markets."
    assert out["influential_citation_count"] == 2
    assert out["external_ids"]["DOI"] == "10.1234/xyz"
    assert out["open_access_pdf"] == "https://arxiv.org/pdf/2503.00320"


def test_fetch_paper_returns_none_on_miss(monkeypatch):
    from fingerprint_atlas import semantic_scholar as s2
    monkeypatch.setattr(s2, "_http_get_json", lambda url, **kw: None)
    assert s2.fetch_paper("9999.99999") is None


def test_fetch_paper_handles_null_tldr_or_pdf(monkeypatch):
    """S2 returns tldr=null and openAccessPdf=null for many older papers.
    Must not crash on .get() against None."""
    from fingerprint_atlas import semantic_scholar as s2
    payload = {
        "paperId": "x", "title": "y", "year": 2000,
        "citationCount": 0, "influentialCitationCount": 0,
        "tldr": None, "externalIds": {}, "openAccessPdf": None,
    }
    monkeypatch.setattr(s2, "_http_get_json", lambda url, **kw: payload)
    out = s2.fetch_paper("1234.56789")
    assert out["tldr"] is None
    assert out["open_access_pdf"] is None


def test_fetch_references_normalises_s2_payload(monkeypatch):
    from fingerprint_atlas import semantic_scholar as s2
    fake = {
        "data": [
            {
                "citedPaper": {
                    "paperId": "ref1",
                    "title": "Minority Game",
                    "year": 1997,
                    "externalIds": {"ArXiv": "cond-mat/9712151"},
                    "citationCount": 500,
                    "influentialCitationCount": 80,
                },
            },
            {"citedPaper": None},   # missing → skipped
            {
                "citedPaper": {
                    "paperId": "ref2",
                    "title": "Old Paper No Arxiv",
                    "year": 1990,
                    "externalIds": {"DOI": "10.1/x"},
                    "citationCount": 50,
                    "influentialCitationCount": 5,
                },
            },
        ],
    }
    monkeypatch.setattr(s2, "_http_get_json", lambda url, **kw: fake)
    refs = s2.fetch_references("1909.03185")
    assert len(refs) == 2  # the None citedPaper got dropped
    assert refs[0]["arxiv_id"] == "cond-mat/9712151"
    assert refs[1]["arxiv_id"] is None
    assert refs[1]["doi"] == "10.1/x"


def test_set_s2_metadata_persists(monkeypatch):
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata, load_literature,
        set_s2_metadata,
    )
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/lit.db"
        ensure_literature_schema(db)
        upsert_literature_metadata(
            db, arxiv_id="1909.03185", title="Katahira-Chen 2019",
            authors="K, C", year=2019,
            published_date="2019-09-06T00:00:00Z",
            primary_category="q-fin.TR", abstract="",
        )
        set_s2_metadata(
            db, "1909.03185",
            s2_paper_id="kc2019",
            s2_tldr="Self-organized speculation game.",
            s2_influential_citation_count=15,
        )
        row = load_literature(db)[0]
        assert row["s2_paper_id"] == "kc2019"
        assert row["s2_tldr"].startswith("Self-organized")
        assert row["s2_influential_citation_count"] == 15
        assert row["s2_fetched_at"]


def test_http_get_json_with_status_returns_404_distinctly(monkeypatch):
    """A 404 must surface as status=404, not collapse to None like a
    network error — so the caller can stamp 'fetched_at' on real misses
    but retry on transient rate-limits."""
    import urllib.error
    from fingerprint_atlas import semantic_scholar as s2

    class _Fake404(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", 404, "Not Found", {}, None)

    def fake_urlopen(*a, **kw):
        raise _Fake404()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    status, body = s2._http_get_json_with_status("https://example.com/x")
    assert status == 404
    assert body is None


def test_http_get_json_retries_on_429(monkeypatch):
    """The convenience _http_get_json should sleep + retry once on 429,
    so a transient rate-limit doesn't masquerade as a real miss."""
    import urllib.error
    from fingerprint_atlas import semantic_scholar as s2

    calls = {"n": 0}

    def fake_status(url, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, None
        return 200, {"ok": True}

    monkeypatch.setattr(s2, "_http_get_json_with_status", fake_status)
    monkeypatch.setattr("time.sleep", lambda s: None)
    out = s2._http_get_json("https://example.com/x")
    assert out == {"ok": True}
    assert calls["n"] == 2


def test_http_get_json_returns_none_on_persistent_429(monkeypatch):
    from fingerprint_atlas import semantic_scholar as s2
    monkeypatch.setattr(s2, "_http_get_json_with_status",
                         lambda url, timeout=None: (429, None))
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert s2._http_get_json("https://example.com/x") is None
