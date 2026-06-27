"""Tests for the inverse-ABM nearest-neighbour query + distance matrix.

Covers:
  1. _load_returns_from_csv handles single-column, header, and date,value forms.
  2. nearest_abms_to_target works for run-id, model-name, and raw-returns targets.
  3. ABM-only filter excludes synthetic/real candidates.
  4. compute_real_vs_abm_distance_matrix returns shape (n_real, n_abm_families).
  5. plot_real_vs_abm_heatmap produces a PNG and the argmin summary.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from fingerprint_atlas.adapters import build_model, series_for_fingerprint
from fingerprint_atlas.db import ensure_runs_schema, insert_run
from fingerprint_atlas.fingerprint import fingerprint
from fingerprint_atlas.inverse_abm import (
    _load_returns_from_csv, compute_real_vs_abm_distance_matrix,
    nearest_abms_to_target, plot_real_vs_abm_heatmap,
)


def _populate_minimal_db(tmpdir: str) -> str:
    """Build a tmp DB with two ABM families + two 'real' rows."""
    db = os.path.join(tmpdir, "t.db")
    ensure_runs_schema(db)
    # ABM rows: a few SG runs + a few CB runs
    rng_seed = 100
    for name, params in [
        ("speculation_game", dict(N=80, M=2, S=2, T=400)),
        ("speculation_game", dict(N=80, M=3, S=2, T=400)),
        ("cont_bouchaud", dict(N=500, c=0.9, T=400, report_every=10**9)),
        ("cont_bouchaud", dict(N=500, c=0.6, T=400, report_every=10**9)),
    ]:
        m = build_model(name, params)
        res = m.run(seed=rng_seed)
        rng_seed += 1
        series, kind = series_for_fingerprint(name, res)
        fp = fingerprint(series, compute_hill=(kind == "returns"))
        insert_run(
            db, model_name=name, params=params, seed=rng_seed,
            fingerprint_vec=fp, series_kind=kind,
            series_length=int(len(series)),
            provenance={"git_commit": "test"},
            created_at="2026-06-27T00:00:00Z", origin="abm",
        )
    # Two "real" rows: synthetic-but-plausible return series
    rng = np.random.default_rng(0)
    for label in ("real_test_a", "real_test_b"):
        ret = rng.standard_normal(800) * 0.012
        fp = fingerprint(ret, compute_hill=True)
        insert_run(
            db, model_name=label, params={"symbol": label},
            seed=0, fingerprint_vec=fp, series_kind="returns",
            series_length=800,
            provenance={"git_commit": "test"},
            created_at="2026-06-27T00:00:00Z", origin="real",
        )
    return db


# ---- _load_returns_from_csv ----------------------------------------------

def test_load_returns_from_csv_single_column(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("0.01\n-0.005\n0.003\n")
    arr = _load_returns_from_csv(str(path))
    assert arr.tolist() == [0.01, -0.005, 0.003]


def test_load_returns_from_csv_with_header(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("return\n0.01\n-0.005\n")
    arr = _load_returns_from_csv(str(path))
    assert arr.tolist() == [0.01, -0.005]


def test_load_returns_from_csv_date_value_columns(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("date,return\n2024-01-01,0.01\n2024-01-02,-0.005\n")
    arr = _load_returns_from_csv(str(path))
    assert arr.tolist() == [0.01, -0.005]


# ---- nearest_abms_to_target ----------------------------------------------

def test_nearest_by_run_id_excludes_self():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        result = nearest_abms_to_target(db, target_run_id=1, k=3, abm_only=True)
        # k=3 returns 3 matches and none of them is run_id=1 (self)
        assert len(result["matches"]) == 3
        assert all(m["run_id"] != 1 for m in result["matches"])
        # distances must be non-decreasing
        ds = [m["distance"] for m in result["matches"]]
        assert ds == sorted(ds)


def test_nearest_by_returns_finds_some_neighbours():
    """Feeding an external returns array should not crash and should
    produce k matches sorted by distance."""
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        rng = np.random.default_rng(7)
        external = rng.standard_normal(500) * 0.01
        result = nearest_abms_to_target(db, returns=external, k=2, abm_only=True)
        assert result["target_label"].startswith("<external")
        assert len(result["matches"]) == 2
        # all matches must be ABMs (abm_only)
        assert all(m["origin"] == "abm" for m in result["matches"])


def test_nearest_by_model_name_uses_centroid():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        result = nearest_abms_to_target(
            db, target_model_name="speculation_game", k=3, abm_only=True,
        )
        assert "centroid" in result["target_label"]
        assert len(result["matches"]) == 3


def test_nearest_include_real_synthetic_widens_search():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        narrow = nearest_abms_to_target(
            db, target_model_name="speculation_game", k=10, abm_only=True,
        )
        wide = nearest_abms_to_target(
            db, target_model_name="speculation_game", k=10, abm_only=False,
        )
        # wide must have at least as many candidates as narrow
        assert wide["n_candidates_searched"] >= narrow["n_candidates_searched"]


def test_nearest_unknown_target_raises():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        with pytest.raises(KeyError):
            nearest_abms_to_target(db, target_model_name="not_a_model")
        with pytest.raises(KeyError):
            nearest_abms_to_target(db, target_run_id=9999)


def test_nearest_no_source_raises():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        with pytest.raises(ValueError):
            nearest_abms_to_target(db, k=3)


# ---- distance matrix + heatmap -------------------------------------------

def test_real_vs_abm_matrix_shape_and_argmin():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        data = compute_real_vs_abm_distance_matrix(db)
        # 2 real rows × 2 abm families
        assert data["matrix"].shape == (2, 2)
        assert data["real_labels"] == ["real_test_a", "real_test_b"]
        assert set(data["abm_families"]) == {"speculation_game", "cont_bouchaud"}
        assert len(data["argmin_per_real"]) == 2
        for entry in data["argmin_per_real"]:
            assert entry["nearest_abm_family"] in {"speculation_game", "cont_bouchaud"}


def test_heatmap_writes_png():
    with tempfile.TemporaryDirectory() as td:
        db = _populate_minimal_db(td)
        out = os.path.join(td, "h.png")
        info = plot_real_vs_abm_heatmap(db, out)
        assert os.path.exists(out)
        assert info["matrix_shape"] == [2, 2]
        assert len(info["argmin_per_real"]) == 2


def test_heatmap_raises_when_no_real_rows():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        ensure_runs_schema(db)
        # only one ABM row, no real rows
        m = build_model("speculation_game", dict(N=80, M=2, S=2, T=400))
        res = m.run(seed=1)
        series, kind = series_for_fingerprint("speculation_game", res)
        fp = fingerprint(series, compute_hill=True)
        insert_run(db, model_name="speculation_game", params={},
                   seed=1, fingerprint_vec=fp, series_kind=kind,
                   series_length=len(series),
                   provenance={"git_commit": "test"},
                   created_at="2026-06-27T00:00:00Z", origin="abm")
        with pytest.raises(RuntimeError):
            compute_real_vs_abm_distance_matrix(db)
