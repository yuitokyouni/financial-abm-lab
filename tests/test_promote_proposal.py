"""Tests for idea_cli promote-proposal — gap_mine proposal → idea row."""
from __future__ import annotations

import json
import sqlite3


def test_promote_proposal_creates_idea_with_back_link(tmp_path, capsys):
    from fingerprint_atlas import idea_cli
    from fingerprint_atlas.db import (ensure_proposals_schema,
                                         ensure_ideas_schema, insert_proposal,
                                         load_ideas)
    db = str(tmp_path / "t.db")
    ensure_proposals_schema(db)
    ensure_ideas_schema(db)
    # Seed a gap_mine proposal end-to-end (mirrors what gap_propose inserts).
    pid = insert_proposal(
        db,
        proposal_type="gap_mine",
        target_model="speculation_game",
        params={"N": 300, "_gap": {"view": "A",
                                      "row": "Prospect theory in trading",
                                      "col": "regime-switching",
                                      "salience": 3.89}},
        rationale="Prospect bias × regime 切替を SG layer 1 に組み込む実験。",
        predicted_fingerprint={"leverage": -0.15},
        predicted_novelty_distance=None,
        references=["1303.4321"],
        llm_model="openai/gpt-oss-120b",
    )

    class A:
        db = ""
        proposal_id = 0
    args = A(); args.db = db; args.proposal_id = pid
    rc = idea_cli.cmd_promote_proposal(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert f"proposal #{pid}" in out
    # idea was created, back-link to proposal recorded
    ideas = load_ideas(db)
    assert len(ideas) == 1
    idea = ideas[0]
    assert "speculation_game" in idea["idea_text"]
    assert "Prospect theory in trading × regime-switching" in idea["idea_text"]
    # proposal_ids is stored as comma-separated text
    with sqlite3.connect(db) as con:
        prop_ids = con.execute(
            "SELECT proposal_ids FROM ideas WHERE id = ?", (idea["id"],)
        ).fetchone()[0]
    assert prop_ids == str(pid)


def test_promote_proposal_errors_on_unknown_id(tmp_path, capsys):
    from fingerprint_atlas import idea_cli
    from fingerprint_atlas.db import (ensure_proposals_schema,
                                         ensure_ideas_schema)
    db = str(tmp_path / "t.db")
    ensure_proposals_schema(db)
    ensure_ideas_schema(db)

    class A:
        db = ""
        proposal_id = 999
    args = A(); args.db = db
    rc = idea_cli.cmd_promote_proposal(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "no proposal with id=999" in err
