"""Tests for the Japanese-label / gloss layer."""
from __future__ import annotations


def test_family_label_and_gloss():
    from fingerprint_atlas.i18n import family_label, family_gloss
    # known ABM family — Japanese label + non-empty gloss
    assert "少数派ゲーム" in family_label("minority_game")
    assert family_gloss("minority_game"), "MG needs a gloss"
    assert "投機ゲーム" in family_label("speculation_game")
    # unknown family falls back to the raw key
    assert family_label("not_a_family") == "not_a_family"
    assert family_gloss("not_a_family") == ""


def test_fact_label_includes_gloss_for_each_canonical_fact():
    from fingerprint_atlas.i18n import fact_label, fact_gloss
    from fingerprint_atlas.gap_finder import CANONICAL_FACTS
    for fact in CANONICAL_FACTS:
        label = fact_label(fact)
        assert label and label != fact, f"missing JA label for {fact}"
        # 'other' is the only fact allowed an empty gloss
        if fact != "other":
            assert fact_gloss(fact), f"missing gloss for {fact}"
    # specific call-outs the user cares about
    assert "自己相関の欠如" in fact_label("absence-of-autocorr")
    assert "ヘビーテール" in fact_label("fat-tails")


def test_translate_gap_row_col_per_view():
    from fingerprint_atlas.i18n import translate_gap_row_col
    # view A: row stays, col becomes JA fact label
    r, c = translate_gap_row_col("A", "Minority Game", "fat-tails")
    assert r == "Minority Game"
    assert "ヘビーテール" in c
    # view B: row becomes JA family label, col becomes JA fact label
    r, c = translate_gap_row_col("B", "franke_westerhoff", "absence-of-autocorr")
    assert "Franke" in r and "Westerhoff" in r
    assert "自己相関" in c
    # view C: pass-through (techniques + subfields already readable)
    r, c = translate_gap_row_col("C", "Hill estimator", "Limit order book")
    assert r == "Hill estimator" and c == "Limit order book"


def test_gap_mine_cli_output_includes_japanese_labels(tmp_path, monkeypatch,
                                                       capsys):
    """End-to-end via cmd_gap_mine: verify Japanese surfaces in stdout."""
    import sqlite3
    from fingerprint_atlas import arxiv_cli
    from fingerprint_atlas.db import ensure_literature_schema, ensure_runs_schema
    db = str(tmp_path / "t.db")
    ensure_literature_schema(db)
    ensure_runs_schema(db)
    # Plant minimal runs so view B produces gaps
    from fingerprint_atlas.fingerprint import FEATURE_NAMES
    import json
    n = len(FEATURE_NAMES)
    far_fp_vec = [0.0] * n
    far_fp_vec[FEATURE_NAMES.index("acf_ret_l1")] = 8.0
    far_fp = json.dumps(far_fp_vec)
    with sqlite3.connect(db) as con:
        for k, model in enumerate(["real_spx", "real_btc"]):
            for j in range(3):
                jitter = [0.01 * (k * 3 + j + 1) / n] * n
                con.execute(
                    "INSERT INTO runs (model_name, params_json, seed, "
                    "fingerprint_json, series_kind, series_length, "
                    "provenance_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (model, "{}", 1, json.dumps(jitter), "returns", 1000,
                     "{}", "now"),
                )
        for _ in range(3):
            con.execute(
                "INSERT INTO runs (model_name, params_json, seed, "
                "fingerprint_json, series_kind, series_length, "
                "provenance_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                ("franke_westerhoff", "{}", 1, far_fp, "returns", 1000,
                 "{}", "now"),
            )
        con.commit()

    class A:
        pass
    args = A(); args.db = db; args.top = 5; args.json = False
    arxiv_cli.cmd_gap_mine(args)
    out = capsys.readouterr().out
    # Japanese view name surfaces in the per-view summary
    assert "ABM家系" in out or "スタイル化事実" in out
    # Family Japanese label surfaces in the top gaps
    assert "Franke" in out  # name remains, kana follows
    # Stylized-fact Japanese label surfaces
    assert "自己相関の欠如" in out