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


# Match github.com URLs. Protocol is optional (PDFs often print bare
# "Code: github.com/foo/bar"). We keep just the org/repo segment.
_GITHUB_URL_RE = re.compile(
    r"(?:https?://)?github\.com/([A-Za-z0-9][A-Za-z0-9._\-]*)/([A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,;:)]}>\"'"


def _normalize_for_url_scan(text: str) -> str:
    """Reverse the line-break artifacts that PDF text extractors inject
    into long URLs. Two common patterns:
      'https://github.com/Alicia/\\nTRIBE-bond'   (hard line break)
      'github.com/foo/\\nbar-baz'                  (same)
      'github.com/foo-\\nbar/baz'                  (hyphenated linewrap)
    Collapsing newlines that follow '/' or '-' inside URL-like substrings
    is enough; we don't try to be clever about prose.
    """
    # Linewrap after a '-' inside a word: keep the hyphen, drop only the
    # newline. (Removing the hyphen too is correct for prose dehyphenation
    # but wrong for repo names like 'very-long-repo'; we err toward
    # preserving real hyphens since false positives just produce a wrong
    # URL that 404s instead of a fake link that points at someone else.)
    text = re.sub(r"-\n", "-", text)
    # Collapse a newline that immediately follows '/' (mid-URL) → ''
    text = re.sub(r"/\n", "/", text)
    # As a final cushion, collapse runs of whitespace (incl. \n) to a single
    # space so the URL regex doesn't choke on weird PDF spacing.
    text = re.sub(r"\s+", " ", text)
    return text


def extract_github_from_text(text: str | None) -> str | None:
    """Return the first canonical github.com/<org>/<repo> URL in `text`.

    Tolerates: missing protocol, trailing punctuation / closing brackets,
    `.git` suffix, line-wrapped URLs (newline-after-/ and hyphenation).
    """
    if not text:
        return None
    candidates: list[str] = []
    # Try BOTH the raw text and the normalized text. Normalization repairs
    # PDF line-wrap mangling, but raw text wins when the URL was already
    # clean. Pick the longer match — line-wrap repair only ever extends a
    # repo name (e.g. 'very-long-' → 'very-long-repo-name').
    for variant in (text, _normalize_for_url_scan(text)):
        m = _GITHUB_URL_RE.search(variant)
        if not m:
            continue
        org, repo = m.group(1), m.group(2)
        while repo and repo[-1] in _TRAILING_PUNCT:
            repo = repo[:-1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        # A trailing '-' or '.' on the repo is a strong sign of a truncated
        # line-wrapped URL ('very-long-\nrepo' would yield 'very-long-'
        # before normalization). Strip and keep so we can compare lengths.
        repo = repo.rstrip("-.")
        if repo:
            candidates.append(f"https://github.com/{org}/{repo}")
    if not candidates:
        return None
    return max(candidates, key=len)


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


_ARXIV_PDF_URL = "https://arxiv.org/pdf/{base}.pdf"
_PDF_MAX_BYTES = 8 * 1024 * 1024  # 8 MB cap; abort if PDF is bigger
_PDF_TIMEOUT = 30.0


def _download_pdf_bytes(arxiv_id: str) -> bytes | None:
    base = _arxiv_id_base(arxiv_id)
    url = _ARXIV_PDF_URL.format(base=base)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_PDF_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            # Stream-read with a cap so a runaway big PDF doesn't OOM us.
            buf = bytearray()
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                buf.extend(chunk)
                if len(buf) > _PDF_MAX_BYTES:
                    return None
            return bytes(buf)
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, OSError):
        return None


def extract_github_from_pdf(arxiv_id: str, max_pages: int = 4) -> str | None:
    """Download the arxiv PDF, extract text from the first `max_pages`
    pages, and regex-search for a github URL.

    First ~4 pages cover abstract + introduction + footnotes, which is
    where 'code is available at...' lives in almost every paper that has
    a repo. Skipping the body saves bandwidth and parse time.

    Returns the URL or None. All failures (network, pypdf parse error,
    unsupported PDF) are swallowed.
    """
    try:
        from pypdf import PdfReader  # local import: optional dep
    except ImportError:
        return None
    body = _download_pdf_bytes(arxiv_id)
    if not body:
        return None
    import io
    try:
        reader = PdfReader(io.BytesIO(body))
    except Exception:
        return None
    text_parts: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        try:
            text_parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(text_parts)
    return extract_github_from_text(text)


def fetch_arxiv_comment(arxiv_id: str) -> str | None:
    """Hit arxiv API for a single paper, return the author-comment field
    or None. Many ABM/finance papers stash 'code at github.com/...' here
    rather than in the abstract."""
    try:
        import arxiv  # local import: cli-only dep
    except ImportError:
        return None
    base = _arxiv_id_base(arxiv_id)
    try:
        client = arxiv.Client(page_size=1, delay_seconds=3.0)
        results = list(client.results(arxiv.Search(id_list=[base])))
    except Exception:
        return None
    if not results:
        return None
    return results[0].comment


def resolve_code_url(arxiv_id: str, abstract: str | None,
                     comment: str | None = None) -> tuple[str | None, str | None]:
    """Try abstract → comment → PWC. Return (url, source) where source is
    'abstract' / 'comment' / 'pwc' / None.

    `comment` is the arxiv author-comment field. If you have it cached, pass
    it; otherwise the caller can also pass None and rely on PWC fallback."""
    url = extract_github_from_text(abstract)
    if url:
        return url, "abstract"
    url = extract_github_from_text(comment)
    if url:
        return url, "comment"
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
