#!/usr/bin/env python3
"""Read-only Zotero/Drive/GCS gateway. Never overwrite existing local files.

Use --help for commands. No cloud resources are created, no PDFs are committed,
and no LLM calls are made. Google credentials are env tokens or gcloud ADC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "references" / "catalog.json"
DEFAULT_CACHE = ROOT / ".cache" / "research-assets"
HOSTS = {"api.zotero.org", "www.googleapis.com", "storage.googleapis.com"}
MAX_JSON = 16 * 1024 * 1024
DEFAULT_MAX_BYTES = 128 * 1024 * 1024


class AssetError(RuntimeError):
    """Actionable error; never include response bodies or credentials."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AssetError("Redirect refused: credentials are not forwarded to another URL.")


OPENER = urllib.request.build_opener(NoRedirect())


def _open(url: str, headers: dict[str, str]):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc not in HOSTS
            or parsed.username or parsed.password or parsed.fragment):
        raise AssetError("Only the fixed Zotero/Google HTTPS API endpoints are allowed.")
    for attempt in range(3):
        try:
            return OPENER.open(urllib.request.Request(url, headers=headers), timeout=30)
        except urllib.error.HTTPError as exc:
            status = exc.code
            wait_raw = exc.headers.get("Retry-After", "")
            exc.close()
            if status not in (429, 500, 502, 503, 504) or attempt == 2:
                raise AssetError(f"{parsed.hostname}: HTTP {status}; check access/scopes or retry later.") from None
            # Do not retry early if the server asks for a long or date-based wait.
            if wait_raw and (not wait_raw.isdigit() or int(wait_raw) > 30):
                raise AssetError("Server requested a longer wait; retry later.") from None
            wait = int(wait_raw) if wait_raw else 2 ** attempt
            print(f"HTTP {status}; retry {attempt + 1}/2 in {wait}s", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise AssetError(f"{parsed.hostname}: network/timeout failure; no credentials logged.") from None
    raise AssertionError("unreachable")


def _json_request(url: str, headers: dict[str, str]) -> object:
    with _open(url, headers) as response:
        raw = response.read(MAX_JSON + 1)
        backoff = response.headers.get("Backoff", "")
    if len(raw) > MAX_JSON:
        raise AssetError("JSON response exceeded 16 MiB; narrow the query.")
    if backoff:
        if not backoff.isdigit() or int(backoff) > 30:
            raise AssetError("Zotero requested a longer backoff; retry later.")
        time.sleep(int(backoff))
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise AssetError("API response was not valid JSON.") from None


def _credential(value: str) -> str:
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise AssetError("Credential contains invalid characters; check the secret configuration.")
    return value


def google_token(service: str) -> str:
    token = os.environ.get(f"GOOGLE_{service.upper()}_ACCESS_TOKEN")
    if token:
        return _credential(token)
    if not shutil.which("gcloud"):
        raise AssetError(f"Set GOOGLE_{service.upper()}_ACCESS_TOKEN or install/authenticate gcloud ADC.")
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AssetError("gcloud ADC token request failed or timed out.") from None
    if proc.returncode or not proc.stdout.strip():
        raise AssetError("gcloud ADC is not authenticated; see references/README.md.")
    return _credential(proc.stdout.strip())


def zotero_search(query: str, limit: int = 20, start: int = 0) -> list[dict]:
    user = os.environ.get("ZOTERO_USER_ID", "")
    key = os.environ.get("ZOTERO_API_KEY", "")
    if not re.fullmatch(r"[0-9]+", user) or not key:
        raise AssetError("Set numeric ZOTERO_USER_ID and a read-only ZOTERO_API_KEY.")
    if not 1 <= limit <= 100 or start < 0:
        raise AssetError("Zotero limit must be 1..100; start must be non-negative.")
    qs = urllib.parse.urlencode({"q": query, "qmode": "titleCreatorYear", "limit": limit,
                                 "start": start, "sort": "dateAdded", "direction": "asc", "format": "json"})
    data = _json_request(f"https://api.zotero.org/users/{user}/items/top?{qs}",
                         {"Zotero-API-Key": _credential(key), "Zotero-API-Version": "3"})
    if not isinstance(data, list):
        raise AssetError("Unexpected Zotero response.")
    return [{"key": item.get("key"), "version": item.get("version"),
             "data": item.get("data", {})} for item in data]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_hash(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AssetError("A verified lowercase SHA-256 is required before downloading.")


def load_catalog(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        doc = json.load(source)
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or not isinstance(doc.get("references"), list):
        raise AssetError("Unsupported catalog schema.")
    seen = set()
    for ref in doc["references"]:
        rid = ref.get("id", "") if isinstance(ref, dict) else ""
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", rid) or rid in seen:
            raise AssetError("Reference IDs must be unique and filename-safe.")
        seen.add(rid)
        if ref.get("sha256") is not None:
            _check_hash(ref["sha256"])
    return doc


def find_ref(doc: dict, ref_id: str) -> dict:
    for ref in doc["references"]:
        if ref.get("id") == ref_id:
            return ref
    raise AssetError(f"Unknown reference id: {ref_id}")


def _cached(output: Path, expected: str) -> bool:
    if output.is_symlink():
        raise AssetError("Refusing a symlink output.")
    if output.exists():
        if output.is_file() and sha256(output) == expected:
            return True
        raise AssetError("Existing output differs; preserved unchanged. Choose a new output path.")
    return False


def download(url: str, headers: dict[str, str], output: Path, expected: str,
             max_bytes: int, *, pdf: bool = False) -> dict:
    """Stage, verify, then publish without replacing another file (even on races)."""
    _check_hash(expected)
    if max_bytes <= 0:
        raise AssetError("max_bytes must be positive.")
    if _cached(output, expected):
        return {"path": str(output), "sha256": expected, "cache_hit": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".fabm-", suffix=".part", dir=output.parent)
    count = 0
    digest = hashlib.sha256()
    prefix = b""
    started = time.monotonic()
    try:
        with os.fdopen(fd, "wb") as target, _open(url, headers) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise AssetError("Download exceeds --max-bytes; nothing installed.")
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > max_bytes or time.monotonic() - started > 300:
                    raise AssetError("Download size/time limit exceeded; partial file removed.")
                prefix = (prefix + chunk)[:5]
                digest.update(chunk)
                target.write(chunk)
            if length and count != int(length):
                raise AssetError("Truncated download; original output preserved.")
            target.flush()
            os.fsync(target.fileno())
        if digest.hexdigest() != expected:
            raise AssetError("SHA-256 mismatch; original output preserved.")
        if pdf and prefix != b"%PDF-":
            raise AssetError("Response is not a PDF.")
        try:
            # Same-directory hard link is atomic and fails if a target already exists.
            os.link(temporary, output)
        except FileExistsError:
            if not _cached(output, expected):
                raise AssetError("Output appeared during download; preserved unchanged.")
        return {"path": str(output), "sha256": expected, "bytes": count, "cache_hit": False}
    finally:
        Path(temporary).unlink(missing_ok=True)


def drive_download(file_id: str, output: Path, expected: str,
                   max_bytes: int = DEFAULT_MAX_BYTES, *, pdf: bool = True) -> dict:
    _check_hash(expected)
    if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        raise AssetError("A raw Drive file ID is required.")
    if _cached(output, expected):
        return {"path": str(output), "sha256": expected, "cache_hit": True}
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    return download(url, {"Authorization": f"Bearer {google_token('drive')}"},
                    output, expected, max_bytes, pdf=pdf)


def gcs_url(uri: str, generation: str | None = None) -> str:
    parsed = urllib.parse.urlsplit(uri)
    if (parsed.scheme != "gs" or not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", parsed.netloc)
            or not parsed.path.lstrip("/") or parsed.query or parsed.fragment
            or any(c in uri for c in "*?[]\\\r\n")):
        raise AssetError("Use one exact gs://bucket/object URI; no wildcards, query or fragment.")
    params = {"alt": "media"}
    if generation is not None:
        if not str(generation).isdigit():
            raise AssetError("GCS generation must be numeric.")
        params["generation"] = str(generation)
    name = urllib.parse.quote(parsed.path[1:], safe="")
    return f"https://storage.googleapis.com/storage/v1/b/{parsed.netloc}/o/{name}?{urllib.parse.urlencode(params)}"


def gcs_download(uri: str, output: Path, expected: str,
                 max_bytes: int = DEFAULT_MAX_BYTES, generation: str | None = None) -> dict:
    _check_hash(expected)
    url = gcs_url(uri, generation)
    if _cached(output, expected):
        return {"path": str(output), "sha256": expected, "cache_hit": True}
    return download(url, {"Authorization": f"Bearer {google_token('gcs')}"}, output, expected, max_bytes)


def literature_search(path: Path, query: str, limit: int) -> list[dict]:
    """Read the existing Atlas snapshot; never change it or adopt candidates implicitly."""
    with path.open(encoding="utf-8") as source:
        rows = json.load(source)
    if not isinstance(rows, list):
        raise AssetError("Atlas snapshot must be an array of records.")
    fields = ("arxiv_id", "title", "authors", "year", "mechanism_summary", "mechanism_tags")
    return [{**{k: row.get(k) for k in fields}, "evidence_level": "discovery_summary_not_verified_full_text"}
            for row in rows if query.casefold() in json.dumps(row, ensure_ascii=False).casefold()][:limit]


def doctor(live: bool, doc: dict, probe_gcs_uri: str | None = None) -> dict:
    result = {"live_requested": live,
              "zotero": "configured_not_verified" if os.getenv("ZOTERO_USER_ID") and os.getenv("ZOTERO_API_KEY") else "missing_credentials",
              "drive": "configured_not_verified" if os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN") or shutil.which("gcloud") else "missing_credentials",
              "gcs": "configured_not_verified" if os.getenv("GOOGLE_GCS_ACCESS_TOKEN") or shutil.which("gcloud") else "missing_credentials",
              "registered_references": len(doc["references"])}
    if live:
        for service in ("zotero", "drive"):
            try:
                if service == "zotero":
                    zotero_search("", 1)
                else:
                    ref = next((r for r in doc["references"] if r.get("drive_file_id")), None)
                    if not ref:
                        raise AssetError("No registered Drive PDF to probe.")
                    fid = ref["drive_file_id"]
                    if not re.fullmatch(r"[A-Za-z0-9_-]+", fid):
                        raise AssetError("Invalid Drive ID.")
                    _json_request(f"https://www.googleapis.com/drive/v3/files/{fid}?fields=id,name,size",
                                  {"Authorization": f"Bearer {google_token('drive')}"})
                result[service] = "live_read_ok"
            except (AssetError, OSError, ValueError) as exc:
                result[service] = f"blocked: {exc}"
        # Authentication alone cannot demonstrate access to an unspecified bucket.
        result["gcs"] = "not_live_tested: pass --gcs-uri for a metadata-only probe"
        if probe_gcs_uri:
            try:
                url = gcs_url(probe_gcs_uri).replace("alt=media", "fields=bucket,name,generation,size")
                _json_request(url, {"Authorization": f"Bearer {google_token('gcs')}"})
                result["gcs"] = "live_read_ok"
            except (AssetError, OSError, ValueError) as exc:
                result["gcs"] = f"blocked: {exc}"
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("doctor"); d.add_argument("--live", action="store_true")
    d.add_argument("--gcs-uri", help="optional exact object for a metadata-only live read")
    z = sub.add_parser("zotero-search"); z.add_argument("query")
    z.add_argument("--limit", type=int, default=20); z.add_argument("--start", type=int, default=0)
    lit = sub.add_parser("literature-search"); lit.add_argument("query")
    lit.add_argument("--snapshot", type=Path, default=ROOT / "data/literature_methods.json")
    lit.add_argument("--limit", type=int, default=20)
    r = sub.add_parser("refs"); rs = r.add_subparsers(dest="refs_cmd", required=True)
    rs.add_parser("list")
    show = rs.add_parser("show"); show.add_argument("id")
    fetch = rs.add_parser("fetch"); fetch.add_argument("id"); fetch.add_argument("--output", type=Path)
    fetch.add_argument("--text", action="store_true", help="fetch the registered page-numbered text instead")
    fetch.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    g = sub.add_parser("gcs-fetch"); g.add_argument("uri"); g.add_argument("--output", type=Path, required=True)
    g.add_argument("--sha256", required=True); g.add_argument("--generation")
    g.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "zotero-search":
            result = zotero_search(args.query, args.limit, args.start)
        elif args.cmd == "literature-search":
            if args.limit <= 0:
                raise AssetError("limit must be positive.")
            result = literature_search(args.snapshot, args.query, args.limit)
        elif args.cmd == "gcs-fetch":
            result = gcs_download(args.uri, args.output, args.sha256, args.max_bytes, args.generation)
        else:
            doc = load_catalog(args.catalog)
            if args.cmd == "doctor":
                result = doctor(args.live, doc, args.gcs_uri)
            elif args.refs_cmd == "list":
                result = doc["references"]
            else:
                ref = find_ref(doc, args.id)
                if args.refs_cmd == "show":
                    result = ref
                else:
                    asset = ref.get("text", {}) if args.text else ref
                    suffix = ".pages.txt" if args.text else ".pdf"
                    result = drive_download(asset.get("drive_file_id"), args.output or args.cache / "papers" / f"{args.id}{suffix}",
                                            asset.get("sha256"), args.max_bytes, pdf=not args.text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.cmd == "doctor":
            expected = "live_read_ok" if args.live else "configured_not_verified"
            return 0 if all(result[k] == expected for k in ("zotero", "drive", "gcs")) else 2
        return 0
    except (AssetError, OSError, ValueError) as exc:
        print(f"research-assets: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
