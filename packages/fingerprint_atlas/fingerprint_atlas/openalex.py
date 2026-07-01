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

import html
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
_LAST_HTTP_STATUS: int | None = None
_RATE_LIMITED = False
_RATE_LIMITED_AT: float | None = None
# OpenAlex per-minute window is ~60 s. After 90 s of no traffic the lock
# clears itself so a single 429 doesn't kill the rest of the session.
_RATE_LIMIT_COOLDOWN_S = 90.0


def reset_rate_limit() -> None:
    """Public escape hatch for callers who want to force-clear the lock
    (e.g. a canon-atlas retry loop after fixing the query)."""
    global _RATE_LIMITED, _RATE_LIMITED_AT
    _RATE_LIMITED = False
    _RATE_LIMITED_AT = None


class OpenAlexQueryError(RuntimeError):
    """Raised when canon discovery failed rather than returned no matches."""

    def __init__(self, status: int | None):
        self.status = status
        detail = f"HTTP {status}" if status else "network/timeout"
        super().__init__(f"OpenAlex query failed ({detail})")


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
    """One short backoff-retry on 429, then give up. Session-scoped rate
    lock auto-clears after `_RATE_LIMIT_COOLDOWN_S` so a single 429 does
    not permanently block the session."""
    global _LAST_HTTP_STATUS, _RATE_LIMITED, _RATE_LIMITED_AT
    if _RATE_LIMITED and _RATE_LIMITED_AT is not None:
        if time.time() - _RATE_LIMITED_AT >= _RATE_LIMIT_COOLDOWN_S:
            _RATE_LIMITED = False
            _RATE_LIMITED_AT = None
        else:
            _LAST_HTTP_STATUS = 429
            return None
    status, body = _http_get_json_with_status(url, timeout)
    if status == 429:
        time.sleep(5.0)
        status, body = _http_get_json_with_status(url, timeout)
        if status == 429:
            _RATE_LIMITED = True
            _RATE_LIMITED_AT = time.time()
    _LAST_HTTP_STATUS = status
    return body if status == 200 else None


def _http_get_text(url: str, timeout: float = _OA_TIMEOUT) -> str | None:
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            UnicodeDecodeError, OSError):
        return None


# ----- single-paper enrichment -------------------------------------------

def _arxiv_doi(arxiv_id: str) -> str:
    """arxiv assigns a DOI like '10.48550/arXiv.<base_id>' to every paper.
    OpenAlex indexes by this canonical DOI, so we can look any arxiv
    paper up without round-tripping through their search endpoint."""
    return f"10.48550/arXiv.{_arxiv_base(arxiv_id)}"


def _normalise_work(raw: dict) -> dict:
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


def _old_style_arxiv_metadata(arxiv_id: str) -> tuple[str | None, str | None]:
    """Return (title, journal DOI) from an old-style arXiv abstract page."""
    aid = urllib.parse.quote(_arxiv_base(arxiv_id), safe="/")
    body = _http_get_text(f"https://arxiv.org/abs/{aid}")
    if not body:
        return None, None

    def meta(name: str) -> str | None:
        match = re.search(
            rf'<meta\s+name=["\']{re.escape(name)}["\']\s+'
            rf'content=["\']([^"\']+)["\']',
            body,
            flags=re.IGNORECASE,
        )
        return html.unescape(match.group(1)).strip() if match else None

    return meta("citation_title"), meta("citation_doi")


def _fetch_work_by_title(title: str) -> dict | None:
    query = urllib.parse.quote(f'"{title[:200]}"', safe="")
    select = (
        "id,title,publication_year,cited_by_count,concepts,"
        "referenced_works,open_access,doi"
    )
    url = (f"{_OA_BASE}/works?filter=display_name.search:{query}"
           f"&sort=cited_by_count:desc&per-page=5&select={select}")
    raw = _http_get_json(url)
    if not raw or not isinstance(raw.get("results"), list):
        return None
    target = re.sub(r"\W+", " ", title).strip().casefold()
    for work in raw["results"]:
        candidate = re.sub(
            r"\W+", " ", work.get("title") or ""
        ).strip().casefold()
        if candidate == target:
            return work
    return None


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
    base_id = _arxiv_base(arxiv_id)
    if "/" in base_id:
        title, journal_doi = _old_style_arxiv_metadata(base_id)
        if journal_doi:
            url = f"{_OA_BASE}/works/doi:{urllib.parse.quote(journal_doi)}"
            raw = _http_get_json(url)
            if raw and isinstance(raw, dict):
                return _normalise_work(raw)
        if title:
            raw = _fetch_work_by_title(title)
            if raw:
                return _normalise_work(raw)

    url = f"{_OA_BASE}/works/doi:{urllib.parse.quote(_arxiv_doi(base_id))}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw, dict):
        return None
    return _normalise_work(raw)


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
      (a) If `query_or_concept` is an explicit OpenAlex concept id
          (CXXXXX or full URI), filter by that concept.
      (b) Otherwise use exact-phrase title/abstract search.

    Natural-language queries are deliberately not auto-resolved to concepts.
    OpenAlex's concept search often returns a broader first result (for
    example "game" for "Minority game"), silently polluting canon results.

    Each entry: {oa_paper_id, arxiv_id, title, year, cited_by_count, doi}.
    """
    global _LAST_HTTP_STATUS
    _LAST_HTTP_STATUS = None
    concept_id: str | None = None
    if "/" in query_or_concept or query_or_concept.startswith("C"):
        m = re.search(r"(C\d+)", query_or_concept)
        if m:
            concept_id = m.group(1)

    select = "id,title,publication_year,cited_by_count,ids,doi,locations"
    n_per_page = min(n, 200)

    # Build filter clauses with literal ',' ':' '>' '=' — OpenAlex's
    # filter parser splits on the literal comma between clauses, so
    # urlencode'ing them to %2C / %3A breaks it. We URL-encode only the
    # search VALUES (which may contain spaces, '&', '?', etc), not the
    # filter syntax.
    if concept_id:
        filter_clauses = [f"concepts.id:{concept_id}"]
        if year_max is not None:
            filter_clauses.append(f"publication_year:<={year_max}")
    else:
        # title_and_abstract.search defaults to OR'd word matching ('minority
        # game' matches every paper with 'minority' OR 'game' anywhere).
        # Wrap the query in double quotes to force exact-phrase matching —
        # 'Minority game' becomes the literal phrase, dropping racial-
        # minorities / gaming-addiction / etc noise. Combine with a
        # citation floor (>9) to also kill low-impact phrase hits.
        phrase = f'"{query_or_concept}"'
        q_safe = urllib.parse.quote(phrase, safe="")
        filter_clauses = [f"title_and_abstract.search:{q_safe}",
                           "cited_by_count:>9"]
        if year_max is not None:
            filter_clauses.append(f"publication_year:<={year_max}")

    url = (f"{_OA_BASE}/works?filter={','.join(filter_clauses)}"
           f"&sort=cited_by_count:desc&per-page={n_per_page}&select={select}")
    raw = _http_get_json(url)
    if raw is None:
        raise OpenAlexQueryError(_LAST_HTTP_STATUS)

    # Retry fallback: title_and_abstract.search filter is occasionally
    # absent / mis-parsed for very narrow queries. Plain ?search= with a
    # citation-floor filter is a more lenient last resort.
    if not concept_id and (not raw or not raw.get("results")):
        q_safe = urllib.parse.quote(query_or_concept, safe="")
        retry_filter = "cited_by_count:>9"
        if year_max is not None:
            retry_filter += f",publication_year:<={year_max}"
        url = (f"{_OA_BASE}/works?search={q_safe}"
               f"&filter={retry_filter}"
               f"&per-page={n_per_page}&select={select}")
        raw = _http_get_json(url)
        if raw is None:
            raise OpenAlexQueryError(_LAST_HTTP_STATUS)

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


def _top_concept_id_from_seed(seed: str,
                                skip_concepts: set[str] | None = None
                                ) -> tuple[str, str] | None:
    """Given a seed paper, resolve it via direct DOI/ID lookup (NO search=)
    and return its highest-scoring OpenAlex concept as (concept_id,
    display_name). None if the seed can't be resolved.

    `seed` accepts three forms:
      - arxiv id, e.g. 'adap-org/9708006' or '1909.03185'
      - OpenAlex W-id, e.g. 'W1537415400' (for journal-only papers with
        no arxiv preprint — Lux-Marchesi Nature 1999 etc)
      - the 'oa:W…' synthetic prefix used elsewhere in this codebase

    Concept picking:
      - fetch_paper() when arxiv-shaped — resolves arxiv → journal DOI
        for old-style papers, so the concept list comes from the well-
        tagged journal record instead of the sparse arxiv-preprint record
      - direct /works/W… when OA-shaped
      - skip generic, non-discriminative concepts (Computer science /
        Mathematics / Economics / Set (abstract data type) / …) — they
        dominate the top of many OA papers but return unrelated top-cited
        works when used as a filter
      - `skip_concepts` extends this deny-list at call time

    Used as an outage fallback: when `/works?search=…` is 504-ing,
    concept-filter queries (`filter=concepts.id:C…`) still succeed, so
    canon detection can continue by pivoting off a known-good anchor.
    """
    if not seed:
        return None
    # Resolve to a concrete W-id first.
    m_oa = re.match(r"^(?:oa:)?(W\d+)$", seed.strip())
    if m_oa:
        work_id = m_oa.group(1)
    else:
        base_id = _arxiv_base(seed)
        if not base_id:
            return None
        # fetch_paper handles the arxiv → journal-DOI resolution and gives
        # us the canonical OA work id.
        normalised = fetch_paper(base_id)
        if not normalised or not normalised.get("oa_paper_id"):
            return None
        m = re.search(r"(W\d+)", normalised["oa_paper_id"])
        if not m:
            return None
        work_id = m.group(1)
    url = f"{_OA_BASE}/works/{work_id}"
    raw = _http_get_json(url)
    if not raw or not isinstance(raw, dict):
        return None
    concepts = raw.get("concepts") or []
    if not concepts:
        return None
    generic = {
        # discipline-level (OA level 0-1) — too broad to be discriminative
        "Computer science", "Mathematics", "Economics", "Physics",
        "Statistics", "Artificial intelligence", "Data science",
        "Sociology", "Chemistry", "Biology", "Materials science",
        "Engineering", "Political science", "Medicine",
        # broad method families that catch physics papers of every stripe
        "Set (abstract data type)", "Power (physics)", "Simulation",
        "Scaling", "Criticality", "Statistical physics",
        "Molecular dynamics", "Nonlinear system",
        # sub-discipline sinks — still too big to be canon anchors
        "Mathematical economics", "Microeconomics",
        "Management science", "Theoretical computer science",
        "Econometrics", "Financial economics",
    }
    if skip_concepts:
        generic |= skip_concepts
    scored = sorted(
        (c for c in concepts if isinstance(c, dict) and c.get("id")),
        key=lambda c: -c.get("score", 0.0),
    )
    for c in scored:
        name = c.get("display_name") or ""
        if name in generic:
            continue
        cid = re.search(r"(C\d+)", c.get("id") or "")
        if cid:
            return cid.group(1), name
    return None


def find_canon_papers_by_seed(seed: str, *, n: int = 30,
                                year_max: int | None = None
                                ) -> list[dict]:
    """Canon-detection fallback anchored on a known seed paper.

    Path: fetch seed (direct DOI/ID lookup — survives search-endpoint
    outages) → extract its top concept → concept-filter query for the
    top-N most-cited works under that concept. `seed` accepts an arxiv
    id or an OpenAlex W-id (see `_top_concept_id_from_seed`).
    """
    global _LAST_HTTP_STATUS
    _LAST_HTTP_STATUS = None
    resolved = _top_concept_id_from_seed(seed)
    if resolved is None:
        raise OpenAlexQueryError(_LAST_HTTP_STATUS)
    concept_id, _concept_name = resolved

    select = "id,title,publication_year,cited_by_count,ids,doi,locations"
    filter_clauses = [f"concepts.id:{concept_id}", "cited_by_count:>9"]
    if year_max is not None:
        filter_clauses.append(f"publication_year:<={year_max}")
    url = (f"{_OA_BASE}/works?filter={','.join(filter_clauses)}"
           f"&sort=cited_by_count:desc&per-page={min(n, 200)}&select={select}")
    raw = _http_get_json(url)
    if raw is None:
        raise OpenAlexQueryError(_LAST_HTTP_STATUS)
    out: list[dict] = []
    for work in (raw.get("results") or [])[:n]:
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


# ----- canon ingestion (full metadata from OA work id) ------------------

def _reconstruct_abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index:
       {word: [positions_in_text]}.
    Reconstruct by placing each word at its position. Returns '' for
    works without an indexed abstract (~10% of works).
    """
    if not inverted or not isinstance(inverted, dict):
        return ""
    pos_words: list[tuple[int, str]] = []
    for word, positions in inverted.items():
        if not isinstance(positions, list):
            continue
        for p in positions:
            try:
                pos_words.append((int(p), word))
            except (TypeError, ValueError):
                continue
    pos_words.sort()
    return " ".join(w for _, w in pos_words)


def fetch_work_full(oa_id: str) -> dict | None:
    """Fetch one OpenAlex work and return rich metadata suitable for
    inserting into literature_methods as a canon row.

    Returns:
      {oa_paper_id, title, authors (str), year, published_date, doi,
       abstract (reconstructed), cited_by_count, concepts (list[str]),
       primary_category (None — OA doesn't have arxiv categories)}
    or None on a hard miss.
    """
    m = re.search(r"(W\d+)", oa_id)
    if not m:
        return None
    work_id = m.group(1)
    select = ("id,title,publication_year,publication_date,cited_by_count,"
              "concepts,authorships,abstract_inverted_index,doi,locations")
    url = (f"{_OA_BASE}/works/{work_id}"
           f"?select={urllib.parse.quote(select)}")
    raw = _http_get_json(url)
    if not raw or not isinstance(raw, dict):
        return None
    authors: list[str] = []
    for a in (raw.get("authorships") or [])[:25]:
        name = ((a or {}).get("author") or {}).get("display_name")
        if name:
            authors.append(name)
    concepts: list[str] = []
    for c in (raw.get("concepts") or [])[:5]:
        if isinstance(c, dict) and c.get("display_name"):
            concepts.append(c["display_name"])
    return {
        "oa_paper_id": raw.get("id"),
        "title": raw.get("title"),
        "authors": ", ".join(authors),
        "year": raw.get("publication_year"),
        "published_date": raw.get("publication_date"),
        "doi": raw.get("doi"),
        "abstract": _reconstruct_abstract(raw.get("abstract_inverted_index")),
        "cited_by_count": raw.get("cited_by_count"),
        "concepts": concepts,
        "arxiv_id": _arxiv_id_from_work(raw),
    }


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
