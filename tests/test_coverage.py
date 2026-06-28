"""Unit tests for coverage matrix builder + renderers."""
from __future__ import annotations

import os
import tempfile

import numpy as np


def _fake_rows() -> list[dict]:
    return [
        {"arxiv_id": "a1", "title": "MG1",
         "mechanism_tags": ["minority-game"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails", "vol-clustering"]},
        {"arxiv_id": "a2", "title": "MG2",
         "mechanism_tags": ["minority-game"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails"]},
        {"arxiv_id": "a3", "title": "LLM1",
         "mechanism_tags": ["LLM-agent"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["herding"]},
        {"arxiv_id": "a4", "title": "Ising1",
         "mechanism_tags": ["Ising-model"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails", "herding"]},
        # Paper with a fact NOT in canonical vocab — should be dropped silently
        {"arxiv_id": "a5", "title": "Misc",
         "mechanism_tags": ["LLM-agent"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["something-weird"]},
    ]


def test_build_coverage_counts_correctly():
    from fingerprint_atlas.coverage import build_coverage
    cov = build_coverage(_fake_rows(), top_rows=5)
    # mechanism tags by paper count: minority-game 2, LLM-agent 2, Ising 1
    assert "minority-game" in cov["row_labels"]
    assert "LLM-agent" in cov["row_labels"]
    # fat-tails: 2 MG + 1 Ising = 3
    i_mg = cov["row_labels"].index("minority-game")
    j_ft = cov["col_labels"].index("fat-tails")
    assert cov["matrix"][i_mg, j_ft] == 2
    i_is = cov["row_labels"].index("Ising-model")
    assert cov["matrix"][i_is, j_ft] == 1
    # herding: 1 LLM + 1 Ising = 2
    j_he = cov["col_labels"].index("herding")
    assert cov["matrix"][cov["row_labels"].index("LLM-agent"), j_he] == 1
    # something-weird gets silently dropped
    assert "something-weird" not in cov["col_labels"]


def test_render_markdown_has_totals():
    from fingerprint_atlas.coverage import build_coverage, render_markdown
    cov = build_coverage(_fake_rows())
    md = render_markdown(cov)
    assert "mechanism" in md
    assert "fat-tails" in md
    assert "total" in md.lower()
    # Should have a row per surveyed mechanism + 1 totals row + 2 header rows
    n_data_lines = sum(1 for line in md.splitlines()
                       if line.startswith("|") and "---" not in line)
    assert n_data_lines >= 4


def test_render_heatmap_writes_png(tmp_path):
    from fingerprint_atlas.coverage import build_coverage, render_heatmap
    cov = build_coverage(_fake_rows())
    out = str(tmp_path / "cov.png")
    render_heatmap(cov, out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000  # non-empty PNG


def test_build_coverage_drops_zero_total_rows():
    """A tag that only appears in papers whose stylized_facts_targeted is
    empty or non-canonical should NOT show up as a row (visual noise)."""
    from fingerprint_atlas.coverage import build_coverage
    rows = [
        {"arxiv_id": "g1", "title": "Generic", "mechanism_tags": [],
         "oa_concepts": "Computer science",
         "stylized_facts_targeted": []},  # zero-total, generic concept
        {"arxiv_id": "g2", "title": "MG2",
         "mechanism_tags": ["minority-game"],
         "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails"]},
    ]
    cov = build_coverage(rows, top_rows=10)
    assert "minority-game" in cov["row_labels"]
    assert "Computer science" not in cov["row_labels"]
    assert "untagged" not in cov["row_labels"]
