"""methods_draft — LLM-assisted draft of methodology notes for a method.

Generates a starting point for the four commentary columns of a row in
`methods`. The user can then run `methods_cli edit <name>` to review,
modify, accept, or discard.

The LLM (gpt-oss-120b on Groq by default) sees:
  - The method's mechanism description (from SEED or user edit)
  - The method's references
  - User notes already present on this method (refresh path)
  - User notes on OTHER methods (style reference — keeps voice consistent)
  - Relevant literature_methods entries — picked by tag overlap with the
    target method and arxiv id of references

Output is a single JSON object:
  {
    "novelty_notes":         "...",
    "mechanism_strengths":   "...",
    "mechanism_weaknesses":  "...",
    "research_questions":    "...",
    "tags":                  "..."   // optional comma-separated tags
  }

Used by `methods_cli draft <name>` to write a markdown file the user
opens with `methods_cli edit <name>`.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .methods import Method, list_methods


DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


SYSTEM_PROMPT = """\
You are drafting research notes on a financial agent-based model (ABM) on
behalf of a researcher who maintains a methodology DB.

You will receive a JSON context with:
  - target_method      : the method being annotated — name, kind, mechanism,
                         references, user_notes_so_far
  - other_methods_notes: existing user notes on OTHER methods. Match their
                         voice and concreteness. They are the style guide.
  - relevant_literature: arxiv papers whose mechanism_tags overlap with
                         the target. Cite their arxiv_id when the connection
                         is real.

Your task: produce DRAFT research notes for these four commentary columns
(plus optional tags). The user will edit your draft before saving.

Output ONE JSON object:
  {
    "novelty_notes":         "<methodological novelty assessment, 2-5 sentences,
                              honest about what is *not* novel>",
    "mechanism_strengths":   "<what the method captures well — bullet form is
                              fine; cite arxiv_ids when supporting a claim>",
    "mechanism_weaknesses":  "<what is weak / missing / under-mechanised —
                              be specific, not generic. List concrete failure
                              modes>",
    "research_questions":    "<2-4 open questions this method raises;
                              questions that an experiment could answer>",
    "tags":                  "<optional comma-separated tags like
                              'novelty:medium, mechanism:reusable,
                              borrowable:cognitive-price'>"
  }

Style requirements (HARD constraints):
  - Write in Japanese.
  - Be critical. Disagreement with the original paper is welcomed.
  - Cite from `relevant_literature` ONLY by arxiv_id (e.g. "arXiv:2604.18602").
    Do not fabricate arxiv ids.
  - Avoid template phrases: "の関係を調べる", "を目的としています",
    "ダイナミクスの理解を深める" — these are red flags of empty content.
  - Each field MUST be non-empty; if you genuinely don't have a draft,
    write one honest sentence saying so (e.g. "実装と現実の差分の評価が
    まだ不足しているため、現時点では空欄に等しい").

Output ONLY the JSON object. No prose around it.
"""


def _select_other_methods_notes(target: Method, all_methods: list[Method],
                                k: int = 4) -> list[dict[str, Any]]:
    """Pick up to k other methods that already have user-written notes.

    Prefer same `kind` (abm/synthetic/etc.) — they share commentary style;
    fall back to anyone with notes.
    """
    others = [m for m in all_methods if m.name != target.name and any(
        getattr(m, sec) for sec in ("novelty_notes", "mechanism_strengths",
                                     "mechanism_weaknesses", "research_questions"))]
    same_kind = [m for m in others if m.kind == target.kind]
    rest = [m for m in others if m.kind != target.kind]
    picks = (same_kind + rest)[:k]
    return [{
        "name": m.name, "kind": m.kind,
        "user_notes": {
            "novelty_notes": m.novelty_notes,
            "mechanism_strengths": m.mechanism_strengths,
            "mechanism_weaknesses": m.mechanism_weaknesses,
            "research_questions": m.research_questions,
            "tags": m.tags,
        },
    } for m in picks]


def _select_relevant_literature(target: Method, db_path: str,
                                 k: int = 10) -> list[dict[str, Any]]:
    """Heuristic: pull literature with mechanism_tags overlapping the target's
    methods row, plus any paper whose arxiv_id is already in target.references.
    """
    from .db import load_literature
    rows = load_literature(db_path)
    if not rows:
        return []
    target_tag_words = set()
    for t in (target.tags or "").split(","):
        for w in t.replace(":", " ").split():
            if w.strip():
                target_tag_words.add(w.strip().lower())
    # Use method name itself + kind as additional implicit tags.
    target_tag_words.update({target.name.replace("_", " "), target.kind})
    # also pull from mechanism keywords
    for kw in ("herding", "order-book", "minority", "chartist", "fundamentalist",
               "regime", "LLM-agent", "calibration", "GARCH", "Lévy"):
        if kw.lower() in (target.mechanism or "").lower():
            target_tag_words.add(kw.lower())

    scored: list[tuple[float, dict]] = []
    target_refs = {r for r in (target.references or [])}
    for r in rows:
        if r.get("relevance_score") is None or r.get("relevance_score", 0) < 0.4:
            continue
        # Tag overlap score
        tags_lower = {t.lower() for t in r.get("mechanism_tags", [])}
        overlap = len(tags_lower & target_tag_words)
        # bonus if the paper is explicitly in target.references
        if r["arxiv_id"] in target_refs or f"arXiv:{r['arxiv_id']}" in target_refs:
            overlap += 5
        scored.append((overlap + 0.1 * (r.get("relevance_score") or 0), r))
    scored.sort(key=lambda kv: -kv[0])
    out = []
    for score, r in scored[:k]:
        out.append({
            "arxiv_id": r["arxiv_id"], "title": r["title"], "year": r["year"],
            "mechanism_summary": r.get("mechanism_summary"),
            "mechanism_tags": r.get("mechanism_tags"),
            "stylized_facts_targeted": r.get("stylized_facts_targeted"),
            "novelty_signal": r.get("novelty_signal"),
            "_relevance_to_target": round(float(score), 3),
        })
    return out


def _call_groq(system_prompt: str, user_payload: dict, model: str,
               temperature: float = 0.5, max_retries: int = 2) -> dict:
    """Retries up to max_retries times on Groq's transient
    'json_validate_failed' 400 (gpt-oss-120b JSON-mode quirk)."""
    try:
        from groq import Groq
    except ImportError as e:
        raise ImportError("groq SDK not installed. `uv add groq`.") from e
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")
    client = Groq(api_key=api_key)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            transient = ("json_validate_failed" in msg
                         or "Failed to validate JSON" in msg)
            if attempt < max_retries and transient:
                temperature = min(1.0, temperature + 0.1)
                continue
            raise
    raise last_exc


def draft_notes_for_method(db_path: str, method_name: str, *,
                           groq_model: str = DEFAULT_GROQ_MODEL,
                           temperature: float = 0.5,
                           dry_run_response: dict | None = None
                           ) -> dict[str, Any]:
    """Build the context, call the LLM (or use dry_run_response), validate."""
    all_methods = list_methods(db_path)
    target = next((m for m in all_methods if m.name == method_name), None)
    if target is None:
        raise KeyError(f"no method named {method_name!r}")

    context = {
        "target_method": {
            "name": target.name, "kind": target.kind,
            "mechanism": target.mechanism,
            "references": target.references,
            "user_notes_so_far": {
                "novelty_notes": target.novelty_notes,
                "mechanism_strengths": target.mechanism_strengths,
                "mechanism_weaknesses": target.mechanism_weaknesses,
                "research_questions": target.research_questions,
                "tags": target.tags,
            },
        },
        "other_methods_notes": _select_other_methods_notes(target, all_methods),
        "relevant_literature": _select_relevant_literature(target, db_path),
    }

    if dry_run_response is not None:
        raw = dry_run_response
    else:
        raw = _call_groq(SYSTEM_PROMPT, {"context": context}, groq_model, temperature)

    # defensive parse: ensure each field is a string AND normalise newlines.
    # gpt-oss-120b (and some other Groq models) emit literal '\n' inside JSON
    # string values rather than using JSON's actual newline escape. After
    # json.loads that becomes a backslash-n literal in the Python string,
    # which renders as '\n' on display instead of a line break. Normalise.
    def _str(v):
        if v is None:
            return ""
        return str(v).strip().replace("\\n", "\n")

    draft = {
        "novelty_notes": _str(raw.get("novelty_notes")),
        "mechanism_strengths": _str(raw.get("mechanism_strengths")),
        "mechanism_weaknesses": _str(raw.get("mechanism_weaknesses")),
        "research_questions": _str(raw.get("research_questions")),
        "tags": _str(raw.get("tags")),
    }
    return {"draft": draft, "context_used": {
        "n_other_methods_notes": len(context["other_methods_notes"]),
        "n_relevant_literature": len(context["relevant_literature"]),
        "literature_cited_in_context": [p["arxiv_id"]
                                        for p in context["relevant_literature"]],
    }, "llm_model": groq_model}
