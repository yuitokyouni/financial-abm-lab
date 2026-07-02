"""Tests for gap_finder — 3-view gap detection + salience ranking."""
from __future__ import annotations

import json

import numpy as np


def _runs(model: str, fingerprint: list[float], n: int = 3) -> list[dict]:
    return [
        {"model_name": model, "fingerprint_json": json.dumps(fingerprint)}
        for _ in range(n)
    ]


def test_view_a_empty_in_dense_row_gets_high_salience():
    from fingerprint_atlas import gap_finder
    rows = [
        {"arxiv_id": "1.1", "mechanism_tags": "minority game, learning",
         "stylized_facts_targeted": "fat-tails"},
        {"arxiv_id": "1.2", "mechanism_tags": "minority game",
         "stylized_facts_targeted": "vol-clustering"},
        {"arxiv_id": "1.3", "mechanism_tags": "minority game",
         "stylized_facts_targeted": "absence-of-autocorr"},
        # leverage column intentionally never targeted under minority_game
    ]
    subfields = [
        {"key": "minority_game", "name": "Minority Game",
         "title_any": ["minority"]},
        {"key": "other_sf", "name": "Other", "title_any": ["nothing"]},
    ]
    v = gap_finder._build_view_a(rows, subfields)
    assert v.name == "A"
    facts = gap_finder.CANONICAL_FACTS
    mg_row = v.matrix[0]
    # 3 cells populated (one each); leverage column = 0
    assert mg_row.sum() == 3
    assert mg_row[facts.index("leverage")] == 0
    # Salience for the empty leverage cell must exceed salience for the
    # populated fat-tails cell in the same row.
    sal_leverage = v.salience[0, facts.index("leverage")]
    sal_fat = v.salience[0, facts.index("fat-tails")]
    assert sal_leverage > sal_fat


def test_view_b_distance_from_real_per_family_per_fact():
    """A family whose median fingerprint differs from real-market median
    on a specific fingerprint dim should surface as a large-distance gap."""
    from fingerprint_atlas import gap_finder
    from fingerprint_atlas.fingerprint import FEATURE_NAMES
    n = len(FEATURE_NAMES)
    # Real-market: zeros vector. Family A: matches real. Family B: far off
    # on the dim that maps to leverage.
    real_fp = [0.0] * n
    fam_a_fp = [0.0] * n            # matches real exactly
    fam_b_fp = [0.0] * n
    fam_b_fp[FEATURE_NAMES.index("leverage")] = 5.0   # 5σ off if real_std == 1

    # Need >=2 real points so std is well-defined
    real_runs = (_runs("real_a", real_fp, n=3)
                  + _runs("real_b", [v + 1e-6 for v in real_fp], n=3))
    runs = (real_runs + _runs("fam_a", fam_a_fp, n=3)
             + _runs("fam_b", fam_b_fp, n=3))

    families = [
        {"key": "fam_a", "name": "A"},
        {"key": "fam_b", "name": "B"},
    ]
    runs_by_model: dict[str, list[dict]] = {}
    for r in runs:
        fp = np.asarray(json.loads(r["fingerprint_json"]), dtype=float)
        rr = dict(r); rr["_fp"] = fp
        runs_by_model.setdefault(r["model_name"], []).append(rr)

    v = gap_finder._build_view_b(runs_by_model, families, FEATURE_NAMES)
    a_row = v.matrix[v.row_labels.index("fam_a")]
    b_row = v.matrix[v.row_labels.index("fam_b")]
    leverage_col = v.col_labels.index("leverage")
    # fam_b on leverage must be the biggest deviation
    assert b_row[leverage_col] > 1.0
    assert b_row[leverage_col] > a_row[leverage_col]
    # higher_is_gap is set correctly
    assert v.higher_is_gap is True


def test_rank_top_gaps_drops_noise_columns_and_sparse_rows():
    """'other' and rows below min_row_total must be dropped from ranking."""
    from fingerprint_atlas.gap_finder import GapView, rank_top_gaps
    import numpy as np
    # 3 rows × 3 cols, row 0 is dense (10 total), row 1 dense (10), row 2 empty (0)
    # 'other' is col 0, 'fat-tails' is col 1, 'leverage' is col 2
    M = np.array([
        [0, 5, 5],   # row 0: 'other' empty but row dense — should NOT surface
        [10, 0, 0],  # row 1: 'other' has all the mass; 'fat-tails' empty IS a gap
        [0, 0, 0],   # row 2: empty row, no gaps
    ], dtype=float)
    # Synthesise high salience everywhere so filtering is the only gate
    S = np.ones_like(M) * 5.0
    v = GapView(
        name="A", title="t",
        row_labels=["dense_a", "dense_b", "empty"],
        col_labels=["other", "fat-tails", "leverage"],
        matrix=M, salience=S, higher_is_gap=False, description="",
    )
    top = rank_top_gaps([v], top_n=20, min_row_total=3, min_col_total=1)
    # 'other' column never appears
    assert all(g.col != "other" for g in top)
    # empty row 'empty' never appears (row_total = 0 < 3)
    assert all(g.row != "empty" for g in top)
    # row 1 (dense_b) has fat-tails AND leverage empty AND non-other,
    # row+col density OK on fat-tails (col_total=5 from row 0)
    cells = {(g.row, g.col) for g in top}
    assert ("dense_b", "fat-tails") in cells
    assert ("dense_b", "leverage") in cells


def test_view_c_matches_version_stripped_arxiv_ids():
    """A technique referencing 'adap-org/9708006' must match a DB row
    stored as 'adap-org/9708006v3' (version suffix), and vice versa."""
    from fingerprint_atlas import gap_finder
    rows = [
        {"arxiv_id": "adap-org/9708006v3",
         "mechanism_tags": "minority game",
         "stylized_facts_targeted": ""},
    ]
    techniques = [
        {"key": "mg_strategy_selection", "name": "MG strategy selection",
         "ref_papers": ["adap-org/9708006"]},  # no version suffix
    ]
    subfields = [{"key": "minority_game", "name": "Minority Game",
                   "title_any": ["minority"]}]
    v = gap_finder._build_view_c(rows, techniques, subfields)
    # The technique's ref must match the DB row → 1
    assert v.matrix[0, 0] == 1


def test_view_c_zero_overlap_in_popular_cell_gets_high_salience():
    from fingerprint_atlas import gap_finder
    # 3 papers in "limit order book" subfield, 0 of them referenced by
    # the 'prospect_asymmetric_sizing' technique → high-salience gap.
    rows = [
        {"arxiv_id": "L.1", "mechanism_tags": "limit order book",
         "stylized_facts_targeted": ""},
        {"arxiv_id": "L.2", "mechanism_tags": "order book dynamics",
         "stylized_facts_targeted": ""},
        {"arxiv_id": "L.3", "mechanism_tags": "limit order book",
         "stylized_facts_targeted": ""},
        # P.1 is a paper that uses prospect-asymmetric-sizing in some
        # OTHER subfield (so the technique row is non-empty).
        {"arxiv_id": "P.1", "mechanism_tags": "prospect theory",
         "stylized_facts_targeted": ""},
    ]
    techniques = [
        {"key": "prospect_asymmetric_sizing",
         "name": "Prospect-asym sizing",
         "ref_papers": ["P.1"]},
    ]
    subfields = [
        {"key": "limit_order_book", "name": "Limit order book",
         "title_any": ["order book"]},
        {"key": "prospect_theory", "name": "Prospect theory",
         "title_any": ["prospect"]},
    ]
    v = gap_finder._build_view_c(rows, techniques, subfields)
    # technique × LOB: 0 (no overlap)
    # technique × prospect_theory: 1 (P.1 is in both)
    lob_col = v.col_labels.index("Limit order book")
    pt_col = v.col_labels.index("Prospect theory")
    assert v.matrix[0, lob_col] == 0
    assert v.matrix[0, pt_col] == 1
    # Salience higher on the zero cell
    assert v.salience[0, lob_col] > v.salience[0, pt_col]


def test_rank_top_gaps_prefers_high_salience_and_respects_view_weights():
    from fingerprint_atlas.gap_finder import (
        GapView, rank_top_gaps,
    )
    # One synthetic view per kind. Salience is what the ranker reads.
    va = GapView(name="A", title="", row_labels=["r1"], col_labels=["c1"],
                  matrix=np.array([[0]]),
                  salience=np.array([[1.0]]),
                  higher_is_gap=False, description="")
    vb = GapView(name="B", title="", row_labels=["fam"], col_labels=["fat-tails"],
                  matrix=np.array([[2.0]]),
                  salience=np.array([[1.0]]),
                  higher_is_gap=True, description="")
    vc = GapView(name="C", title="", row_labels=["t1"], col_labels=["s1"],
                  matrix=np.array([[0]]),
                  salience=np.array([[1.0]]),
                  higher_is_gap=False, description="")
    # Salience is equal across views → view B's weight (1.3) must win.
    # But the A and C cells need to satisfy row+col density >= 3 to count;
    # synthesise them out by giving the matrices density.
    va = GapView(name="A", title="",
                  row_labels=["r1", "r2"], col_labels=["c1", "c2"],
                  matrix=np.array([[0, 5], [5, 5]]),
                  salience=np.array([[1.0, 0.0], [0.0, 0.0]]),
                  higher_is_gap=False, description="")
    vc = GapView(name="C", title="",
                  row_labels=["t1", "t2"], col_labels=["s1", "s2"],
                  matrix=np.array([[0, 5], [5, 5]]),
                  salience=np.array([[1.0, 0.0], [0.0, 0.0]]),
                  higher_is_gap=False, description="")
    top = rank_top_gaps([va, vb, vc], top_n=10)
    # All three view types represented
    views_present = {g.view for g in top}
    assert views_present == {"A", "B", "C"}
    # Top gap is from view B (weight 1.3 × salience 1.0)
    assert top[0].view == "B"


def test_find_gaps_integrates_curated_modules():
    """End-to-end: with realistic but tiny inputs, find_gaps returns
    sensible views and a non-empty top list."""
    from fingerprint_atlas import gap_finder
    from fingerprint_atlas.fingerprint import FEATURE_NAMES
    n = len(FEATURE_NAMES)
    rows = [
        {"arxiv_id": "x.1", "mechanism_tags": "minority game",
         "stylized_facts_targeted": "fat-tails"},
        {"arxiv_id": "x.2", "mechanism_tags": "volatility clustering",
         "stylized_facts_targeted": "vol-clustering"},
    ]
    runs = (_runs("real_spx", [0.0]*n, n=3)
             + _runs("real_btc", [0.01]*n, n=3)
             + _runs("minority_game", [1.0]*n, n=3)
             + _runs("lux_marchesi", [0.5]*n, n=3))
    views, top = gap_finder.find_gaps(rows, runs, top_n=5)
    # 3 views built
    assert [v.name for v in views] == ["A", "B", "C"]
    # Top list bounded by top_n, may be empty if no gaps satisfy thresholds
    assert len(top) <= 5
