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
import os
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


# ----- repo snapshot (README + top-level file list) ----------------------

_README_CANDIDATES = (
    "README.md", "Readme.md", "readme.md",
    "README.rst", "README", "README.txt",
)
_GH_BRANCHES = ("HEAD", "main", "master")
_README_MAX_CHARS = 3000
_FILE_TREE_MAX_ENTRIES = 80


def _parse_github_url(code_url: str) -> tuple[str, str] | None:
    """Split https://github.com/<org>/<repo>(.git)? → (org, repo)."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(\.git)?/?$",
                 code_url.strip(), re.IGNORECASE)
    if not m:
        return None
    return m.group(1), m.group(2)


def _http_get_text(url: str, timeout: float = _PWC_TIMEOUT,
                   extra_headers: dict | None = None) -> str | None:
    headers = {"User-Agent": _USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, OSError):
        return None


def _fetch_readme(org: str, repo: str) -> str | None:
    """Try README candidates across HEAD/main/master via raw.githubusercontent."""
    for branch in _GH_BRANCHES:
        for name in _README_CANDIDATES:
            url = f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{name}"
            txt = _http_get_text(url)
            if txt:
                return txt[:_README_MAX_CHARS]
    return None


def _fetch_file_tree(org: str, repo: str) -> list[str] | None:
    """List top-level entries via GitHub Contents API (no auth needed for
    public repos; 60 req/hr unauth, or 5000/hr with GITHUB_TOKEN env)."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{org}/{repo}/contents/"
    body = _http_get_text(url, extra_headers=headers)
    if not body:
        return None
    try:
        items = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list):
        return None
    out: list[str] = []
    for it in items[:_FILE_TREE_MAX_ENTRIES]:
        name = it.get("name")
        typ = it.get("type")
        if name and typ:
            out.append(f"{name}/" if typ == "dir" else name)
    return out


def fetch_repo_snapshot(code_url: str) -> dict:
    """Return {readme_excerpt, file_tree, status, error_msg}. Best-effort:
    network failures don't raise, they degrade status to 'error'."""
    parts = _parse_github_url(code_url)
    if not parts:
        return {"readme_excerpt": None, "file_tree": None,
                "status": "error", "error_msg": "not a github URL"}
    org, repo = parts
    try:
        readme = _fetch_readme(org, repo)
        tree = _fetch_file_tree(org, repo)
    except Exception as exc:
        return {"readme_excerpt": None, "file_tree": None,
                "status": "error", "error_msg": str(exc)[:200]}
    tree_str = "\n".join(tree) if tree else None
    if readme:
        return {"readme_excerpt": readme, "file_tree": tree_str,
                "status": "ok", "error_msg": None}
    if tree_str:
        # No README but we got the tree — still useful structure signal.
        return {"readme_excerpt": None, "file_tree": tree_str,
                "status": "no_readme", "error_msg": None}
    return {"readme_excerpt": None, "file_tree": None,
            "status": "error", "error_msg": "no README and no tree fetched"}
