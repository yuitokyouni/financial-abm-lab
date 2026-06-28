"""code_links — surface a code-repo URL for an arxiv paper.

Two stages, cheapest first:

1. `extract_github_from_text(text)`  — pure regex over the abstract; many
   recent LLM-agent / mechanism papers paste a `github.com/<org>/<repo>`
   URL right into the abstract. No network.

2. `fetch_pwc_repo(arxiv_id)`        — Papers with Code public API. Free,
   no auth. Returns the first linked repo URL or None. ~1 HTTP round trip.

Call site (arxiv_ingest) does `extract_github_from_text` first, falls back
to `fetch_pwc_repo` only when the abstract didn't expose anything.

Both helpers are best-effort: any failure (network down, malformed JSON,
unknown arxiv id) returns None instead of raising. The caller decides
whether to log it.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request


# Match github.com URLs; tolerate query strings / trailing punctuation /
# parens / closing brackets. We only keep the org/repo segment.
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9][A-Za-z0-9._\-]*)/([A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,;:)]}>\"'"


def extract_github_from_text(text: str | None) -> str | None:
    """Return the first canonical github.com/<org>/<repo> URL in `text`.

    Strips trailing punctuation / closing brackets that often follow URLs
    in prose. Drops `.git` suffix so we get a clean web URL.
    """
    if not text:
        return None
    m = _GITHUB_URL_RE.search(text)
    if not m:
        return None
    org, repo = m.group(1), m.group(2)
    # Strip trailing junk from the repo segment (regex char class is
    # permissive; explicit cleanup avoids URLs like `repo).`).
    while repo and repo[-1] in _TRAILING_PUNCT:
        repo = repo[:-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not repo:
        return None
    return f"https://github.com/{org}/{repo}"


_PWC_PAPERS_URL = "https://paperswithcode.com/api/v1/papers/"
_PWC_TIMEOUT = 10.0
_USER_AGENT = "fingerprint-atlas/0.1 (+https://github.com/yuitokyouni/financial-abm-lab)"


def _http_get_json(url: str, timeout: float = _PWC_TIMEOUT) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT,
                                                "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, json.JSONDecodeError, OSError):
        return None


def _arxiv_id_base(arxiv_id: str) -> str:
    """Drop the trailing version suffix ('v2') if any. PWC indexes the
    base id."""
    return re.sub(r"v\d+$", "", arxiv_id)


def fetch_pwc_repo(arxiv_id: str) -> str | None:
    """Query Papers with Code for repo(s) linked to this arxiv id; return
    the first repo URL or None.

    PWC schema (v1):
      GET /api/v1/papers/?arxiv_id=<id>  → {"results": [{"id": "...", ...}]}
      GET /api/v1/papers/<paper_id>/repositories/
                                          → {"results": [{"url": "...", ...}]}
    """
    base = _arxiv_id_base(arxiv_id)
    q = urllib.parse.urlencode({"arxiv_id": base})
    listing = _http_get_json(f"{_PWC_PAPERS_URL}?{q}")
    if not listing or not listing.get("results"):
        return None
    paper_id = listing["results"][0].get("id")
    if not paper_id:
        return None
    repos = _http_get_json(f"{_PWC_PAPERS_URL}{urllib.parse.quote(paper_id)}/repositories/")
    if not repos or not repos.get("results"):
        return None
    url = repos["results"][0].get("url")
    if not url:
        return None
    return url.rstrip("/")


def resolve_code_url(arxiv_id: str, abstract: str | None) -> tuple[str | None, str | None]:
    """Convenience: try abstract → PWC. Return (url, source) where source is
    'abstract' / 'pwc' / None."""
    url = extract_github_from_text(abstract)
    if url:
        return url, "abstract"
    url = fetch_pwc_repo(arxiv_id)
    if url:
        return url, "pwc"
    return None, None
