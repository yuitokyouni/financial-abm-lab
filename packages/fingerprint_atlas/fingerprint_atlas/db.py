"""db — the `runs` table in the knowhow SQLite DB (test/knowhow/abm_knowhow.db).

Schema extension of the seed `techniques` table (which is left untouched). The
`runs` table is what makes layer 3 of the seed plan real: every ABM run lands
here as a row whose `fingerprint_json` is the 6-vector queried for atlas /
novelty / inverse-ABM.

We deliberately do NOT migrate the existing `techniques` table — `ensure_runs_schema`
is purely additive and idempotent so the same DB stays the single source.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Iterable

import numpy as np

RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY,
    model_name      TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    seed            INTEGER NOT NULL,
    fingerprint_json TEXT NOT NULL,        -- raw 6-vector (FEATURE_NAMES order)
    series_kind     TEXT NOT NULL,         -- 'returns' | 'attendance_excess'
    series_length   INTEGER NOT NULL,
    provenance_json TEXT NOT NULL,         -- {git_commit, code_hash, timestamp, host}
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_name);
"""


def ensure_runs_schema(db_path: str) -> None:
    """Create the `runs` table if absent. Idempotent; leaves `techniques` alone."""
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(RUNS_SCHEMA)


def insert_run(
    db_path: str,
    *,
    model_name: str,
    params: dict[str, Any],
    seed: int,
    fingerprint_vec: np.ndarray,
    series_kind: str,
    series_length: int,
    provenance: dict[str, Any],
    created_at: str,
) -> int:
    """Insert one run row. Returns its rowid."""
    fp = [None if not np.isfinite(v) else float(v) for v in np.asarray(fingerprint_vec).tolist()]
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO runs (model_name, params_json, seed, fingerprint_json, "
            "series_kind, series_length, provenance_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                model_name,
                json.dumps(params, default=_json_default, sort_keys=True),
                int(seed),
                json.dumps(fp),
                series_kind,
                int(series_length),
                json.dumps(provenance, default=_json_default, sort_keys=True),
                created_at,
            ),
        )
        return int(cur.lastrowid)


def load_runs(db_path: str, model_name: str | None = None) -> list[dict[str, Any]]:
    """Read back all runs (optionally filtered by model). Parses JSON columns."""
    sql = ("SELECT id, model_name, params_json, seed, fingerprint_json, "
           "series_kind, series_length, provenance_json, created_at FROM runs")
    args: tuple = ()
    if model_name is not None:
        sql += " WHERE model_name = ?"
        args = (model_name,)
    sql += " ORDER BY id"
    with sqlite3.connect(db_path) as con:
        rows = con.execute(sql, args).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r[0],
            "model_name": r[1],
            "params": json.loads(r[2]),
            "seed": r[3],
            "fingerprint": np.array(json.loads(r[4]), dtype=float),
            "series_kind": r[5],
            "series_length": r[6],
            "provenance": json.loads(r[7]),
            "created_at": r[8],
        })
    return out


def _json_default(o: Any) -> Any:
    """JSON fallback for numpy scalars and dataclasses we don't unpack."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def collect_population(rows: Iterable[dict[str, Any]]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Stack fingerprints from rows; drop rows whose fingerprint has NaN.

    Returns (fps_raw, kept_rows) — same length, aligned.
    """
    fps: list[np.ndarray] = []
    kept: list[dict[str, Any]] = []
    for r in rows:
        fp = np.asarray(r["fingerprint"], dtype=float)
        if np.all(np.isfinite(fp)):
            fps.append(fp)
            kept.append(r)
    if not fps:
        return np.zeros((0, 0)), []
    return np.vstack(fps), kept
