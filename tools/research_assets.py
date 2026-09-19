#!/usr/bin/env python3
"""Read-only research asset gateway for local and remote coding agents.

Zotero is the bibliographic source, Google Drive holds canonical PDFs, and GCS
holds large research data. Git stores only stable identifiers/provenance.

No third-party Python SDK is required: Zotero/Drive use HTTPS and GCS delegates
authentication/downloads to gcloud so credentials never enter this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "references" / "catalog.json"
DEFAULT_CACHE = ROOT / ".cache" / "research-assets"


def _json_request(url: str, headers: dict[str, str]) -> object:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def zotero_search(query: str, limit: int = 20) -> list[dict]:
    user = os.environ.get("ZOTERO_USER_ID")
    key = os.environ.get("ZOTERO_API_KEY")
    if not user or not key:
        raise SystemExit("Set ZOTERO_USER_ID and ZOTERO_API_KEY (read-only key recommended).")
    qs = urllib.parse.urlencode({"q": query, "qmode": "titleCreatorYear", "limit": limit, "format": "json"})
    url = f"https://api.zotero.org/users/{urllib.parse.quote(user)}/items/top?{qs}"
    data = _json_request(url, {"Zotero-API-Key": key, "Zotero-API-Version": "3"})
    out = []
    for item in data:
        d = item.get("data", {})
        out.append({
            "key": item.get("key"),
            "title": d.get("title"),
            "creators": d.get("creators", []),
            "date": d.get("date"),
            "doi": d.get("DOI") or None,
            "url": d.get("url") or None,
        })
    return out


def drive_download(file_id: str, output: Path) -> None:
    token = os.environ.get("GOOGLE_DRIVE_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Set GOOGLE_DRIVE_ACCESS_TOKEN to a short-lived OAuth access token.")
    output.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}?alt=media"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as resp, output.open("wb") as fh:
        while chunk := resp.read(1024 * 1024):
            fh.write(chunk)


def gcs_download(uri: str, output: Path) -> None:
    if not uri.startswith("gs://"):
        raise SystemExit("GCS URI must start with gs://")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gcloud", "storage", "cp", uri, str(output)], check=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalog(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema_version") != 1 or not isinstance(doc.get("references"), list):
        raise SystemExit(f"Unsupported catalog: {path}")
    return doc


def find_ref(doc: dict, ref_id: str) -> dict:
    for ref in doc["references"]:
        if ref.get("id") == ref_id:
            return ref
    raise SystemExit(f"Unknown reference id: {ref_id}")


def cmd_refs(args: argparse.Namespace) -> int:
    doc = load_catalog(Path(args.catalog))
    if args.refs_cmd == "list":
        for ref in doc["references"]:
            print(json.dumps(ref, ensure_ascii=False))
        return 0
    ref = find_ref(doc, args.id)
    if args.refs_cmd == "show":
        print(json.dumps(ref, ensure_ascii=False, indent=2))
        return 0
    if args.refs_cmd == "fetch":
        drive_id = ref.get("drive_file_id")
        if not drive_id:
            raise SystemExit(f"{args.id} has no drive_file_id yet")
        out = Path(args.output) if args.output else Path(args.cache) / "papers" / f"{args.id}.pdf"
        drive_download(drive_id, out)
        actual = sha256(out)
        expected = ref.get("sha256")
        if expected and expected != actual:
            out.unlink(missing_ok=True)
            raise SystemExit(f"SHA-256 mismatch for {args.id}: expected {expected}, got {actual}")
        print(json.dumps({"path": str(out), "sha256": actual}))
        return 0
    raise AssertionError(args.refs_cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    sub = ap.add_subparsers(dest="cmd", required=True)

    z = sub.add_parser("zotero-search", help="search the synced Zotero library")
    z.add_argument("query")
    z.add_argument("--limit", type=int, default=20)

    r = sub.add_parser("refs", help="inspect/fetch registered implementation references")
    rs = r.add_subparsers(dest="refs_cmd", required=True)
    rs.add_parser("list")
    show = rs.add_parser("show"); show.add_argument("id")
    fetch = rs.add_parser("fetch"); fetch.add_argument("id"); fetch.add_argument("--output")

    g = sub.add_parser("gcs-fetch", help="fetch a registered/known large object from GCS")
    g.add_argument("uri"); g.add_argument("--output", required=True)

    args = ap.parse_args()
    if args.cmd == "zotero-search":
        print(json.dumps(zotero_search(args.query, args.limit), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "refs":
        return cmd_refs(args)
    if args.cmd == "gcs-fetch":
        gcs_download(args.uri, Path(args.output))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
