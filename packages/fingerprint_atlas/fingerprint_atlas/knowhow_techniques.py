"""knowhow_techniques — thin reader over the seed `techniques` table.

The 15-technique knowhow DB lives at test/knowhow/abm_knowhow.db (built by
test/knowhow/seed_knowhow.py). This module just surfaces those rows so the
idea_plan flow can include them in its prompt context — telling the LLM
which calibration / validation / ablation tricks are available without
having to hard-code them in every prompt.
"""
from __future__ import annotations

import sqlite3
from typing import Any


def load_techniques(db_path: str) -> list[dict[str, Any]]:
    """Return the techniques table contents, or [] if it doesn't exist."""
    out: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(db_path) as con:
            rows = con.execute(
                "SELECT name, pain_point, one_liner, when_to_use, "
                "failure_mode, recommendation, confidence, papers "
                "FROM techniques ORDER BY id"
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    for r in rows:
        out.append({
            "name": r[0],
            "pain_point": r[1].split(",") if r[1] else [],
            "one_liner": r[2],
            "when_to_use": r[3],
            "failure_mode": r[4],
            "recommendation": r[5],
            "confidence": r[6],
            "papers": r[7].split(",") if r[7] else [],
        })
    return out
