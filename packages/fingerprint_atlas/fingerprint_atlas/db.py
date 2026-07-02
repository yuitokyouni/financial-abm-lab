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
    fingerprint_json TEXT NOT NULL,        -- capped feature vector (FEATURE_NAMES order)
    series_kind     TEXT NOT NULL,         -- 'returns' | 'attendance_excess'
    series_length   INTEGER NOT NULL,
    provenance_json TEXT NOT NULL,         -- {git_commit, code_hash, timestamp, host}
    created_at      TEXT NOT NULL,
    hill_raw        REAL,                  -- uncapped Hill α (diagnostic)
    origin          TEXT NOT NULL DEFAULT 'abm',  -- 'abm' | 'synthetic' | 'real'
    preference_label        REAL,          -- user Likert score (e.g. -2..+2); NULL = unlabeled
    preference_labeled_at   TEXT           -- ISO-8601 timestamp of the labelling event
);
"""

#: Indexes are created AFTER the ALTER TABLE migration so that an index on a
#: column we are about to add isn't requested before the column exists.
_RUNS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model_name)",
    "CREATE INDEX IF NOT EXISTS idx_runs_origin ON runs(origin)",
    "CREATE INDEX IF NOT EXISTS idx_runs_pref ON runs(preference_label)",
]


def _column_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def ensure_runs_schema(db_path: str) -> None:
    """Create the `runs` table if absent. Idempotent; leaves `techniques` alone.

    Additive migration: any column listed in the schema but missing on an
    existing `runs` table is added via ALTER TABLE. Existing rows get NULL
    for new nullable columns (or the declared DEFAULT for NOT NULL ones).
    """
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(RUNS_SCHEMA)
        if not _column_exists(con, "runs", "hill_raw"):
            con.execute("ALTER TABLE runs ADD COLUMN hill_raw REAL")
        if not _column_exists(con, "runs", "origin"):
            con.execute("ALTER TABLE runs ADD COLUMN origin TEXT NOT NULL DEFAULT 'abm'")
        if not _column_exists(con, "runs", "preference_label"):
            con.execute("ALTER TABLE runs ADD COLUMN preference_label REAL")
        if not _column_exists(con, "runs", "preference_labeled_at"):
            con.execute("ALTER TABLE runs ADD COLUMN preference_labeled_at TEXT")
        for stmt in _RUNS_INDEXES:
            con.execute(stmt)
        con.commit()


def update_preference(db_path: str, run_id: int, label: float,
                      labeled_at: str | None = None) -> None:
    """Set `preference_label` (and timestamp) on one row. Idempotent overwrite."""
    import datetime as _dt
    if labeled_at is None:
        labeled_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "UPDATE runs SET preference_label = ?, preference_labeled_at = ? WHERE id = ?",
            (float(label), labeled_at, int(run_id)),
        )
        if cur.rowcount == 0:
            raise KeyError(f"no row with id={run_id}")
        con.commit()


def clear_preference(db_path: str, run_id: int) -> None:
    """Reset a row's preference label to NULL (unlabeled)."""
    with sqlite3.connect(db_path) as con:
        con.execute(
            "UPDATE runs SET preference_label = NULL, preference_labeled_at = NULL "
            "WHERE id = ?", (int(run_id),)
        )
        con.commit()


# ============================================================================
# proposals — LLM-generated ABM suggestions, lifecycle: proposed → executed
# ============================================================================

PROPOSALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id                          INTEGER PRIMARY KEY,
    proposal_type               TEXT NOT NULL,        -- 'param_sweep' for now; later: 'mechanism_combo' etc.
    target_model                TEXT NOT NULL,        -- one of REGISTRY keys, or 'new' for novel methods
    params_json                 TEXT NOT NULL,        -- the concrete params to run
    rationale                   TEXT NOT NULL,        -- LLM's natural-language reasoning
    predicted_fingerprint_json  TEXT,                 -- LLM's prediction of the resulting fingerprint
    predicted_novelty_distance  REAL,                 -- LLM's estimate of distance to nearest existing run
    references_json             TEXT NOT NULL DEFAULT '[]',
    llm_model                   TEXT NOT NULL,        -- e.g. 'llama-3.3-70b-versatile'
    status                      TEXT NOT NULL DEFAULT 'proposed',  -- 'proposed' | 'approved' | 'rejected' | 'executed'
    executed_run_id             INTEGER,              -- runs.id once executed
    actual_fingerprint_json     TEXT,                 -- post-execute reality
    actual_novelty_distance     REAL,                 -- post-execute reality
    prediction_error            REAL,                 -- L2 distance between predicted and actual fp (standardised)
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL,
    FOREIGN KEY (executed_run_id) REFERENCES runs(id)
);
"""

_PROPOSALS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status)",
    "CREATE INDEX IF NOT EXISTS idx_proposals_target ON proposals(target_model)",
]


def ensure_proposals_schema(db_path: str) -> None:
    """Idempotent: create `proposals` table + indexes."""
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(PROPOSALS_SCHEMA)
        for stmt in _PROPOSALS_INDEXES:
            con.execute(stmt)
        con.commit()


def insert_proposal(
    db_path: str, *,
    proposal_type: str,
    target_model: str,
    params: dict[str, Any],
    rationale: str,
    predicted_fingerprint: dict[str, float] | None,
    predicted_novelty_distance: float | None,
    references: list[str],
    llm_model: str,
) -> int:
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    pf_json = json.dumps(predicted_fingerprint) if predicted_fingerprint else None
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO proposals "
            "(proposal_type, target_model, params_json, rationale, "
            "predicted_fingerprint_json, predicted_novelty_distance, "
            "references_json, llm_model, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal_type, target_model, json.dumps(params, sort_keys=True, default=_json_default),
             rationale, pf_json,
             None if predicted_novelty_distance is None else float(predicted_novelty_distance),
             json.dumps(references), llm_model, now, now),
        )
        return int(cur.lastrowid)


def update_proposal_status(db_path: str, proposal_id: int, status: str,
                           executed_run_id: int | None = None,
                           actual_fingerprint: dict[str, float] | None = None,
                           actual_novelty_distance: float | None = None,
                           prediction_error: float | None = None) -> None:
    """Set status and optionally the post-execute measurement fields."""
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    af_json = json.dumps(actual_fingerprint) if actual_fingerprint else None
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "UPDATE proposals SET status = ?, updated_at = ?, "
            "executed_run_id = COALESCE(?, executed_run_id), "
            "actual_fingerprint_json = COALESCE(?, actual_fingerprint_json), "
            "actual_novelty_distance = COALESCE(?, actual_novelty_distance), "
            "prediction_error = COALESCE(?, prediction_error) "
            "WHERE id = ?",
            (status, now, executed_run_id, af_json,
             None if actual_novelty_distance is None else float(actual_novelty_distance),
             None if prediction_error is None else float(prediction_error),
             int(proposal_id)),
        )
        if cur.rowcount == 0:
            raise KeyError(f"no proposal with id={proposal_id}")
        con.commit()


# ============================================================================
# literature_methods — arxiv-ingested papers, structured by LLM extraction
# ============================================================================

LITERATURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS literature_methods (
    id                        INTEGER PRIMARY KEY,
    arxiv_id                  TEXT NOT NULL UNIQUE,    -- e.g. '2412.01234' or '2412.01234v2'
    title                     TEXT NOT NULL,
    authors                   TEXT NOT NULL,           -- comma-separated
    year                      INTEGER NOT NULL,
    published_date            TEXT NOT NULL,           -- ISO-8601
    primary_category          TEXT,
    abstract                  TEXT NOT NULL,
    -- LLM-extracted structured fields
    mechanism_summary         TEXT,                    -- 1-3 sentence what it proposes
    mechanism_tags            TEXT NOT NULL DEFAULT '',  -- comma-separated free tags
    stylized_facts_targeted   TEXT NOT NULL DEFAULT '',  -- comma-separated
    novelty_signal            TEXT,                    -- 1 sentence claimed-novelty
    relevance_score           REAL,                    -- 0-1 LLM-estimated relevance to financial-ABM atlas
    extracted_by_model        TEXT,                    -- groq llm id, NULL if not yet extracted
    extraction_attempts       INTEGER NOT NULL DEFAULT 0,
    -- user annotations (free-form, like methods)
    user_notes                TEXT NOT NULL DEFAULT '',
    user_tags                 TEXT NOT NULL DEFAULT '',
    -- provenance
    ingested_at               TEXT NOT NULL,
    updated_at                TEXT NOT NULL
);
"""

_LITERATURE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_lit_year ON literature_methods(year)",
    "CREATE INDEX IF NOT EXISTS idx_lit_cat ON literature_methods(primary_category)",
    "CREATE INDEX IF NOT EXISTS idx_lit_rel ON literature_methods(relevance_score)",
]


def ensure_literature_schema(db_path: str) -> None:
    """Idempotent literature_methods table create."""
    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.executescript(LITERATURE_SCHEMA)
        for stmt in _LITERATURE_INDEXES:
            con.execute(stmt)
        con.commit()


def upsert_literature_metadata(
    db_path: str, *,
    arxiv_id: str, title: str, authors: str, year: int,
    published_date: str, primary_category: str | None, abstract: str,
) -> int:
    """Insert a paper's raw metadata if absent; return the row id.

    Idempotent: re-ingesting the same arxiv_id is a no-op. LLM extraction is
    a separate step (`update_literature_extraction`) so we don't lose
    extraction results on a metadata refresh.
    """
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    with sqlite3.connect(db_path) as con:
        existing = con.execute(
            "SELECT id FROM literature_methods WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        if existing:
            return int(existing[0])
        cur = con.execute(
            "INSERT INTO literature_methods (arxiv_id, title, authors, year, "
            "published_date, primary_category, abstract, ingested_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (arxiv_id, title, authors, int(year), published_date,
             primary_category, abstract, now, now),
        )
        return int(cur.lastrowid)


def update_literature_extraction(
    db_path: str, arxiv_id: str, *,
    mechanism_summary: str | None,
    mechanism_tags: list[str],
    stylized_facts_targeted: list[str],
    novelty_signal: str | None,
    relevance_score: float | None,
    extracted_by_model: str,
) -> None:
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "UPDATE literature_methods SET "
            "mechanism_summary = ?, mechanism_tags = ?, "
            "stylized_facts_targeted = ?, novelty_signal = ?, "
            "relevance_score = ?, extracted_by_model = ?, "
            "extraction_attempts = extraction_attempts + 1, updated_at = ? "
            "WHERE arxiv_id = ?",
            (mechanism_summary, ", ".join(mechanism_tags),
             ", ".join(stylized_facts_targeted), novelty_signal,
             None if relevance_score is None else float(relevance_score),
             extracted_by_model, now, arxiv_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"no literature row with arxiv_id={arxiv_id}")
        con.commit()


def load_literature(db_path: str, *, min_relevance: float | None = None,
                    tag: str | None = None, max_results: int | None = None
                    ) -> list[dict[str, Any]]:
    sql = ("SELECT id, arxiv_id, title, authors, year, published_date, "
           "primary_category, abstract, mechanism_summary, mechanism_tags, "
           "stylized_facts_targeted, novelty_signal, relevance_score, "
           "extracted_by_model, extraction_attempts, user_notes, user_tags, "
           "ingested_at, updated_at FROM literature_methods")
    where: list[str] = []
    args: list[Any] = []
    if min_relevance is not None:
        where.append("relevance_score >= ?")
        args.append(float(min_relevance))
    if tag is not None:
        # Tags are stored as ", "-joined strings; normalise both sides by
        # stripping spaces so the LIKE match works regardless of leading
        # spaces around commas.
        where.append("REPLACE(',' || mechanism_tags || ',', ' ', '') LIKE ?")
        args.append(f"%,{tag.replace(' ', '')},%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(relevance_score, -1) DESC, year DESC, id DESC"
    if max_results is not None:
        sql += " LIMIT ?"
        args.append(int(max_results))
    with sqlite3.connect(db_path) as con:
        rows = con.execute(sql, tuple(args)).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0], "arxiv_id": r[1], "title": r[2], "authors": r[3],
            "year": r[4], "published_date": r[5], "primary_category": r[6],
            "abstract": r[7], "mechanism_summary": r[8],
            "mechanism_tags": [t.strip() for t in (r[9] or "").split(",") if t.strip()],
            "stylized_facts_targeted": [t.strip() for t in (r[10] or "").split(",") if t.strip()],
            "novelty_signal": r[11], "relevance_score": r[12],
            "extracted_by_model": r[13], "extraction_attempts": r[14],
            "user_notes": r[15] or "", "user_tags": r[16] or "",
            "ingested_at": r[17], "updated_at": r[18],
        })
    return out


def load_proposals(db_path: str, status: str | None = None) -> list[dict[str, Any]]:
    sql = ("SELECT id, proposal_type, target_model, params_json, rationale, "
           "predicted_fingerprint_json, predicted_novelty_distance, references_json, "
           "llm_model, status, executed_run_id, actual_fingerprint_json, "
           "actual_novelty_distance, prediction_error, created_at, updated_at "
           "FROM proposals")
    args: tuple = ()
    if status is not None:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY id"
    with sqlite3.connect(db_path) as con:
        rows = con.execute(sql, args).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r[0], "proposal_type": r[1], "target_model": r[2],
            "params": json.loads(r[3]), "rationale": r[4],
            "predicted_fingerprint": json.loads(r[5]) if r[5] else None,
            "predicted_novelty_distance": r[6],
            "references": json.loads(r[7] or "[]"),
            "llm_model": r[8], "status": r[9],
            "executed_run_id": r[10],
            "actual_fingerprint": json.loads(r[11]) if r[11] else None,
            "actual_novelty_distance": r[12],
            "prediction_error": r[13],
            "created_at": r[14], "updated_at": r[15],
        })
    return out


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
              origin: str | None = None,
              labeled: bool | None = None) -> list[dict[str, Any]]:
    """Read back all runs (optionally filtered). Parses JSON columns.

    labeled : if True, only rows with a non-NULL preference_label; if False,
              only unlabeled rows; None = no filter on labelling.
    """
    sql = ("SELECT id, model_name, params_json, seed, fingerprint_json, "
           "series_kind, series_length, provenance_json, created_at, hill_raw, origin, "
           "preference_label, preference_labeled_at FROM runs")
    where: list[str] = []
    args: list[Any] = []
    if model_name is not None:
        where.append("model_name = ?")
        args.append(model_name)
    if origin is not None:
        where.append("origin = ?")
        args.append(origin)
    if labeled is True:
        where.append("preference_label IS NOT NULL")
    elif labeled is False:
        where.append("preference_label IS NULL")
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
            "preference_label": r[11],
            "preference_labeled_at": r[12],
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
