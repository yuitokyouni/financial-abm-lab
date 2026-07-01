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
import re as _re
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
    "financial_abm_strict": (
        # Constrained to q-fin.TR (Trading & Microstructure), and abstract MUST
        # mention a financial-ABM-specific mechanism phrase. This avoids the
        # off-topic capture observed with `agent_based_recent` (engines, AMM
        # market-making, opinion dynamics — high LLM-rated but tangentially
        # relevant to our atlas).
        'cat:q-fin.TR AND ('
        'abs:"heterogeneous agent" OR abs:"heterogeneous agents" '
        'OR abs:"agent-based market" OR abs:"agent-based model" '
        'OR abs:"speculation game" OR abs:"minority game" '
        'OR abs:"market microstructure" OR abs:"limit order book" '
        'OR abs:"chartist" OR abs:"fundamentalist" '
        'OR abs:"herding" OR abs:"stylized facts")'
    ),
    "foundational_abm": (
        # Catches the older / cross-category ABM foundations the q-fin
        # query misses: physics.soc-ph self-organization, MG / SG /
        # Lux-Marchesi / Cont-Bouchaud / Challet et al. work, including
        # pre-2020 papers and econophysics venues. Pair with --sort
        # relevance so well-cited classics surface even if old.
        '(cat:physics.soc-ph OR cat:q-fin.GN OR cat:q-fin.TR OR cat:nlin.AO) '
        'AND ('
        'abs:"minority game" OR abs:"speculation game" '
        'OR abs:"self-organized" OR abs:"self-organization" '
        'OR abs:"Lux-Marchesi" OR abs:"Cont-Bouchaud" '
        'OR abs:"Challet" OR abs:"Katahira" '
        'OR abs:"stylized fact" OR abs:"stylized facts" '
        'OR abs:"financial market model" OR abs:"econophysics")'
    ),
    # ----- targeted coverage-gap presets -----
    # Each preset fills a sparse column or under-represented mechanism
    # cluster in the literature_methods coverage matrix. Sweep all of them
    # to lift the per-cell paper count off 0/1.
    "behavioral_finance": (
        # Loss aversion / disposition effect / overconfidence — the
        # behavioral-bias literature that LLM-agent papers (TRIBE,
        # TraderTalk etc) build on. Currently sparse in our corpus.
        '(cat:q-fin.TR OR cat:q-fin.GN OR cat:q-fin.ST) AND ('
        'abs:"loss aversion" OR abs:"disposition effect" '
        'OR abs:"overconfidence" OR abs:"prospect theory" '
        'OR abs:"reference point" OR abs:"behavioral bias")'
    ),
    "herding_dynamics": (
        # The herding STYLIZED FACT in *financial* settings. The earlier
        # 'OR cat:physics.soc-ph' variant pulled a flood of off-topic
        # sociology-of-opinion papers (voter / majority-rule / flocking).
        # Restrict to q-fin and require a finance-specific keyword.
        'cat:q-fin.* AND ('
        'abs:"herding behavior" OR abs:"information cascade" '
        'OR abs:"financial contagion" OR abs:"market contagion" '
        'OR abs:"investor herding" OR abs:"trader herding") '
    ),
    "leverage_effect": (
        # Asymmetric volatility / leverage effect — the empirical
        # asymmetry between price-down + vol-up vs price-up. Almost
        # empty in our matrix.
        '(cat:q-fin.* OR cat:stat.AP) AND ('
        'abs:"leverage effect" OR abs:"asymmetric volatility" '
        'OR abs:"volatility asymmetry" OR abs:"negative-return positive-volatility")'
    ),
    "regime_switching": (
        # Markov-switching / hidden-state regime models. Bridges
        # ABM-flavor and time-series-flavor literature.
        '(cat:q-fin.* OR cat:stat.AP) AND ('
        'abs:"regime switching" OR abs:"regime change" '
        'OR abs:"Markov switching" OR abs:"hidden Markov" '
        'OR abs:"structural break" OR abs:"market regime")'
    ),
    "econophysics_classics": (
        # Targeted at the 1995-2010 econophysics body of work: scaling
        # laws, multifractality, Mantegna-Stanley distributional studies.
        '(cat:physics.soc-ph OR cat:cond-mat.stat-mech OR cat:q-fin.ST) AND ('
        'abs:"power law" OR abs:"scaling law" OR abs:"multifractal" '
        'OR abs:"Mantegna" OR abs:"Stanley" '
        'OR abs:"empirical finance" OR abs:"financial scaling")'
    ),
    "low_freq_returns": (
        # Long-memory & aggregational-gaussianity — the two stylized
        # facts most under-represented in our coverage matrix.
        'cat:q-fin.* AND ('
        'abs:"long memory" OR abs:"long-range dependence" '
        'OR abs:"Hurst exponent" OR abs:"fractional integration" '
        'OR abs:"aggregational gaussianity" OR abs:"return distribution scaling")'
    ),
}

# Same default as propose.py — chosen after live A/B (see propose.py for notes).
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

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
                              // choose ONLY from this fixed list (Cont 2001
                              // + two ABM-specific targets):
                              //   'fat-tails'                    heavy tails in returns
                              //   'vol-clustering'               ARCH-like clustering
                              //   'leverage'                     corr(r_t, sigma^2_{t+k}) < 0
                              //   'long-memory'                  slow ACF decay in |r|
                              //   'aggregational-gaussianity'    normal at low freq
                              //   'absence-of-autocorr'          lag-1 ACF ~ 0 for r
                              //   'gain-loss-asymmetry'          drawdowns faster than rallies
                              //   'volume-volatility-corr'       high vol ↔ high volume
                              //   'regime-switching'             discrete state changes
                              //   'herding'                      correlated agent action
                              //   'other'                        last-resort catch-all —
                              //                                  use ONLY if the paper's
                              //                                  target really doesn't
                              //                                  match any label above
  "novelty_signal": "1 sentence describing what the paper claims is genuinely
                     novel relative to prior work, or null if no clear claim.",
  "relevance_score": <float 0..1, your estimate of how relevant this paper is
                     to building/extending an atlas of FINANCIAL agent-based
                     models. < 0.3 if the paper is only tangentially related.>
}

Be conservative. Output ONLY the JSON object, no prose.
"""


def query_arxiv_by_ids(arxiv_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch arxiv metadata for an explicit list of arxiv_ids. Useful for
    targeted ingest of foundational papers (e.g. Katahira-Chen 1909.03185)
    that the broad-query passes can miss because they're old or in a
    category we don't sweep."""
    import arxiv
    # Defence: strip whitespace, drop trailing '# comment', drop version
    # suffix (arxiv id_list expects base ids; entry_id carries the version).
    cleaned: list[str] = []
    for raw in arxiv_ids:
        if not raw:
            continue
        s = str(raw).split("#", 1)[0].strip()
        if not s:
            continue
        cleaned.append(_re.sub(r"v\d+$", "", s))
    if not cleaned:
        return []
    search = arxiv.Search(id_list=cleaned)
    client = arxiv.Client(page_size=min(100, len(cleaned)), delay_seconds=3.0)
    out = []
    for r in client.results(search):
        out.append({
            "arxiv_id": _extract_arxiv_id_from_entry(r.entry_id),
            "title": r.title.strip().replace("\n", " "),
            "authors": ", ".join(a.name for a in r.authors),
            "year": r.published.year,
            "published_date": r.published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primary_category": r.primary_category,
            "abstract": r.summary.strip().replace("\n", " "),
            "comment": (r.comment or "").strip() or None,
        })
    return out


def _extract_arxiv_id_from_entry(entry_id: str) -> str:
    """Pull the canonical arxiv id (incl. category prefix for old papers)
    out of arxiv's `entry_id` URL.

    arxiv has two id schemes:
      new-style (2007+) : `http://arxiv.org/abs/2503.00320v2`
                          → '2503.00320v2'
      old-style         : `http://arxiv.org/abs/cond-mat/0101326v1`
                          → 'cond-mat/0101326v1' (NOT just '0101326v1' —
                            the category is part of the id)

    A naive `rsplit('/', 1)[-1]` strips the category off old-style ids,
    breaking DOI lookups (the canonical DOI is
    `10.48550/arXiv.cond-mat/0101326`, not `…/0101326`)."""
    marker = "/abs/"
    if (i := entry_id.find(marker)) >= 0:
        raw = entry_id[i + len(marker):]
    else:
        raw = entry_id.rsplit("/", 1)[-1]
    return _re.sub(r"v\d+$", "", raw)


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
        out.append({
            "arxiv_id": _extract_arxiv_id_from_entry(r.entry_id),
            "title": r.title.strip().replace("\n", " "),
            "authors": ", ".join(a.name for a in r.authors),
            "year": r.published.year,
            "published_date": r.published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primary_category": r.primary_category,
            "abstract": r.summary.strip().replace("\n", " "),
            "comment": (r.comment or "").strip() or None,
        })
    return out


def _call_groq_for_extraction(paper: dict, model: str,
                              temperature: float = 0.3,
                              max_retries: int = 2) -> dict:
    """Per-paper structured extraction. Wraps `llm_client.call_llm`, which
    routes to OpenAI when `model` is an OpenAI chat model id, otherwise
    Groq. Keeps an explicit `time.sleep(65)` recovery on Groq 429 since
    the per-key TPM window is 60s — that backoff is more aggressive than
    the generic transient retry."""
    from .llm_client import call_llm
    paper_payload = {"title": paper["title"], "abstract": paper["abstract"]}
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            # Structured extraction output is English-only (DB keys, tag
            # matching, coverage matrix all key on the English slug). Do
            # NOT inject the JA glossary — it leaked JA tokens into
            # mechanism_tags for at least one paper (limited-rationality
            # etc), which then split the coverage matrix on tag equality.
            return call_llm(EXTRACTION_SYSTEM_PROMPT, paper_payload, model,
                            temperature=temperature, max_retries=0,
                            generate_japanese=False)
        except Exception as exc:
            last_exc = exc
            msg = str(exc)
            # Recovery classification by explicit error CODE, not
            # message keywords — Groq's 429 body carries an upsell URL
            # (`.../settings/billing`) that used to false-positive the
            # naive `"billing" in msg` check and skip all retries.
            unrecoverable = ("insufficient_quota" in msg
                             or "invalid_api_key" in msg)
            if unrecoverable:
                raise
            rate_limited = ("rate_limit_exceeded" in msg
                            or "Rate limit reached" in msg
                            or "429" in msg)
            # Groq exposes two separate 429s: TPM (tokens/min, refills
            # in seconds) vs TPD (tokens/day, refills in minutes-to-
            # hours). Only TPM is worth the 65s in-loop sleep — TPD
            # never recovers inside that window, so we bail immediately
            # with a clear message so the caller can switch model or
            # come back tomorrow instead of burning the retry budget.
            tpd = "tokens per day" in msg or "TPD" in msg
            if tpd:
                print(f"  (TPD quota exhausted on {paper['arxiv_id']}; "
                      f"daily budget used up — retry logic can't help. "
                      f"Wait until reset or switch --groq-model.)")
                raise
            if attempt < max_retries and rate_limited:
                print(f"  (TPM rate-limit on {paper['arxiv_id']}, "
                      f"sleeping 65s before retry {attempt + 1}/{max_retries})")
                time.sleep(65)
                continue
            raise
    raise last_exc


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


def ingest(db_path: str, *, query: str | None = None, max_results: int = 50,
           extract: bool = True, groq_model: str = DEFAULT_GROQ_MODEL,
           min_relevance_to_keep: float = 0.0,
           papers: list[dict[str, Any]] | None = None,
           verbose: bool = True) -> dict:
    """End-to-end: query → upsert metadata → (optional) LLM extract → store.

    Either pass `query` (broad arxiv search) or a pre-fetched `papers` list
    (e.g. from `query_arxiv_by_ids` for targeted ingest). Re-running over
    the same papers is safe; arxiv_id is unique. Papers already extracted
    are skipped.
    """
    from .db import (
        ensure_literature_schema, upsert_literature_metadata,
        update_literature_extraction, load_literature,
        set_literature_code_url, set_arxiv_comment,
    )
    from .code_links import resolve_code_url
    ensure_literature_schema(db_path)

    if papers is None:
        if not query:
            raise ValueError("either `query` or `papers` must be provided")
        if verbose:
            print(f"querying arxiv: {query!r}  (max_results={max_results})")
        papers = query_arxiv(query, max_results=max_results)
    if verbose:
        print(f"  -> {len(papers)} papers to process")

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

        # Cache arxiv's author-comment field — many ABM/finance papers put
        # 'code at github.com/...' here rather than in the abstract.
        if p.get("comment") is not None:
            try:
                set_arxiv_comment(db_path, p["arxiv_id"], p["comment"])
            except KeyError:
                pass

        # Attempt to surface a code-repo URL. Cheap: regex over abstract,
        # then comment, then PWC. Skip if already persisted.
        existing_code_url = next(
            (r.get("code_url") for r in before_rows
             if r["arxiv_id"] == p["arxiv_id"] and r.get("code_url")),
            None,
        )
        if not existing_code_url:
            try:
                url, source = resolve_code_url(
                    p["arxiv_id"], p["abstract"], p.get("comment"),
                )
            except (OSError, ValueError, KeyError, TypeError) as e:
                if verbose:
                    print(f"    code_url resolve failed: {type(e).__name__}: {e}")
                url, source = None, None
            if url:
                set_literature_code_url(db_path, p["arxiv_id"],
                                        code_url=url, source=source)
                if verbose:
                    print(f"    code_url ({source}): {url}")

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

        # Groq's gpt-oss-120b free-tier TPM is 8000. Each extraction call
        # uses ~600 input + 200 output = 800 tokens, so ~10 papers/minute
        # is the ceiling. Sleep 6s between successful extractions so we
        # stay under the limit without paying 60s recovery penalties.
        time.sleep(6.0)

    return {
        "query": query, "n_papers_returned": len(papers),
        "n_new_metadata": n_new, "n_extracted": n_extracted,
        "n_skipped_already_extracted": n_skipped,
        "n_dropped_below_relevance": n_dropped,
        "n_errors": len(errors),
        "errors": errors,
        "groq_model": groq_model if extract else None,
    }


def ingest_by_ids(db_path: str, arxiv_ids: list[str], *,
                   extract: bool = True,
                   groq_model: str = DEFAULT_GROQ_MODEL,
                   min_relevance_to_keep: float = 0.0,
                   verbose: bool = True) -> dict:
    """Targeted ingest of an explicit arxiv_id list. Wraps `ingest` with
    pre-fetched metadata so foundational papers (e.g. Katahira-Chen 2019
    = 1909.03185) get into the DB even when they fall outside our broad
    query coverage."""
    if verbose:
        print(f"fetching {len(arxiv_ids)} arxiv id(s)")
    papers = query_arxiv_by_ids(arxiv_ids)
    if verbose:
        print(f"  -> {len(papers)} returned by arxiv "
              f"(missing: {len(arxiv_ids) - len(papers)})")
    return ingest(db_path, papers=papers, extract=extract,
                  groq_model=groq_model,
                  min_relevance_to_keep=min_relevance_to_keep, verbose=verbose)
