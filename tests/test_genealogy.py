"""Unit tests for canon detection + genealogy tree. Network monkeypatched."""
from __future__ import annotations

import os


def test_find_concept_id_resolves_display_name(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {"results": [
        {"id": "https://openalex.org/C2779489203",
         "display_name": "Minority game"},
    ]}
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    assert oa.find_concept_id("Minority game") == "https://openalex.org/C2779489203"


def test_find_canon_papers_returns_sorted(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {"results": [
        {"id": "https://openalex.org/W1", "title": "Foundational paper",
         "publication_year": 1997, "cited_by_count": 500,
         "ids": {"arxiv": "https://arxiv.org/abs/cond-mat/9712151"},
         "doi": "10.1/abc"},
        {"id": "https://openalex.org/W2", "title": "Less foundational",
         "publication_year": 2005, "cited_by_count": 50,
         "ids": {}, "doi": None},
    ]}
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa.find_canon_papers("C12345", n=5)
    assert len(out) == 2
    assert out[0]["arxiv_id"] == "cond-mat/9712151"
    assert out[0]["cited_by_count"] == 500


def test_find_citing_papers_extracts_concepts(monkeypatch):
    from fingerprint_atlas import openalex as oa
    fake = {"results": [
        {"id": "https://openalex.org/W3", "title": "Citing paper",
         "publication_year": 2010, "cited_by_count": 80,
         "ids": {"arxiv": "https://arxiv.org/abs/1001.0001"},
         "doi": None,
         "concepts": [{"display_name": "Econophysics"},
                       {"display_name": "Agent-based model"}]},
    ]}
    monkeypatch.setattr(oa, "_http_get_json", lambda url, **kw: fake)
    out = oa.find_citing_papers("https://openalex.org/W1", n=5)
    assert len(out) == 1
    assert out[0]["concepts"] == ["Econophysics", "Agent-based model"]


def test_build_tree_walks_depth(monkeypatch):
    from fingerprint_atlas import genealogy

    def fake_citing(oa_id, n=50, year_max=None, min_cited_by=0):
        if oa_id == "W_root":
            return [
                {"oa_paper_id": "W_a", "arxiv_id": "1101.0001",
                 "title": "Child A", "year": 2000, "cited_by_count": 50,
                 "concepts": ["A"]},
                {"oa_paper_id": "W_b", "arxiv_id": "1101.0002",
                 "title": "Child B", "year": 2001, "cited_by_count": 30,
                 "concepts": ["B"]},
            ]
        return []

    monkeypatch.setattr(genealogy, "find_citing_papers", fake_citing)
    monkeypatch.setattr("time.sleep", lambda s: None)
    tree = genealogy.build_tree(
        "W_root", root_arxiv_id="cond-mat/9999999", root_title="Root",
        root_year=1997, root_cit=500,
        depth=2, per_node=10, sleep=0,
    )
    ids = {n["id"] for n in tree["nodes"]}
    assert ids == {"W_root", "W_a", "W_b"}
    assert len(tree["edges"]) == 2
    by_id = {n["id"]: n for n in tree["nodes"]}
    assert by_id["W_root"]["depth"] == 0
    assert by_id["W_a"]["depth"] == 1


def test_render_html_writes_self_contained_file(tmp_path):
    from fingerprint_atlas.genealogy import render_html
    tree = {
        "nodes": [
            {"id": "W_root", "label": "Root paper", "arxiv_id": "1001.0001",
             "year": 1997, "cited_by_count": 500,
             "concept": "root", "depth": 0},
            {"id": "W_a", "label": "Child A", "arxiv_id": "1101.0001",
             "year": 2005, "cited_by_count": 80,
             "concept": "A", "depth": 1},
        ],
        "edges": [{"source": "W_root", "target": "W_a"}],
    }
    out = str(tmp_path / "tree.html")
    render_html(tree, out, title="test")
    assert os.path.exists(out)
    with open(out) as fh:
        body = fh.read()
    assert "vis-network" in body
    assert "W_root" in body and "W_a" in body
    assert "Root paper" in body


def test_filter_tree_removes_noise_branch_and_merges_duplicate_titles():
    from fingerprint_atlas.genealogy import filter_tree

    tree = {
        "nodes": [
            {"id": "root", "label": "Minority Game", "concept": "root",
             "depth": 0, "cited_by_count": 100},
            {"id": "market", "label": "Adaptive market game",
             "concept": "Economics", "depth": 1, "cited_by_count": 20},
            {"id": "market-copy", "label": "Adaptive market game",
             "concept": "Economics", "depth": 1, "cited_by_count": 10},
            {"id": "useful", "label": "Minority game dynamics",
             "concept": "Game theory", "depth": 2, "cited_by_count": 5},
            {"id": "noise", "label": "Silicon fracture",
             "concept": "Materials science", "depth": 1, "cited_by_count": 30},
            {"id": "orphan", "label": "Market pricing",
             "concept": "Finance", "depth": 2, "cited_by_count": 8},
        ],
        "edges": [
            {"source": "root", "target": "market"},
            {"source": "root", "target": "market-copy"},
            {"source": "market", "target": "useful"},
            {"source": "noise", "target": "orphan"},
            {"source": "root", "target": "noise"},
        ],
    }

    filtered = filter_tree(
        tree,
        ["minority", "market", "game theory"],
        ["silicon"],
    )

    assert {node["id"] for node in filtered["nodes"]} == {
        "root", "market", "useful",
    }
    assert filtered["edges"] == [
        {"source": "market", "target": "useful"},
        {"source": "root", "target": "market"},
    ]


def test_find_canon_papers_falls_back_to_search_when_no_concept(monkeypatch):
    """When OpenAlex has no concept for the query (e.g. 'Minority game'),
    find_canon_papers must fall back to /works?search=...&sort=cited_by_count
    and return high-cited papers anyway."""
    from fingerprint_atlas import openalex as oa
    calls = []

    def fake_http(url, **kw):
        calls.append(url)
        # First call: find_concept_id /concepts → empty
        if "/concepts?" in url:
            return {"results": []}
        # Second call: find_concept_id fallback /works?search= → empty concepts
        if "select=concepts" in url:
            return {"results": [{"concepts": []}]}
        # Third call: find_canon_papers /works with title_and_abstract.search filter
        if "title_and_abstract.search" in url:
            return {"results": [
                {"id": "https://openalex.org/W1",
                 "title": "Statistical mechanics of the minority game",
                 "publication_year": 2000, "cited_by_count": 800,
                 "ids": {"arxiv": "https://arxiv.org/abs/cond-mat/9909265"},
                 "doi": "10.1/x"},
                {"id": "https://openalex.org/W2",
                 "title": "Minority game and the price of information",
                 "publication_year": 2002, "cited_by_count": 300,
                 "ids": {}, "doi": None},
            ]}
        return None

    monkeypatch.setattr(oa, "_http_get_json", fake_http)
    out = oa.find_canon_papers("Minority game", n=5)
    assert len(out) == 2
    assert out[0]["cited_by_count"] == 800
    assert out[0]["arxiv_id"] == "cond-mat/9909265"
    # Fallback path: filter=title_and_abstract.search:..., cit-floor,
    # NOT concept-id based.
    last_url = calls[-1]
    assert "title_and_abstract.search" in last_url
    assert "cited_by_count" in last_url
    assert "concepts.id" not in last_url
