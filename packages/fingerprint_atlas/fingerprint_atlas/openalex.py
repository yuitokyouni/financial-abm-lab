"""openalex — OpenAlex API integration.

Drop-in alternative to semantic_scholar for users who don't have an S2
API key. OpenAlex requires no auth, allows 10 req/sec, and has 100k
req/day per IP — practically unlimited for our use case. They ask for a
'polite email' in the User-Agent / mailto query param; we send the repo
URL instead.

Mapping to our DB columns:

  oa_paper_id            ← work.id (canonical OpenAlex URI)
  oa_cited_by_count      ← work.cited_by_count
  oa_concepts            ← top 3 concept display_names, comma-joined

Reference graph: work.referenced_works is a list of OpenAlex IDs, not
arxiv IDs. To find which references are on arxiv, we batch-fetch each
referenced work and read its ids.openalex / ids.doi / locations[].
That's slightly more wire traffic than S2's direct arxiv_id field, but
still well under the rate limit.

Everything is best-effort: any error (network, 4xx, 5xx, malformed JSON)
returns None / empty list instead of raising.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request


_OA_BASE = "https://api.openalex.org"
_OA_TIMEOUT = 15.0
_POLITE_MAILTO = "yuitokyouni+oa@gmail.com"  # OpenAlex etiquette param
_USER_AGENT = "fingerprint-atlas/0.1 (mailto:" + _POLITE_MAILTO + ")"


def _arxiv_base(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.strip())


def _http_get_json_with_status(url: str, timeout: float = _OA_TIMEOUT
                                ) -> tuple[int | None, dict | None]:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
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


def _http_get_json(url: str, timeout: float = _OA_TIMEOUT) -> dict | None:
    """One short backoff-retry on 429, then give up. OpenAlex's free tier
    is generous enough that this is rarely triggered."""
    status, body = _http_get_json_with_status(url, timeout)
    if status == 429:
        time.sleep(5.0)
        status, body = _http_get_json_with_status(url, timeout)
    return body if status == 200 else None


# ----- single-paper enrichment -------------------------------------------

def _arxiv_doi(arxiv_id: str) -> str:
    """arxiv assigns a DOI like '10.48550/arXiv.<base_id>' to every paper.
    OpenAlex indexes by this canonical DOI, so we can look any arxiv
    paper up without round-tripping through their search endpoint."""
    return f"10.48550/arXiv.{_arxiv_base(arxiv_id)}"


def fetch_paper(arxiv_id: str) -> dict | None:
    """Return normalised OpenAlex view of one paper, or None on miss.

    Shape:
      {
        "oa_paper_id": str,         # OpenAlex URI
        "title": str,
        "year": int,
        "cited_by_count": int,
        "concepts": list[str],       # top concept display_names
        "referenced_works": list[str],  # OpenAlex IDs (NOT arxiv ids)
        "open_access_pdf": str | None,
        "doi": str | None,
      }
    """
    url = f"{_OA_BASE}/works/doi:{urllib.parse.quote(_arxiv_doi(arxiv_id))}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw, dict):
        return None
    concepts = raw.get("concepts") or []
    concept_names = [c.get("display_name") for c in concepts[:5]
                      if isinstance(c, dict) and c.get("display_name")]
    oa = raw.get("open_access") or {}
    return {
        "oa_paper_id": raw.get("id"),
        "title": raw.get("title"),
        "year": raw.get("publication_year"),
        "cited_by_count": raw.get("cited_by_count"),
        "concepts": concept_names,
        "referenced_works": raw.get("referenced_works") or [],
        "open_access_pdf": oa.get("oa_url") if isinstance(oa, dict) else None,
        "doi": raw.get("doi"),
    }


# ----- concept search + canon detection ----------------------------------

def find_concept_id(concept_name: str) -> str | None:
    """Look up the OpenAlex concept id (e.g. 'C2779489203') for a display
    name like 'Minority game'. Returns None if no match.

    OpenAlex's concept taxonomy auto-tags every work — so this gives us a
    way to find papers thematically related to a topic, separate from any
    citation graph we have."""
    q = urllib.parse.quote(concept_name)
    url = f"{_OA_BASE}/concepts?search={q}&per-page=5"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list) or not raw["results"]:
        return None
    # Pick the closest title match (case-insensitive)
    target = concept_name.lower().strip()
    for c in raw["results"]:
        if (c.get("display_name") or "").lower().strip() == target:
            return c.get("id")
    # Fallback: take the first result
    return raw["results"][0].get("id")


def find_canon_papers(concept_id_or_name: str, *, n: int = 30,
                       year_max: int | None = None) -> list[dict]:
    """Top-N highest-cited papers under an OpenAlex concept.

    Pass either the OpenAlex concept id ('C2779489203' or
    'https://openalex.org/C2779489203') or a display name ('Minority game')
    which we'll resolve via find_concept_id.

    Each entry: {oa_paper_id, arxiv_id (if any), title, year, cited_by_count,
    doi, abstract_inverted_index}. arxiv_id is None for journal-only papers
    we can't ingest via the arxiv API."""
    # Resolve display name to concept id if needed
    if "/" in concept_id_or_name or concept_id_or_name.startswith("C"):
        m = re.search(r"(C\d+)", concept_id_or_name)
        concept_id = m.group(1) if m else None
    else:
        full = find_concept_id(concept_id_or_name)
        m = re.search(r"(C\d+)", full or "")
        concept_id = m.group(1) if m else None
    if not concept_id:
        return []
    f = [f"concepts.id:{concept_id}"]
    if year_max is not None:
        f.append(f"publication_year:<={year_max}")
    qs = urllib.parse.urlencode({
        "filter": ",".join(f),
        "sort": "cited_by_count:desc",
        "per-page": min(n, 200),
        "select": "id,title,publication_year,cited_by_count,ids,doi,locations",
    })
    url = f"{_OA_BASE}/works?{qs}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list):
        return []
    out: list[dict] = []
    for work in raw["results"][:n]:
        out.append({
            "oa_paper_id": work.get("id"),
            "arxiv_id": _arxiv_id_from_work(work),
            "title": work.get("title"),
            "year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count"),
            "doi": work.get("doi"),
        })
    return out


# ----- title search ------------------------------------------------------

def search_by_title(title: str, year: int | None = None) -> dict | None:
    """Look a paper up on OpenAlex by title, return its canonical arxiv_id.

    Use case: a row whose arxiv_id was stored in a broken form (e.g. old
    category-prefix stripped). We still have the title in DB, so this
    pulls the right work back. `year` (when provided) disambiguates
    similarly-titled papers.

    Returns {oa_paper_id, arxiv_id, doi} or None on miss."""
    if not title:
        return None
    q = urllib.parse.quote(title[:200])
    url = f"{_OA_BASE}/works?search={q}&per_page=3"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list) or not raw["results"]:
        return None
    for work in raw["results"]:
        if year and work.get("publication_year") != year:
            continue
        arxiv_id = _arxiv_id_from_work(work)
        if arxiv_id:
            return {
                "oa_paper_id": work.get("id"),
                "arxiv_id": arxiv_id,
                "doi": work.get("doi"),
                "title": work.get("title"),
                "year": work.get("publication_year"),
            }
    return None


def _arxiv_id_from_work(work: dict) -> str | None:
    """Extract arxiv_id (incl. old-style category prefix) from an OpenAlex
    work payload — checks ids.arxiv first, falls back to locations[]."""
    if not isinstance(work, dict):
        return None
    ids = work.get("ids") or {}
    if "arxiv" in ids and isinstance(ids["arxiv"], str):
        m = re.search(r"(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})", ids["arxiv"])
        if m:
            return m.group(1)
    for loc in (work.get("locations") or []):
        url_field = (loc or {}).get("landing_page_url", "") or ""
        m = re.search(r"arxiv\.org/abs/(\S+)", url_field)
        if m:
            aid = m.group(1).rstrip("/")
            # strip version suffix to match the rest of the codebase's
            # base-id convention
            return re.sub(r"v\d+$", "", aid)
    return None


# ----- forward citation (papers that cite this one) ---------------------

def find_citing_papers(oa_paper_id: str, *, n: int = 50,
                        year_max: int | None = None,
                        min_cited_by: int = 0) -> list[dict]:
    """Return up to N papers that CITE the given OpenAlex work, sorted by
    their own cited_by_count (so the most influential descendants surface
    first). The 'forward' direction of the citation graph — opposite of
    fetch_references.

    Unlike referenced_works (which OpenAlex has empty for most arxiv
    preprints), the inverted index here is built from any work that
    contributes references, so coverage is much higher for canonical
    works."""
    # Accept either 'W12345' bare id or full 'https://openalex.org/W12345'
    m = re.search(r"(W\d+)", oa_paper_id)
    if not m:
        return []
    work_id = m.group(1)
    f = [f"cites:{work_id}"]
    if year_max is not None:
        f.append(f"publication_year:<={year_max}")
    if min_cited_by > 0:
        f.append(f"cited_by_count:>={min_cited_by}")
    qs = urllib.parse.urlencode({
        "filter": ",".join(f),
        "sort": "cited_by_count:desc",
        "per-page": min(n, 200),
        "select": ("id,title,publication_year,cited_by_count,ids,doi,"
                   "locations,concepts"),
    })
    url = f"{_OA_BASE}/works?{qs}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list):
        return []
    out: list[dict] = []
    for work in raw["results"][:n]:
        concepts = []
        for c in (work.get("concepts") or [])[:3]:
            if isinstance(c, dict) and c.get("display_name"):
                concepts.append(c["display_name"])
        out.append({
            "oa_paper_id": work.get("id"),
            "arxiv_id": _arxiv_id_from_work(work),
            "title": work.get("title"),
            "year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count"),
            "doi": work.get("doi"),
            "concepts": concepts,
        })
    return out


# ----- reference walking -------------------------------------------------

_OA_WORK_FIELDS = (
    "id,title,publication_year,cited_by_count,ids,locations"
)


def _resolve_oa_work(oa_id: str) -> dict | None:
    """Fetch one OpenAlex work by its OA URI. Returns the arxiv id if any."""
    # oa_id looks like 'https://openalex.org/W1234567890' — extract the W… part.
    m = re.search(r"(W\d+)", oa_id)
    if not m:
        return None
    work_id = m.group(1)
    url = (f"{_OA_BASE}/works/{work_id}"
           f"?select={urllib.parse.quote(_OA_WORK_FIELDS)}")
    raw = _http_get_json(url)
    if not raw or not isinstance(raw, dict):
        return None
    return {
        "oa_paper_id": raw.get("id"),
        "title": raw.get("title"),
        "year": raw.get("publication_year"),
        "cited_by_count": raw.get("cited_by_count"),
        "arxiv_id": _arxiv_id_from_work(raw),
    }


def fetch_references(arxiv_id: str, *, limit: int = 100,
                      sleep: float = 0.1) -> list[dict]:
    """Walk a paper's referenced_works, resolving each to find arxiv_ids.

    Heavier than S2 (one extra round trip per referenced work) but still
    bounded by limit. Returns list of:
      {"oa_paper_id": str, "title": str, "year": int|None,
       "arxiv_id": str|None, "cited_by_count": int|None}
    """
    paper = fetch_paper(arxiv_id)
    if not paper:
        return []
    refs = paper["referenced_works"][:limit]
    out: list[dict] = []
    for oa_id in refs:
        resolved = _resolve_oa_work(oa_id)
        if resolved:
            out.append(resolved)
        if sleep:
            time.sleep(sleep)
    return out


# ----- pacing helper -----------------------------------------------------

_DEFAULT_SLEEP = 0.5  # 2 req/s — well under OpenAlex's 10 req/s cap


def sleep_for_rate_limit(seconds: float | None = None) -> None:
    time.sleep(_DEFAULT_SLEEP if seconds is None else seconds)
