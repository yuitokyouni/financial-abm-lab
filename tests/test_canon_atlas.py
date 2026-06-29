"""Unit tests for canon_atlas (subfield sweep, render, gap-fill list).
Network monkeypatched."""
from __future__ import annotations

import os


def _fake_canon_factory(papers_by_query):
    """Return a fake find_canon_papers(query, n, year_max=None) impl."""
    def fake(query, *, n=8, year_max=None):
        return papers_by_query.get(query, [])
    return fake


def test_build_atlas_annotates_in_db_correctly(monkeypatch):
    from fingerprint_atlas import canon_atlas
    from fingerprint_atlas.subfields import Subfield

    # Two subfields, one mostly in DB, one mostly missing
    fake_papers = {
        "topic A": [
            {"oa_paper_id": "W1", "arxiv_id": "1001.0001",
             "title": "A1", "year": 2001, "cited_by_count": 100, "doi": "10/a1"},
            {"oa_paper_id": "W2", "arxiv_id": "1001.0002",
             "title": "A2", "year": 2002, "cited_by_count": 80, "doi": None},
            {"oa_paper_id": "W3", "arxiv_id": None,
             "title": "A3 (book)", "year": 2003, "cited_by_count": 60,
             "doi": "10/a3"},
        ],
        "topic B": [
            {"oa_paper_id": "W4", "arxiv_id": "1002.0001",
             "title": "B1", "year": 2010, "cited_by_count": 50, "doi": None},
            {"oa_paper_id": "W5", "arxiv_id": "1002.0002v2",
             "title": "B2", "year": 2011, "cited_by_count": 30, "doi": None},
        ],
    }
    monkeypatch.setattr(canon_atlas, "find_canon_papers",
                         _fake_canon_factory(fake_papers))
    monkeypatch.setattr(canon_atlas, "sleep_for_rate_limit", lambda s: None)

    subfields: list[Subfield] = [
        {"key": "a", "name": "A", "category": "foundational", "query": "topic A"},
        {"key": "b", "name": "B", "category": "stylized", "query": "topic B"},
    ]
    db_ids = {"1001.0001", "1002.0001"}  # 1/2 on-arxiv for A, 1/2 for B

    atlas = canon_atlas.build_atlas(subfields, db_arxiv_ids=db_ids,
                                      n_per_subfield=8, sleep=0)

    assert len(atlas) == 2
    a = next(e for e in atlas if e["key"] == "a")
    b = next(e for e in atlas if e["key"] == "b")

    # A: 3 canon, 2 on arxiv (W3 has no arxiv_id), 1 in DB → coverage 50%
    assert a["n_canon"] == 3
    assert a["n_on_arxiv"] == 2
    assert a["n_in_db"] == 1
    assert a["coverage"] == 0.5

    # B: 2 canon, 2 on arxiv, 1 in DB (version suffix stripping for W5)
    assert b["n_canon"] == 2
    assert b["n_on_arxiv"] == 2
    assert b["n_in_db"] == 1
    assert b["coverage"] == 0.5

    # in_db flag set correctly per paper
    a_papers = {p["arxiv_id"]: p for p in a["papers"]}
    assert a_papers["1001.0001"]["in_db"] is True
    assert a_papers["1001.0002"]["in_db"] is False
    # paper with no arxiv_id keeps in_db False
    assert next(p for p in a["papers"] if p["arxiv_id"] is None)["in_db"] is False


def test_build_atlas_coverage_none_when_no_arxiv(monkeypatch):
    from fingerprint_atlas import canon_atlas
    fake_papers = {
        "only-books": [
            {"oa_paper_id": "W9", "arxiv_id": None, "title": "Book",
             "year": 2000, "cited_by_count": 1000, "doi": "10/x"},
        ],
    }
    monkeypatch.setattr(canon_atlas, "find_canon_papers",
                         _fake_canon_factory(fake_papers))
    monkeypatch.setattr(canon_atlas, "sleep_for_rate_limit", lambda s: None)
    atlas = canon_atlas.build_atlas(
        [{"key": "x", "name": "X", "category": "foundational",
          "query": "only-books"}],
        db_arxiv_ids=set(), sleep=0,
    )
    assert atlas[0]["coverage"] is None
    assert atlas[0]["n_on_arxiv"] == 0


def test_missing_arxiv_ids_dedupes_and_skips_in_db():
    from fingerprint_atlas.canon_atlas import missing_arxiv_ids
    atlas = [
        {"papers": [
            {"arxiv_id": "1001.0001", "in_db": True},   # skip: already in DB
            {"arxiv_id": "1001.0002", "in_db": False},  # take
            {"arxiv_id": None, "in_db": False},         # skip: no arxiv
        ]},
        {"papers": [
            {"arxiv_id": "1001.0002", "in_db": False},  # dup of above
            {"arxiv_id": "1002.0003v3", "in_db": False},  # version suffix
        ]},
    ]
    assert missing_arxiv_ids(atlas) == ["1001.0002", "1002.0003"]


def test_render_html_writes_self_contained_file(tmp_path):
    from fingerprint_atlas.canon_atlas import render_html
    atlas = [
        {"key": "mg", "name": "Minority Game",
         "category": "foundational", "query": "Minority game",
         "seed_arxiv": "adap-org/9708006",
         "papers": [
             {"oa_paper_id": "W1", "arxiv_id": "adap-org/9708006",
              "title": "Emergence of cooperation", "year": 1997,
              "cited_by_count": 924, "doi": None, "in_db": True},
             {"oa_paper_id": "W2", "arxiv_id": None,
              "title": "Theory of Financial Risk", "year": 2003,
              "cited_by_count": 867, "doi": "10/x", "in_db": False},
         ],
         "n_canon": 2, "n_on_arxiv": 1, "n_in_db": 1, "coverage": 1.0},
        {"key": "leverage", "name": "Leverage effect",
         "category": "stylized", "query": "leverage effect",
         "seed_arxiv": None,
         "papers": [
             {"oa_paper_id": "W3", "arxiv_id": "cond-mat/0101120",
              "title": "Leverage effect in volatility", "year": 2001,
              "cited_by_count": 200, "doi": None, "in_db": False},
         ],
         "n_canon": 1, "n_on_arxiv": 1, "n_in_db": 0, "coverage": 0.0},
    ]
    out = str(tmp_path / "atlas.html")
    render_html(atlas, out, title="canon atlas test")

    assert os.path.exists(out)
    with open(out) as fh:
        body = fh.read()
    # title + section headers present
    assert "canon atlas test" in body
    assert "Minority Game" in body
    assert "Leverage effect" in body
    # category legend present
    assert "foundational" in body
    assert "stylized" in body
    # in-DB / missing badges present
    assert "in DB" in body
    assert "missing" in body
    # links to arxiv pages
    assert "arxiv.org/abs/adap-org/9708006" in body
    # coverage % rendered (100% and 0%)
    assert "100%" in body
    assert "0%" in body


def test_subfields_list_well_formed():
    from fingerprint_atlas.subfields import SUBFIELDS
    assert len(SUBFIELDS) >= 25
    keys = [s["key"] for s in SUBFIELDS]
    assert len(set(keys)) == len(keys), "subfield keys must be unique"
    for s in SUBFIELDS:
        assert s["key"] and s["name"] and s["query"] and s["category"]
        assert "/" not in s["key"], f"key {s['key']!r} must be path-safe"
