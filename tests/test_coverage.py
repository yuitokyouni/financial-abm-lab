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
    # Row labels are normalised lowercase slugs now (case variants used
    # to split one mechanism into two rows).
    assert "minority-game" in cov["row_labels"]
    assert "ising-model" in cov["row_labels"]
    # fat-tails: 2 MG + 1 Ising = 3 (Ising's 'herding' also drops silently)
    i_mg = cov["row_labels"].index("minority-game")
    j_ft = cov["col_labels"].index("fat-tails")
    assert cov["matrix"][i_mg, j_ft] == 2
    i_is = cov["row_labels"].index("ising-model")
    assert cov["matrix"][i_is, j_ft] == 1
    # herding was removed from the fact enum — it's a mechanism, not a fact
    assert "herding" not in cov["col_labels"]
    # something-weird gets silently dropped
    assert "something-weird" not in cov["col_labels"]
    # families are attached per row
    assert cov.get("row_families") is not None
    assert len(cov["row_families"]) == len(cov["row_labels"])
    # distinct-papers-per-row is tracked separately from cell sums:
    # MG has 2 papers; the first has 2 facts so cell-sum is 3.
    assert cov["row_papers"][i_mg] == 2
    assert cov["row_totals"][i_mg] == 3
    assert cov["mean_facts_per_paper"] > 1.0


def test_build_coverage_case_variants_collapse_to_one_row():
    """'Minority-Game' vs 'minority-game' used to split into two matrix
    rows. Both must land in one normalised row now."""
    from fingerprint_atlas.coverage import build_coverage
    rows = [
        {"arxiv_id": "c1", "title": "MG cased",
         "mechanism_tags": ["Minority-Game"], "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails"]},
        {"arxiv_id": "c2", "title": "MG lower",
         "mechanism_tags": ["minority-game"], "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails"]},
        {"arxiv_id": "c3", "title": "LOB alias",
         "mechanism_tags": ["limit-order-book"], "oa_concepts": "",
         "stylized_facts_targeted": ["vol-clustering"]},
    ]
    cov = build_coverage(rows, top_rows=5)
    assert cov["row_labels"].count("minority-game") == 1
    assert "Minority-Game" not in cov["row_labels"]
    # limit-order-book aliases into order-book (ABM family)
    assert "order-book" in cov["row_labels"]
    assert "limit-order-book" not in cov["row_labels"]
    i_mg = cov["row_labels"].index("minority-game")
    j_ft = cov["col_labels"].index("fat-tails")
    assert cov["matrix"][i_mg, j_ft] == 2


def test_build_coverage_suppresses_other_when_real_facts_present():
    """Multi-label extraction emits 'other' alongside real facts; counting
    it inflates the other column into the matrix maximum. 'other' should
    count ONLY when it's the paper's sole mapped fact."""
    from fingerprint_atlas.coverage import build_coverage
    rows = [
        {"arxiv_id": "o1", "title": "real fact + other",
         "mechanism_tags": ["order-book"], "oa_concepts": "",
         "stylized_facts_targeted": ["fat-tails", "other"]},
        {"arxiv_id": "o2", "title": "only other",
         "mechanism_tags": ["order-book"], "oa_concepts": "",
         "stylized_facts_targeted": ["other"]},
    ]
    cov = build_coverage(rows, top_rows=5)
    i = cov["row_labels"].index("order-book")
    j_other = cov["col_labels"].index("other")
    j_ft = cov["col_labels"].index("fat-tails")
    assert cov["matrix"][i, j_ft] == 1
    # only o2 counts toward 'other'; o1's tag-along 'other' is dropped
    assert cov["matrix"][i, j_other] == 1


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
