"""semantic_scholar — Semantic Scholar API integration.

Two roles in the pipeline:

1. **Enrich**: for every paper already in literature_methods, fetch:
   - paperId (S2's stable internal id; useful as a key in their other APIs)
   - tldr (1-3 sentence auto-summary; often clearer than the abstract for
     dense papers, and free to inject into LLM context)
   - influentialCitationCount (S2's curated impact metric)
   - openAccessPdf, externalIds (for finding linked code or alternative
     hosts beyond github)

2. **Expand**: walk the references of each paper to discover related
   arxiv-hosted prior work that broad-query passes miss. KineticSim
   references Cont 2001; Katahira 2019 references Challet 1997. Useful
   for pulling the foundational layer up into the corpus.

S2 free tier limits: ~100 requests / 5 minutes unauthenticated, lifted
significantly with an API key (header `x-api-key`, optional env var
SEMANTIC_SCHOLAR_API_KEY). All helpers are best-effort: any error
(network, 4xx, 5xx, malformed JSON) returns None instead of raising.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request


_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_TIMEOUT = 15.0
_USER_AGENT = "fingerprint-atlas/0.1 (+https://github.com/yuitokyouni/financial-abm-lab)"
_RATE_LIMIT_BACKOFF = 12.0  # seconds to wait on 429 before one retry


def _arxiv_base(arxiv_id: str) -> str:
    """Strip 'vN' suffix and any leading whitespace."""
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def _http_get_json_with_status(url: str, timeout: float = _S2_TIMEOUT
                                ) -> tuple[int | None, dict | None]:
    """Return (status_code, parsed_json_or_None). status_code is None on
    network failure / timeout (no HTTP response was received).

    Behaviour vs the legacy _http_get_json: this version distinguishes
    404 (paper genuinely not on S2) from 429 (rate-limit hit, should
    retry) from 500/503 (transient server issue) from network timeout.
    All produce parsed=None, but the status code lets the caller decide
    whether to backoff + retry, log a real miss, or surface a fatal."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return resp.status, None
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError,
            json.JSONDecodeError, OSError):
        return None, None


def _http_get_json(url: str, timeout: float = _S2_TIMEOUT) -> dict | None:
    """Convenience wrapper that retries once on 429. Returns the parsed
    JSON object, or None on any non-200 / network failure / parse error.

    The 12-second backoff is conservative — S2 free tier's rolling
    window is 5 minutes, but a single 12s pause is usually enough to
    clear a transient burst-limit hit."""
    status, body = _http_get_json_with_status(url, timeout)
    if status == 429:
        time.sleep(_RATE_LIMIT_BACKOFF)
        status, body = _http_get_json_with_status(url, timeout)
    return body if status == 200 else None


# ----- single-paper enrichment -------------------------------------------

_PAPER_FIELDS = ",".join((
    "paperId", "title", "year", "abstract",
    "citationCount", "influentialCitationCount",
    "tldr", "externalIds", "openAccessPdf",
))


def fetch_paper(arxiv_id: str) -> dict | None:
    """Look up a paper by arxiv id and return S2's view.

    Returned dict shape (None on miss):
      {
        "s2_paper_id": str, "title": str, "year": int,
        "tldr": str | None,
        "citation_count": int, "influential_citation_count": int,
        "external_ids": {"DOI": ..., "DBLP": ..., ...},
        "open_access_pdf": str | None,
      }
    """
    base = _arxiv_base(arxiv_id)
    url = (f"{_S2_BASE}/paper/ARXIV:{urllib.parse.quote(base)}"
           f"?fields={_PAPER_FIELDS}")
    raw = _http_get_json(url)
    if not raw:
        return None
    tldr_obj = raw.get("tldr") or {}
    openpdf = raw.get("openAccessPdf") or {}
    return {
        "s2_paper_id": raw.get("paperId"),
        "title": raw.get("title"),
        "year": raw.get("year"),
        "tldr": tldr_obj.get("text") if isinstance(tldr_obj, dict) else None,
        "citation_count": raw.get("citationCount"),
        "influential_citation_count": raw.get("influentialCitationCount"),
        "external_ids": raw.get("externalIds") or {},
        "open_access_pdf": openpdf.get("url") if isinstance(openpdf, dict) else None,
    }


# ----- reference walking -------------------------------------------------

_REF_FIELDS = ",".join((
    "paperId", "title", "year", "externalIds",
    "citationCount", "influentialCitationCount",
))
_REFS_PAGE_LIMIT = 100  # S2 caps each page at 100


def fetch_references(arxiv_id: str, *, limit: int = 100) -> list[dict]:
    """Return up to `limit` references of a paper, each shaped as:
      {"s2_paper_id": str, "title": str, "year": int|None,
       "arxiv_id": str|None,           # only if the ref is on arxiv
       "doi": str|None,
       "citation_count": int|None,
       "influential_citation_count": int|None}
    Empty list on any failure."""
    base = _arxiv_base(arxiv_id)
    page_size = min(limit, _REFS_PAGE_LIMIT)
    url = (f"{_S2_BASE}/paper/ARXIV:{urllib.parse.quote(base)}/references"
           f"?fields={_REF_FIELDS}&limit={page_size}")
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("data"), list):
        return []
    out: list[dict] = []
    for entry in raw["data"]:
        # API shape: {"contextsWithIntent": [...], "citedPaper": {...}}
        cited = entry.get("citedPaper") or {}
        if not cited:
            continue
        ext = cited.get("externalIds") or {}
        out.append({
            "s2_paper_id": cited.get("paperId"),
            "title": cited.get("title"),
            "year": cited.get("year"),
            "arxiv_id": ext.get("ArXiv"),  # base id, no version
            "doi": ext.get("DOI"),
            "citation_count": cited.get("citationCount"),
            "influential_citation_count": cited.get("influentialCitationCount"),
        })
    return out


# ----- batch helpers (rate-limited) --------------------------------------

# Unauthenticated S2 is ~100 req / 5 min. With a 4s sleep between calls
# we land at ~75/5min — comfortable headroom.
_DEFAULT_SLEEP = 4.0


def sleep_for_rate_limit(seconds: float | None = None) -> None:
    """Single point of control for S2 inter-request pacing. Tests
    monkeypatch this to skip the wait."""
    time.sleep(_DEFAULT_SLEEP if seconds is None else seconds)
