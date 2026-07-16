"""Tests for the personal English↔Japanese glossary."""
from __future__ import annotations


def test_every_entry_has_required_fields():
    from fingerprint_atlas.glossary import GLOSSARY
    assert len(GLOSSARY) >= 30, "seed catalog should ship with >=30 entries"
    for e in GLOSSARY:
        assert e.get("en"), f"missing en: {e}"
        assert e.get("ja_primary"), f"missing ja_primary for {e.get('en')}"
        # Either avoid OR notes should be present so the LLM has context
        assert e.get("notes") or e.get("avoid"), \
            f"entry {e['en']} needs notes or avoid"


def test_lookup_and_search_are_case_insensitive():
    from fingerprint_atlas.glossary import lookup, search
    # known entry
    assert lookup("fingerprint") is not None
    assert lookup("FINGERPRINT") is not None
    assert lookup("Wealth Dynamics") is not None
    # unknown
    assert lookup("not-a-term") is None
    # search hits multiple
    hits = search("ボラティリティ")
    assert len(hits) >= 1
    assert any(h["en"] == "volatility clustering" for h in hits)


def test_user_specifically_rejected_translations_are_marked_avoid():
    """User explicitly rejected 富動学 (wealth dynamics) and 指紋 (fingerprint).
    These MUST be in the avoid list so the LLM never regenerates them."""
    from fingerprint_atlas.glossary import lookup
    wd = lookup("wealth dynamics")
    assert wd is not None
    bad_words = {a["bad"] for a in (wd.get("avoid") or [])}
    assert "富動学" in bad_words
    assert "動的富動" in bad_words

    fp = lookup("fingerprint")
    assert fp is not None
    bad_words = {a["bad"] for a in (fp.get("avoid") or [])}
    assert "指紋" in bad_words


def test_format_for_prompt_includes_primary_and_rejections():
    from fingerprint_atlas.glossary import format_for_prompt
    body = format_for_prompt()
    assert "日本語訳ガイド" in body
    # known primary translations surface
    assert "市場特徴量ベクトル" in body
    assert "ウェルス・ダイナミクス" in body
    # known rejections surface (with their why-reason near them)
    assert "指紋" in body
    assert "富動学" in body
    # primary and its rejection appear together in the same entry block:
    # e.g. '→ 市場特徴量ベクトル' followed within the same entry by 'reject: 指紋'
    # Find the fingerprint entry line and verify both are in proximity.
    assert "→ 市場特徴量ベクトル" in body
    fp_idx = body.find("→ 市場特徴量ベクトル")
    fp_block = body[fp_idx:fp_idx + 600]  # ~one entry's worth of text
    assert "reject:" in fp_block and "指紋" in fp_block


def test_format_for_prompt_can_be_scoped_to_domain():
    from fingerprint_atlas.glossary import format_for_prompt
    abm = format_for_prompt(domain="financial-abm")
    ml = format_for_prompt(domain="ml")
    # financial-abm scope shouldn't pull in pure-ML entries like SAE
    assert "スパースオートエンコーダ" not in abm
    # ml scope should
    assert "スパースオートエンコーダ" in ml
    # both should include 'general' entries (gap / mechanism / blind spot)
    assert "機構" in abm and "機構" in ml


def test_call_llm_prepends_glossary_when_generate_japanese_true(monkeypatch):
    """The glossary block must be added to the system prompt when
    generate_japanese=True, and absent otherwise."""
    from fingerprint_atlas import llm_client
    captured: dict = {}

    def fake_groq(system_prompt, user_payload, *, model,
                   temperature, max_retries):
        captured["sys"] = system_prompt
        return {"ok": True}

    monkeypatch.setattr(llm_client, "_call_groq", fake_groq)
    monkeypatch.setattr(llm_client, "_is_openai_model", lambda m: False)

    llm_client.call_llm("base sys", {"q": "x"}, "llama-3.1-70b",
                         generate_japanese=False)
    assert "市場特徴量ベクトル" not in captured["sys"]
    assert captured["sys"] == "base sys"

    llm_client.call_llm("base sys", {"q": "x"}, "llama-3.1-70b",
                         generate_japanese=True)
    assert "市場特徴量ベクトル" in captured["sys"]
    assert "base sys" in captured["sys"]


def test_cli_glossary_lookup_and_search(monkeypatch, capsys):
    """End-to-end CLI: lookup + search subcommands print expected JA labels."""
    from fingerprint_atlas import arxiv_cli

    class A:
        sub = "lookup"
        term = "fingerprint"
        domain = None
    rc = arxiv_cli.cmd_glossary(A())
    assert rc == 0
    out = capsys.readouterr().out
    assert "市場特徴量ベクトル" in out
    assert "指紋" in out  # reject reason surfaces

    A.sub = "search"
    A.term = "ボラ"
    rc = arxiv_cli.cmd_glossary(A())
    assert rc == 0
    out = capsys.readouterr().out
    assert "ボラティリティクラスタリング" in out
