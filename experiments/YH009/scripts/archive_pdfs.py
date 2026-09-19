#!/usr/bin/env python3
"""unwind-tape / task B step 3 — sources.csv 全 URL の PDF アーカイバ.

戦略:
  1. inputs/pdfs_supplied/{source_id}__*.pdf が存在すれば seed (ユーザ供給を優先。恒久保存性◎)
  2. なければ URL を GET (指数バックオフ retry)
  3. Content-Type が HTML っぽければ .html 保存 (S002 は JPX ページ)
  4. sha256/bytes/fetched_at を manifest.jsonl と sources.csv に記録
  5. 失敗は gaps_report.md に列挙、sources.csv の archived=FALSE のまま維持

不変条件:
  - 供給 PDF の sha256 を manifest に載せる (改竄検知アンカー)
  - Reuters/robots-blocked などで取れないものは黙って空にせず gaps_report で報告
  - 冪等: 既に data/raw/pdfs/{source_id}__* が存在し supplied と sha256 が一致すれば再取得しない
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


USER_AGENT = "unwind-tape-pdf-archiver/0.1 (financial-abm-lab; +https://github.com/yuitokyouni/financial-abm-lab)"
TIMEOUT_SEC = 30
RETRIES = 4
BACKOFF_BASE = 2.0
BACKOFF_FACTOR = 2.0


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _http_get(url: str, log_prefix: str = "") -> tuple[int, bytes, dict]:
    """Return (status, body, headers). Raise last exception after retries."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.5"})
    last_exc: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT_SEC, allow_redirects=True)
            return r.status_code, r.content, dict(r.headers)
        except Exception as e:
            last_exc = e
            if attempt >= RETRIES:
                break
            wait = BACKOFF_BASE * (BACKOFF_FACTOR ** attempt)
            print(f"{log_prefix} GET {url} failed ({e}); retry {attempt+1}/{RETRIES} in {wait:.1f}s",
                  file=sys.stderr)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def _suffix_from_ct(ct: str, url: str) -> str:
    ct = (ct or "").lower()
    if "pdf" in ct:
        return ".pdf"
    if "html" in ct:
        return ".html"
    # fall back to URL path
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".html") or path.endswith(".htm") or path.endswith("/"):
        return ".html"
    return ".bin"


def _slugify(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)[:120]


def _find_supplied(source_id: str, supplied_dir: Path) -> Path | None:
    if not supplied_dir.exists():
        return None
    for p in sorted(supplied_dir.glob(f"{source_id}__*")):
        return p
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "data" / "parsed" / "tape")
    ap.add_argument("--supplied-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "inputs" / "pdfs_supplied")
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "data" / "raw" / "pdfs")
    ap.add_argument("--gaps-report", type=Path,
                    default=Path(__file__).resolve().parent.parent / "data" / "gaps_report.md")
    args = ap.parse_args(argv)

    sources_csv = args.tape_dir / "sources.csv"
    if not sources_csv.exists():
        print(f"sources.csv not found: {sources_csv} — run migrate_xlsx_to_csv.py first", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.out_dir / "manifest.jsonl"

    now_jst = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds")

    with sources_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    successes: list[str] = []
    failures: list[tuple[str, str]] = []
    seeded: list[str] = []

    for row in rows:
        sid = row["source_id"]
        url = row.get("source_url", "").strip()
        log_pfx = f"[{sid}]"
        supplied = _find_supplied(sid, args.supplied_dir)
        entry: dict = {
            "captured_at": now_jst,
            "source_id": sid,
            "source_url": url,
            "path": "",
            "sha256": "",
            "bytes": 0,
            "status": "pending",
            "detail": "",
        }

        # decide destination filename
        if supplied:
            data = supplied.read_bytes()
            sha = _sha256(data)
            dest = args.out_dir / supplied.name
            # idempotency: skip write if identical file already exists
            if dest.exists() and _sha256(dest.read_bytes()) == sha:
                pass
            else:
                dest.write_bytes(data)
            row["archived"] = "TRUE"
            row["local_path"] = str(dest.relative_to(args.tape_dir.parent.parent))
            row["sha256"] = sha
            row["bytes"] = str(len(data))
            row["fetched_at"] = now_jst
            entry.update({
                "path": row["local_path"],
                "sha256": sha,
                "bytes": len(data),
                "status": "seeded_from_supplied",
                "detail": f"copied from {supplied.name}",
            })
            with manifest.open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            seeded.append(sid)
            print(f"{log_pfx} seeded from supplied → {dest.name}")
            continue

        if not url:
            entry["status"] = "no_url"
            entry["detail"] = "row has no source_url"
            with manifest.open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            failures.append((sid, "no source_url"))
            print(f"{log_pfx} no url — skip")
            continue

        # download
        try:
            status, data, headers = _http_get(url, log_prefix=log_pfx)
        except Exception as e:
            row["archived"] = "FALSE"
            row["fetched_at"] = now_jst
            entry.update({"status": "fetch_error", "detail": str(e)})
            with manifest.open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            failures.append((sid, f"exception: {e}"))
            print(f"{log_pfx} fetch exception: {e}", file=sys.stderr)
            continue

        if status >= 400:
            row["archived"] = "FALSE"
            row["fetched_at"] = now_jst
            entry.update({"status": "fetch_error", "detail": f"HTTP {status}"})
            with manifest.open("a", encoding="utf-8") as mf:
                mf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            failures.append((sid, f"HTTP {status}"))
            print(f"{log_pfx} HTTP {status} from {url}", file=sys.stderr)
            continue

        ext = _suffix_from_ct(headers.get("Content-Type", ""), url)
        stem = _slugify(Path(urlparse(url).path).stem or "index")
        dest = args.out_dir / f"{sid}__{stem}{ext}"
        dest.write_bytes(data)
        sha = _sha256(data)
        row["archived"] = "TRUE"
        row["local_path"] = str(dest.relative_to(args.tape_dir.parent.parent))
        row["sha256"] = sha
        row["bytes"] = str(len(data))
        row["fetched_at"] = now_jst
        entry.update({
            "path": row["local_path"],
            "sha256": sha,
            "bytes": len(data),
            "status": "ok",
            "detail": f"HTTP {status}, Content-Type={headers.get('Content-Type', '?')}",
        })
        with manifest.open("a", encoding="utf-8") as mf:
            mf.write(json.dumps(entry, ensure_ascii=False) + "\n")
        successes.append(sid)
        print(f"{log_pfx} downloaded {len(data)} bytes → {dest.name}")

    # write back sources.csv
    with sources_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # gaps report
    if failures:
        args.gaps_report.parent.mkdir(parents=True, exist_ok=True)
        header_needed = not args.gaps_report.exists()
        with args.gaps_report.open("a", encoding="utf-8") as f:
            if header_needed:
                f.write("# unwind-tape gaps report\n\n")
                f.write("`ts | context | kind | detail` — schema変化 / 取得失敗 / 欠損の追記ログ。\n")
                f.write("欠損は絶対に埋めない。ここに列挙し、原因を追跡してから raw を再取得すること。\n\n")
            for sid, detail in failures:
                f.write(f"- {now_jst} | pdf_archiver:{sid} | fetch_error | {detail}\n")

    print(f"\nsummary: seeded={len(seeded)} downloaded={len(successes)} failed={len(failures)}")
    if failures:
        print(f"failures logged to {args.gaps_report}")
        for sid, detail in failures:
            print(f"  {sid}: {detail}")
    return 4 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
