"""fingerprint_atlas smoke tests.

Goal: every REGISTRY model produces a finite 6-vector under the smallest
possible LHS sample. Catches MODEL_BOUNDS / series_for_fingerprint regressions
before the long populate run.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

from abm_models import REGISTRY
from fingerprint_atlas import (
    FEATURE_NAMES,
    MODEL_BOUNDS,
    build_model,
    distance_matrix,
    ensure_runs_schema,
    fingerprint,
    insert_run,
    load_runs,
    sample_params_lhs,
    series_for_fingerprint,
    standardize,
)
from fingerprint_atlas.atlas import validation_gate


def test_every_registry_model_runs_and_fingerprints():
    rng = np.random.default_rng(0)
    bad: list[tuple[str, str]] = []
    for name in REGISTRY:
        params = sample_params_lhs(name, 2, rng)[0]
        model = build_model(name, params)
        result = model.run(seed=42)
        series, kind = series_for_fingerprint(name, result)
        fp = fingerprint(series)
        if not (np.isfinite(fp).sum() >= 4 and len(fp) == len(FEATURE_NAMES)):
            bad.append((name, f"fp={fp}, kind={kind}, len={len(series)}"))
    assert not bad, "models with broken fingerprints: " + repr(bad)


def test_round_trip_through_db():
    rng = np.random.default_rng(1)
    name = "cont_bouchaud"
    params = sample_params_lhs(name, 2, rng)[0]
    model = build_model(name, params)
    res = model.run(seed=7)
    series, kind = series_for_fingerprint(name, res)
    fp = fingerprint(series)

    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "test.db")
        ensure_runs_schema(db)
        rid = insert_run(db, model_name=name, params=params, seed=7,
                         fingerprint_vec=fp, series_kind=kind,
                         series_length=len(series),
                         provenance={"git_commit": "test"},
                         created_at="2026-06-27T00:00:00Z")
        rows = load_runs(db)
    assert len(rows) == 1 and rows[0]["id"] == rid
    assert rows[0]["model_name"] == name
    np.testing.assert_allclose(rows[0]["fingerprint"], fp, equal_nan=True)


def test_validation_gate_recognises_separation():
    """A toy population: clearly different features by 'model' => gate.ok == True."""
    rng = np.random.default_rng(2)
    rows = []
    # model A: tight volatility, thin tail
    for i in range(8):
        r = rng.standard_normal(2000) * 0.01
        fp = fingerprint(r)
        rows.append({"model_name": "A", "fingerprint": fp})
    # model B: fat-tail injection via student-t
    for i in range(8):
        r = rng.standard_t(df=3, size=2000) * 0.01
        fp = fingerprint(r)
        rows.append({"model_name": "B", "fingerprint": fp})
    gate = validation_gate(rows)
    assert gate["ok"] is True
    assert gate["separation_ratio"] > 1.0
    assert gate["silhouette_macro"] > 0


def test_distance_matrix_shape_and_symmetry():
    fps_std, _, _ = standardize(np.random.default_rng(3).standard_normal((10, 6)))
    D = distance_matrix(fps_std)
    assert D.shape == (10, 10)
    np.testing.assert_allclose(D, D.T)
    np.testing.assert_allclose(np.diag(D), 0.0)


def test_bounds_cover_registry():
    assert set(MODEL_BOUNDS) == set(REGISTRY)
