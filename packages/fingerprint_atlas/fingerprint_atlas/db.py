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
    fingerprint_json TEXT NOT NULL,        -- *capped* 6-vector (FEATURE_NAMES order)
    series_kind     TEXT NOT NULL,         -- 'returns' | 'attendance_excess'
    series_length   INTEGER NOT NULL,
    provenance_json TEXT NOT NULL,         -- {git_commit, code_hash, timestamp, host}
    created_at      TEXT NOT NULL,
    hill_raw        REAL,                  -- uncapped Hill α (diagnostic)
    origin          TEXT NOT NULL DEFAULT 'abm'  -- 'abm' | 'synthetic' | 'real'
);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_name);
CREATE INDEX IF NOT EXISTS idx_runs_origin ON runs(origin);
"""


def _column_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def ensure_runs_schema(db_path: str) -> None:
    """Create the `runs` table if absent. Idempotent; leaves `techniques` alone.

    Also performs additive migration: if `runs` exists but lacks `hill_raw` /
    `origin`, ALTER TABLE adds them. Existing rows get NULL / 'abm' respectively.
    """
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(RUNS_SCHEMA)
        if not _column_exists(con, "runs", "hill_raw"):
            con.execute("ALTER TABLE runs ADD COLUMN hill_raw REAL")
        if not _column_exists(con, "runs", "origin"):
            con.execute("ALTER TABLE runs ADD COLUMN origin TEXT NOT NULL DEFAULT 'abm'")
        con.commit()


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
    hill_raw: float | None = None,
    origin: str = "abm",
) -> int:
    """Insert one run row. Returns its rowid."""
    fp = [None if not np.isfinite(v) else float(v) for v in np.asarray(fingerprint_vec).tolist()]
    hr = (None if hill_raw is None or not np.isfinite(hill_raw) else float(hill_raw))
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO runs (model_name, params_json, seed, fingerprint_json, "
            "series_kind, series_length, provenance_json, created_at, hill_raw, origin) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                model_name,
                json.dumps(params, default=_json_default, sort_keys=True),
                int(seed),
                json.dumps(fp),
                series_kind,
                int(series_length),
                json.dumps(provenance, default=_json_default, sort_keys=True),
                created_at,
                hr,
                origin,
            ),
        )
        return int(cur.lastrowid)


def load_runs(db_path: str, model_name: str | None = None,
              origin: str | None = None) -> list[dict[str, Any]]:
    """Read back all runs (optionally filtered). Parses JSON columns."""
    sql = ("SELECT id, model_name, params_json, seed, fingerprint_json, "
           "series_kind, series_length, provenance_json, created_at, hill_raw, origin FROM runs")
    where: list[str] = []
    args: list[Any] = []
    if model_name is not None:
        where.append("model_name = ?"); args.append(model_name)
    if origin is not None:
        where.append("origin = ?"); args.append(origin)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id"
    with sqlite3.connect(db_path) as con:
        rows = con.execute(sql, tuple(args)).fetchall()
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
            "hill_raw": r[9],
            "origin": r[10],
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
