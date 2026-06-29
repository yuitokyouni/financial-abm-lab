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

    Two-stage search:
      1) /concepts?search=...  (canonical, fast)
      2) /works?search=... then aggregate concepts from the top results
         (robust to /concepts deprecation / sparse topics)

    OpenAlex started transitioning from 'concepts' to 'topics' in 2024,
    so some subfields (esp. niche / mid-sized ones like 'Minority game')
    return empty from /concepts but still appear as a tag on /works
    results. Stage 2 catches those."""
    target = concept_name.lower().strip()

    # Stage 1: direct /concepts lookup.
    q = urllib.parse.quote(concept_name)
    url = f"{_OA_BASE}/concepts?search={q}&per-page=10"
    raw = _http_get_json(url)
    if raw and isinstance(raw.get("results"), list) and raw["results"]:
        for c in raw["results"]:
            if (c.get("display_name") or "").lower().strip() == target:
                return c.get("id")
        # Soft match: substring containment in either direction
        for c in raw["results"]:
            cname = (c.get("display_name") or "").lower().strip()
            if cname and (target in cname or cname in target):
                return c.get("id")
        # Worst case: take first result if /concepts had ANY hits
        return raw["results"][0].get("id")

    # Stage 2: search /works and harvest the concepts attached to top results.
    # More robust because most actual concept-tagging now happens at the
    # works level, regardless of whether /concepts surfaces the taxonomy entry.
    from collections import Counter
    qs = urllib.parse.urlencode({
        "search": concept_name, "per-page": 20, "select": "concepts",
    })
    url = f"{_OA_BASE}/works?{qs}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list):
        return None
    matches: Counter = Counter()
    for work in raw["results"]:
        for c in (work.get("concepts") or []):
            cname = (c.get("display_name") or "").lower().strip()
            cid = c.get("id")
            if not cid or not cname:
                continue
            # weight by both the concept's relevance in this work AND
            # how often it appears across top-K works
            if target == cname:
                matches[(cid, c["display_name"])] += 5
            elif target in cname or cname in target:
                matches[(cid, c["display_name"])] += 2
    if matches:
        (best_id, _), _ = matches.most_common(1)[0]
        return best_id
    return None


def find_canon_papers(query_or_concept: str, *, n: int = 30,
                       year_max: int | None = None) -> list[dict]:
    """Top-N highest-cited papers about a topic.

    Two resolution paths:
      (a) If `query_or_concept` is an OpenAlex concept id (CXXXXX or full
          URI), or find_concept_id resolves the name to one, filter
          /works by `concepts.id:`.
      (b) Otherwise (fine-grained subfields like 'Minority game' that
          aren't first-class OpenAlex concepts), fall back to direct
          search `/works?search=...` and sort by cited_by_count.

    Path (b) is more reliable for narrow subfields — OpenAlex's concept
    taxonomy is coarse (it has 'Stochastic game' but not 'Minority game')
    while its title/abstract search reaches every paper.

    Each entry: {oa_paper_id, arxiv_id, title, year, cited_by_count, doi}.
    """
    concept_id: str | None = None
    if "/" in query_or_concept or query_or_concept.startswith("C"):
        m = re.search(r"(C\d+)", query_or_concept)
        if m:
            concept_id = m.group(1)
    else:
        full = find_concept_id(query_or_concept)
        if full:
            m = re.search(r"(C\d+)", full)
            if m:
                concept_id = m.group(1)

    params = {
        "sort": "cited_by_count:desc",
        "per-page": min(n, 200),
        "select": "id,title,publication_year,cited_by_count,ids,doi,locations",
    }
    if concept_id:
        filt = [f"concepts.id:{concept_id}"]
        if year_max is not None:
            filt.append(f"publication_year:<={year_max}")
        params["filter"] = ",".join(filt)
    else:
        # Fallback path: direct search over title/abstract — works for
        # subfields too narrow to have their own OpenAlex concept.
        params["search"] = query_or_concept
        if year_max is not None:
            params["filter"] = f"publication_year:<={year_max}"

    qs = urllib.parse.urlencode(params)
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
