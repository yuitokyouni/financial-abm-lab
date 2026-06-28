"""Unit tests for openalex helpers. Network monkeypatched out."""
from __future__ import annotations

import tempfile

import pytest


def test_arxiv_doi_constructs_canonical_doi():
    from fingerprint_atlas.openalex import _arxiv_doi
    assert _arxiv_doi("2503.00320v2") == "10.48550/arXiv.2503.00320"
    assert _arxiv_doi("  1909.03185  ") == "10.48550/arXiv.1909.03185"
    assert _arxiv_doi("cond-mat/9712151") == "10.48550/arXiv.cond-mat/9712151"


def test_fetch_paper_normalises_oa_payload(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {
        "id": "https://openalex.org/W12345",
        "title": "TRIBE",
        "publication_year": 2025,
        "cited_by_count": 7,
        "concepts": [
            {"display_name": "Econophysics"},
            {"display_name": "Agent-based model"},
            {"display_name": "Bond market"},
        ],
        "referenced_works": ["https://openalex.org/W111",
                              "https://openalex.org/W222"],
        "open_access": {"oa_url": "https://arxiv.org/pdf/2503.00320"},
        "doi": "https://doi.org/10.48550/arxiv.2503.00320",
    }
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa.fetch_paper("2503.00320v2")
    assert out["oa_paper_id"] == "https://openalex.org/W12345"
    assert out["cited_by_count"] == 7
    assert out["concepts"] == ["Econophysics", "Agent-based model", "Bond market"]
    assert len(out["referenced_works"]) == 2


def test_fetch_paper_returns_none_on_miss(monkeypatch):
    from fingerprint_atlas import openalex as oa
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: None)
    assert oa.fetch_paper("9999.99999") is None


def test_resolve_oa_work_extracts_arxiv_id_from_ids(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {
        "id": "https://openalex.org/W77",
        "title": "Minority Game",
        "publication_year": 1997,
        "cited_by_count": 500,
        "ids": {"arxiv": "https://arxiv.org/abs/cond-mat/9712151"},
    }
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa._resolve_oa_work("https://openalex.org/W77")
    assert out["arxiv_id"] == "cond-mat/9712151"


def test_resolve_oa_work_falls_back_to_location_url(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {
        "id": "https://openalex.org/W88",
        "title": "X",
        "publication_year": 2020,
        "cited_by_count": 10,
        "ids": {},
        "locations": [{"landing_page_url": "https://arxiv.org/abs/2003.04567"}],
    }
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa._resolve_oa_work("https://openalex.org/W88")
    assert out["arxiv_id"] == "2003.04567"


def test_set_oa_metadata_roundtrip():
    from fingerprint_atlas.db import (
        ensure_literature_schema, upsert_literature_metadata,
        load_literature, set_oa_metadata,
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
        set_oa_metadata(
            db, "1909.03185",
            oa_paper_id="https://openalex.org/W123",
            oa_cited_by_count=42,
            oa_concepts="Econophysics, Agent-based model",
        )
        row = load_literature(db)[0]
        assert row["oa_paper_id"] == "https://openalex.org/W123"
        assert row["oa_cited_by_count"] == 42
        assert "Econophysics" in row["oa_concepts"]
        assert row["oa_fetched_at"]


def test_search_by_title_returns_canonical_arxiv_id(monkeypatch):
    """OpenAlex title search resolves to canonical arxiv_id with category
    prefix preserved — the recovery path for rows whose arxiv_id was
    stored in the broken truncated form."""
    from fingerprint_atlas import openalex as oa
    fake = {
        "results": [
            {
                "id": "https://openalex.org/W77",
                "title": "Stylized facts of financial markets",
                "publication_year": 2001,
                "ids": {"arxiv": "https://arxiv.org/abs/cond-mat/0101326"},
                "doi": "10.48550/arxiv.cond-mat/0101326",
            },
        ],
    }
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa.search_by_title("Stylized facts of financial markets",
                              year=2001)
    assert out["arxiv_id"] == "cond-mat/0101326"
    assert "openalex.org/W77" in out["oa_paper_id"]


def test_search_by_title_year_disambiguates(monkeypatch):
    """When the top hit is a different-year paper, the year filter
    should skip it and pick the next candidate."""
    from fingerprint_atlas import openalex as oa
    fake = {
        "results": [
            {  # wrong year — should be skipped
                "id": "https://openalex.org/Wbad",
                "publication_year": 1990,
                "ids": {"arxiv": "https://arxiv.org/abs/wrong/year"},
            },
            {  # right year
                "id": "https://openalex.org/Wgood",
                "publication_year": 2001,
                "ids": {"arxiv": "https://arxiv.org/abs/cond-mat/0101326"},
            },
        ],
    }
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa.search_by_title("anything", year=2001)
    assert out["arxiv_id"] == "cond-mat/0101326"
