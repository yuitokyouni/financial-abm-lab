"""arxiv_ingest — pull papers from arxiv, extract mechanism info via Groq, store.

The financial-ABM literature is large enough that a generic LLM cannot recall
recent mechanisms from training data alone. This module builds a queryable
literature DB so the proposer (`propose.py`) can ground its suggestions in
actual papers.

Pipeline per ingestion call:
  1. `query_arxiv(query, max_results)`        — list of paper metadata via the
                                                arxiv API. No LLM yet.
  2. `extract_paper_structured(paper, model)` — Groq Llama 3.3 70B classifies:
                                                mechanism summary, tags, stylized
                                                facts targeted, novelty signal,
                                                relevance to financial-ABM atlas.
  3. `ingest(db, ...)`                        — runs (1) then (2) per paper,
                                                writes to `literature_methods`.

arxiv metadata is upserted (idempotent on arxiv_id). LLM extraction is a
separate step so a metadata refresh does not wipe extraction results, and so
re-extraction (e.g. after a prompt change) is targeted.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

DEFAULT_QUERIES = {
    "financial_abm": (
        'cat:q-fin.TR OR cat:q-fin.CP OR cat:q-fin.ST'
    ),
    "agent_based_recent": (
        '(abs:"agent-based" OR abs:"ABM" OR abs:"heterogeneous agents") '
        'AND (cat:q-fin.* OR cat:physics.soc-ph)'
    ),
}

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured information from arxiv paper abstracts about financial
markets, agent-based modelling (ABM), or related computational methods.

Given a paper's title and abstract, return a single JSON object:

{
  "mechanism_summary": "1-3 sentences describing the concrete mechanism / model /
                        method proposed. If the paper is not about a mechanism
                        but e.g. a survey, say so.",
  "mechanism_tags": [<3-5 short keywords describing what KIND of mechanism it is>],
                     // examples: 'herding', 'order-book', 'LLM-agent',
                     //           'regime-switching', 'percolation',
                     //           'minority-game', 'reinforcement-learning',
                     //           'differentiable-ABM', 'calibration-method',
                     //           'sentiment-analysis', 'microstructure'
  "stylized_facts_targeted": [<0-5 stylized facts the paper claims to reproduce
                               or analyse>],
                              // choose ONLY from this fixed list:
                              //   'fat-tails', 'vol-clustering', 'leverage',
                              //   'long-memory', 'regime-switching',
                              //   'aggregational-gaussianity', 'absence-of-autocorr',
                              //   'other'
  "novelty_signal": "1 sentence describing what the paper claims is genuinely
                     novel relative to prior work, or null if no clear claim.",
  "relevance_score": <float 0..1, your estimate of how relevant this paper is
                     to building/extending an atlas of FINANCIAL agent-based
                     models. < 0.3 if the paper is only tangentially related.>
}

Be conservative. Output ONLY the JSON object, no prose.
"""


def query_arxiv(query: str, max_results: int = 50,
                sort_by: str = "submitted") -> list[dict[str, Any]]:
    """Query the arxiv API, return a list of paper metadata dicts."""
    import arxiv
    sort_map = {
        "submitted": arxiv.SortCriterion.SubmittedDate,
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdated": arxiv.SortCriterion.LastUpdatedDate,
    }
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=sort_map.get(sort_by, arxiv.SortCriterion.SubmittedDate),
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client(page_size=min(100, max_results), delay_seconds=3.0)
    out = []
    for r in client.results(search):
        # entry_id like 'http://arxiv.org/abs/2412.01234v2' → strip prefix + version
        eid = r.entry_id.rsplit("/", 1)[-1]
        out.append({
            "arxiv_id": eid,
            "title": r.title.strip().replace("\n", " "),
            "authors": ", ".join(a.name for a in r.authors),
            "year": r.published.year,
            "published_date": r.published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primary_category": r.primary_category,
            "abstract": r.summary.strip().replace("\n", " "),
        })
    return out


def _call_groq_for_extraction(paper: dict, model: str,
                              temperature: float = 0.3) -> dict:
    """One Groq call extracting structured info from a paper."""
    try:
        from groq import Groq
    except ImportError as e:
        raise ImportError(
            "groq SDK not installed. Run `uv add groq` or `pip install groq`."
        ) from e
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set.")
    client = Groq(api_key=api_key)
    user_msg = f"Title: {paper['title']}\n\nAbstract: {paper['abstract']}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(resp.choices[0].message.content)


def extract_paper_structured(paper: dict, model: str = DEFAULT_GROQ_MODEL, *,
                             dry_run_response: dict | None = None) -> dict:
    """Call Groq (or use dry_run_response) and validate the extraction.

    Defensive parsing — Llama 3.3 occasionally returns string-formatted lists,
    null for tags, etc. Cooerce into the contract.
    """
    if dry_run_response is not None:
        raw = dry_run_response
    else:
        raw = _call_groq_for_extraction(paper, model)

    def _list_or_split(v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [t.strip() for t in str(v).split(",") if t.strip()]

    return {
        "mechanism_summary": (raw.get("mechanism_summary") or "").strip() or None,
        "mechanism_tags": _list_or_split(raw.get("mechanism_tags"))[:8],
        "stylized_facts_targeted": _list_or_split(raw.get("stylized_facts_targeted"))[:6],
        "novelty_signal": (raw.get("novelty_signal") or "").strip() or None,
        "relevance_score": _coerce_relevance(raw.get("relevance_score")),
        "extracted_by_model": model,
    }


def _coerce_relevance(v) -> float | None:
    """Clamp to [0, 1], coerce strings."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, f))


def ingest(db_path: str, *, query: str, max_results: int = 50,
           extract: bool = True, groq_model: str = DEFAULT_GROQ_MODEL,
           min_relevance_to_keep: float = 0.0,
           verbose: bool = True) -> dict:
    """End-to-end: query → upsert metadata → (optional) LLM extract → store.

    Returns a summary dict. Re-running over the same query is safe; arxiv_id is
    unique. Papers already extracted are skipped unless their extraction is
    stale (we don't currently re-extract — see `re-extract` CLI sub-command).
    """
    from .db import (
        ensure_literature_schema, upsert_literature_metadata,
        update_literature_extraction, load_literature,
    )
    ensure_literature_schema(db_path)

    if verbose:
        print(f"querying arxiv: {query!r}  (max_results={max_results})")
    papers = query_arxiv(query, max_results=max_results)
    if verbose:
        print(f"  -> {len(papers)} papers returned by arxiv")

    n_new, n_extracted, n_skipped, n_dropped = 0, 0, 0, 0
    errors = []

    for p in papers:
        # upsert metadata (cheap)
        before_rows = load_literature(db_path)
        had_id = any(r["arxiv_id"] == p["arxiv_id"] for r in before_rows)
        upsert_literature_metadata(
            db_path,
            arxiv_id=p["arxiv_id"], title=p["title"], authors=p["authors"],
            year=p["year"], published_date=p["published_date"],
            primary_category=p["primary_category"], abstract=p["abstract"],
        )
        if not had_id:
            n_new += 1

        if not extract:
            continue

        # skip if already extracted
        already_extracted = any(
            r["arxiv_id"] == p["arxiv_id"] and r["extracted_by_model"]
            for r in before_rows
        )
        if already_extracted:
            n_skipped += 1
            continue

        try:
            ext = extract_paper_structured(p, groq_model)
        except Exception as exc:
            errors.append({"arxiv_id": p["arxiv_id"], "error": str(exc)[:200]})
            if verbose:
                print(f"  ! {p['arxiv_id']}: extraction failed: {exc}")
            continue

        # apply relevance filter (do NOT delete row; mark with low score)
        if (ext["relevance_score"] is not None
                and ext["relevance_score"] < min_relevance_to_keep):
            n_dropped += 1
            if verbose:
                print(f"  - {p['arxiv_id']} relevance {ext['relevance_score']:.2f} below "
                      f"threshold {min_relevance_to_keep}, keeping metadata but skipping extract")
            continue

        update_literature_extraction(
            db_path, p["arxiv_id"],
            mechanism_summary=ext["mechanism_summary"],
            mechanism_tags=ext["mechanism_tags"],
            stylized_facts_targeted=ext["stylized_facts_targeted"],
            novelty_signal=ext["novelty_signal"],
            relevance_score=ext["relevance_score"],
            extracted_by_model=ext["extracted_by_model"],
        )
        n_extracted += 1
        if verbose:
            rel = ext["relevance_score"]
            tags = ",".join(ext["mechanism_tags"][:3])
            print(f"  + {p['arxiv_id']} [{p['year']}] rel={rel}  tags=[{tags}]  "
                  f"{p['title'][:70]}")

        # arxiv-friendly pacing already enforced by arxiv.Client; Groq has
        # its own per-key rate limit (we just keep the loop sequential).
        time.sleep(0.1)

    return {
        "query": query, "n_papers_returned": len(papers),
        "n_new_metadata": n_new, "n_extracted": n_extracted,
        "n_skipped_already_extracted": n_skipped,
        "n_dropped_below_relevance": n_dropped,
        "n_errors": len(errors),
        "errors": errors,
        "groq_model": groq_model if extract else None,
    }
