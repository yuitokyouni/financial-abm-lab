"""Unit tests for literature_map. No network; deterministic numpy."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest


def _fake_rows(n: int = 20) -> list[dict]:
    """Hand-built mini corpus spanning two obvious clusters: MG/SG papers
    and LLM-agent papers. After SVD-2D the two clusters should separate."""
    rows = []
    for i in range(n // 2):
        rows.append({
            "arxiv_id": f"mg{i:03d}",
            "title": f"Minority game variant {i} with chartists",
            "mechanism_tags": ["minority-game", "herding"],
            "oa_concepts": "Minority game, Econophysics, Herding",
            "oa_cited_by_count": 10 + i,
        })
    for i in range(n - n // 2):
        rows.append({
            "arxiv_id": f"llm{i:03d}",
            "title": f"Large language model agents for trading {i}",
            "mechanism_tags": ["LLM-agent", "sentiment"],
            "oa_concepts": "Large language model, Sentiment analysis, Trader",
            "oa_cited_by_count": 5 + i,
        })
    return rows


def test_build_corpus_filters_empty_token_rows():
    from fingerprint_atlas.literature_map import build_corpus
    rows = [
        {"title": "OK paper", "mechanism_tags": ["herding"], "oa_concepts": ""},
        {"title": "", "mechanism_tags": [], "oa_concepts": ""},  # empty
    ]
    docs, kept = build_corpus(rows)
    assert len(docs) == 1
    assert kept[0]["title"] == "OK paper"


def test_tfidf_matrix_shape_and_normalisation():
    from fingerprint_atlas.literature_map import build_corpus, tfidf_matrix
    rows = _fake_rows(20)
    docs, _ = build_corpus(rows)
    X, vocab = tfidf_matrix(docs, max_features=50)
    assert X.shape[0] == 20
    assert X.shape[1] <= 50
    # Each row L2-normalised (or zero)
    norms = np.linalg.norm(X, axis=1)
    for n in norms:
        assert n == pytest.approx(0.0, abs=1e-6) or n == pytest.approx(1.0, abs=1e-6)


def test_project_2d_separates_two_clusters():
    """Hand-built MG-vs-LLM corpus should land in two distinguishable
    blobs after SVD-2D."""
    from fingerprint_atlas.literature_map import (
        build_corpus, tfidf_matrix, project_2d,
    )
    rows = _fake_rows(20)
    docs, _ = build_corpus(rows)
    X, _ = tfidf_matrix(docs)
    coords = project_2d(X)
    assert coords.shape == (20, 2)
    # MG papers (first 10) vs LLM papers (next 10) should differ in PC1
    mg_pc1 = coords[:10, 0].mean()
    llm_pc1 = coords[10:, 0].mean()
    assert abs(mg_pc1 - llm_pc1) > 0.1


def test_render_literature_map_writes_png_and_csv(tmp_path):
    from fingerprint_atlas.literature_map import render_literature_map
    rows = _fake_rows(20)
    png = str(tmp_path / "map.png")
    csv = str(tmp_path / "map.csv")
    summary = render_literature_map(rows, png, csv_path=csv, top_labels=3)
    assert os.path.exists(png)
    assert os.path.exists(csv)
    assert summary["n_papers"] == 20
    assert summary["n_unique_tags"] >= 2  # minority-game and LLM-agent
    with open(csv) as fh:
        lines = fh.read().splitlines()
    assert lines[0].startswith("arxiv_id,x,y,")
    assert len(lines) == 21  # header + 20 rows


def test_primary_tag_falls_through_to_concept_then_other():
    from fingerprint_atlas.literature_map import primary_tag
    assert primary_tag({"mechanism_tags": ["foo"], "oa_concepts": "bar"}) == "foo"
    assert primary_tag({"mechanism_tags": [], "oa_concepts": "Econophysics, Other"}) == "Econophysics"
    assert primary_tag({"mechanism_tags": [], "oa_concepts": ""}) == "other"
