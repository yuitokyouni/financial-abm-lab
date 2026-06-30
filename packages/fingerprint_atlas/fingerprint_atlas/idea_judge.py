"""idea_judge — natural-language idea → novelty verdict.

Given a free-form description of an ABM idea, surface the closest matches in
the local knowledge base (methods + literature_methods + proposals) and ask
the LLM for a structured novelty verdict:

  trivial_variant    : already covered by existing methods + parameter range
  incremental_novelty: one piece is new (e.g. param region, mechanism tweak)
  novel_combination  : combines existing mechanisms in a new way
  genuinely_novel    : a mechanism not present in DB nor in surfaced literature

Two LLM calls per idea (~5-8K tokens total):
  1. extract aspects (agent types, switching, target stylized facts, keywords)
  2. verdict (uses aspects + the surfaced top-N matches as context)

DB ranking is pure-Python keyword overlap; no embedding model needed.
"""
from __future__ import annotations

import re
from typing import Any

from .db import load_literature, load_proposals
from .methods import list_methods


DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


# ----- LLM prompts ---------------------------------------------------------

_JP_TERM_RULE = """\
日本語で書く field (summary_ja, rationale, 各 prose 系) では、必ず通用する
日本語表記(全角カタカナまたは漢字)を使うこと。半端な英語語幹+「的」
(例: 'mechan的', 'リテラチャー的に')、対義語が一般化していない直訳漢字
(例: '白箱')、未確立のカナ短縮は禁止。確立した訳語: メカニズム的解釈可能性,
ホワイトボックス, アグリゲート, スタイライズド・ファクト, 文献, 集団, 個体。

ただし keyword / tag / 識別子用の field(agent_types, key_keywords,
target_stylized_facts, mechanism_tags, closest_method, references 等)は
DB マッチングに使うので必ず英語のまま。日本語に翻訳しない。
"""


ASPECT_SYSTEM_PROMPT = """\
You extract structured aspects from a natural-language description of a
financial agent-based-model (ABM) research idea.

Output ONE JSON object with this shape (no prose around it):
{
  "agent_types": [<short ENGLISH labels — "fundamentalist", "LLM-trader",
                  "noise-trader", "speculator". DO NOT translate to Japanese.>],
  "switching_mechanism": "<1 sentence: how do agents adapt/switch, or null>",
  "price_formation": "<1 sentence: how does price emerge, or null>",
  "target_stylized_facts": [<0-5 of: "fat-tails", "vol-clustering", "leverage",
                            "long-memory", "regime-switching",
                            "aggregational-gaussianity", "absence-of-autocorr", "other">],
  "novelty_claim": "<1 sentence: what does the proposer think is new?>",
  "key_keywords": [<5-12 short ENGLISH keywords for DB search. The DB
                   methods table and literature abstracts are English, so
                   Japanese keywords match nothing. Examples: "herding",
                   "self-organized", "minority game", "speculation game",
                   "cognitive threshold", "order book", "Lux-Marchesi",
                   "reinforcement learning". Preserve English author /
                   model names verbatim. DO NOT translate to Japanese.>]
}
""" + _JP_TERM_RULE


VERDICT_SYSTEM_PROMPT = """\
You are judging whether a proposed financial-ABM idea is genuinely novel
relative to a local knowledge base.

You will receive:
  - idea           : the original natural-language description
  - aspects        : structured aspects extracted from the idea
  - candidate_methods   : existing ABM mechanisms (name + 1-line mechanism +
                          tag overlap score)
  - candidate_literature: arxiv papers (title + mechanism_summary + tags +
                          relevance to the idea)
  - candidate_proposals : prior executed proposals (rationale + target_model)

Return ONE JSON object:
{
  "category": "trivial_variant" | "incremental_novelty" |
              "novel_combination" | "genuinely_novel",
  "closest_method": "<method.name from candidate_methods, or null>",
  "closest_literature_arxiv_ids": [<arxiv_ids — MUST be a subset of the
                                   arxiv_ids in candidate_literature; do
                                   NOT cite papers from your pre-training
                                   memory or invent ids>],
  "closest_proposal_id": <int or null>,
  "covered_aspects": [<aspects already present in the DB; cite which match>],
  "novel_aspects": [<aspects NOT in the DB; the genuinely new pieces>],
  "differentiation_suggestions": [<2-4 concrete ways to maximise the
                                   research contribution, in Japanese>],
  "confidence": <float 0..1>,
  "summary_ja": "<2-4 sentence Japanese summary the user can read>"
}

Be critical. If the idea is mostly recombination, say so. If literature
already covers the same mechanism, say which paper and stop pretending.
""" + _JP_TERM_RULE


# ----- DB ranking (no LLM, pure keyword overlap) ---------------------------

_NORMALIZE_RE = re.compile(r"[^\w\s\-]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    s = _NORMALIZE_RE.sub(" ", text.lower())
    out: set[str] = set()
    for w in s.split():
        w = w.strip()
        if len(w) >= 3:
            out.add(w)
    return out


def _aspect_tokens(aspects: dict | None) -> set[str]:
    if not aspects:
        return set()
    bag = []
    for key in ("agent_types", "key_keywords", "target_stylized_facts"):
        bag.extend(aspects.get(key) or [])
    for key in ("switching_mechanism", "price_formation", "novelty_claim"):
        v = aspects.get(key)
        if v:
            bag.append(v)
    return _tokens(" ".join(str(x) for x in bag))


def rank_methods(db_path: str, aspects: dict, k: int = 5) -> list[dict]:
    methods = list_methods(db_path)
    needle = _aspect_tokens(aspects)
    scored = []
    for m in methods:
        hay = _tokens(" ".join([
            m.name, m.mechanism or "", m.novelty_notes or "",
            m.mechanism_strengths or "", m.mechanism_weaknesses or "",
            m.tags or "",
        ]))
        if not hay:
            continue
        overlap = len(needle & hay)
        scored.append({
            "name": m.name, "kind": m.kind,
            "mechanism_one_line": (m.mechanism or "").split(".")[0][:160],
            "score": int(overlap),
        })
    scored.sort(key=lambda r: -r["score"])
    return [r for r in scored if r["score"] > 0][:k] or scored[:k]


def rank_literature(db_path: str, aspects: dict, k: int = 5) -> list[dict]:
    rows = load_literature(db_path)
    if not rows:
        return []
    needle = _aspect_tokens(aspects)
    scored = []
    for r in rows:
        hay = _tokens(" ".join([
            r["title"] or "", r["mechanism_summary"] or "",
            r["novelty_signal"] or "", " ".join(r["mechanism_tags"]),
        ]))
        if not hay:
            continue
        overlap = len(needle & hay)
        # Tie-break by relevance_score so off-topic papers get pushed down.
        rel = r.get("relevance_score") or 0.0
        scored.append({
            "arxiv_id": r["arxiv_id"], "title": r["title"],
            "year": r["year"],
            "mechanism_summary": r["mechanism_summary"],
            "mechanism_tags": r["mechanism_tags"],
            "score": int(overlap),
            "relevance_score": rel,
        })
    scored.sort(key=lambda r: (-r["score"], -r["relevance_score"]))
    return [r for r in scored if r["score"] > 0][:k] or scored[:k]


def rank_proposals(db_path: str, aspects: dict, k: int = 5) -> list[dict]:
    rows = load_proposals(db_path)
    if not rows:
        return []
    # Skip rejected rows so cleared-out template-rationale proposals stop
    # polluting the idea_judge context.
    rows = [r for r in rows if (r.get("status") or "") != "rejected"]
    if not rows:
        return []
    needle = _aspect_tokens(aspects)
    scored = []
    for r in rows:
        hay = _tokens(" ".join([
            r["target_model"], r["rationale"] or "",
        ]))
        if not hay:
            continue
        overlap = len(needle & hay)
        rationale_lines = (r["rationale"] or "").splitlines()
        scored.append({
            "id": r["id"], "target_model": r["target_model"],
            "status": r["status"],
            "rationale_one_line": (rationale_lines[0][:120]
                                   if rationale_lines else ""),
            "score": int(overlap),
        })
    scored.sort(key=lambda r: -r["score"])
    return [r for r in scored if r["score"] > 0][:k]


# ----- LLM driver ---------------------------------------------------------

def _call_groq(system_prompt: str, user_payload: dict, model: str,
               temperature: float = 0.4, max_retries: int = 2) -> dict:
    """Backwards-compatible alias for `llm_client.call_llm`. Despite the
    name, this routes to OpenAI when `model` is an OpenAI chat model id
    (gpt-4o-mini etc); see llm_client._is_openai_model for the dispatch
    rule. Kept under the old name so existing callers don't have to
    change."""
    from .llm_client import call_llm
    return call_llm(system_prompt, user_payload, model,
                    temperature=temperature, max_retries=max_retries,
                    generate_japanese=True,
                    glossary_domain="financial-abm")


def extract_aspects(idea_text: str, groq_model: str = DEFAULT_GROQ_MODEL,
                    *, dry_run_response: dict | None = None) -> dict:
    if dry_run_response is not None:
        return dry_run_response
    return _call_groq(ASPECT_SYSTEM_PROMPT, {"idea": idea_text}, groq_model)


def judge_idea(db_path: str, idea_text: str, *,
               groq_model: str = DEFAULT_GROQ_MODEL,
               k_each: int = 5,
               dry_run_aspects: dict | None = None,
               dry_run_verdict: dict | None = None) -> dict:
    """End-to-end: extract → rank → verdict. Returns a single dict."""
    aspects = extract_aspects(idea_text, groq_model,
                              dry_run_response=dry_run_aspects)
    methods = rank_methods(db_path, aspects, k=k_each)
    literature = rank_literature(db_path, aspects, k=k_each)
    proposals = rank_proposals(db_path, aspects, k=k_each)
    payload = {
        "idea": idea_text,
        "aspects": aspects,
        "candidate_methods": methods,
        "candidate_literature": literature,
        "candidate_proposals": proposals,
    }
    if dry_run_verdict is not None:
        verdict = dry_run_verdict
    else:
        verdict = _call_groq(VERDICT_SYSTEM_PROMPT, payload, groq_model)
    warnings = _filter_verdict_arxiv_ids(verdict, literature, db_path)
    return {
        "aspects": aspects,
        "matches": {
            "methods": methods, "literature": literature, "proposals": proposals,
        },
        "verdict": verdict,
        "verdict_warnings": warnings,
        "llm_model": groq_model,
    }


def _filter_verdict_arxiv_ids(verdict: dict, candidate_literature: list[dict],
                              db_path: str) -> dict:
    """Drop arxiv ids the LLM cited that aren't in the candidate list.

    Bucket the cited ids three ways (same scheme as propose.classify_references):
      - in_candidates : id was in candidate_literature (the only allowed source)
      - in_db_only    : id exists in literature_methods but wasn't surfaced
                        by ranking — LLM probably pulled it from pre-training
                        but it happens to be real. Kept but flagged.
      - hallucinated  : id parses as arxiv but isn't anywhere in the DB.
                        Dropped from the verdict, listed in warnings.

    Mutates `verdict` in place; returns a `warnings` dict the caller can
    surface in the CLI output / persist alongside the judgment.
    """
    from .propose import _arxiv_base, _extract_arxiv_id
    if not isinstance(verdict, dict):
        return {"in_db_only": [], "hallucinated": []}
    ids = verdict.get("closest_literature_arxiv_ids") or []
    if not ids:
        return {"in_db_only": [], "hallucinated": []}
    candidate_bases = {_arxiv_base(r["arxiv_id"]) for r in candidate_literature
                       if r.get("arxiv_id")}
    db_bases: set[str] = set()
    try:
        from .db import load_literature
        db_bases = {_arxiv_base(r["arxiv_id"]) for r in load_literature(db_path)}
    except Exception:
        pass
    kept: list[str] = []
    in_db_only: list[str] = []
    hallucinated: list[str] = []
    for cited in ids:
        aid = _extract_arxiv_id(cited) or cited
        base = _arxiv_base(aid)
        if base in candidate_bases:
            kept.append(cited)
        elif base in db_bases:
            kept.append(cited)
            in_db_only.append(cited)
        else:
            hallucinated.append(cited)
    verdict["closest_literature_arxiv_ids"] = kept
    return {"in_db_only": in_db_only, "hallucinated": hallucinated}
