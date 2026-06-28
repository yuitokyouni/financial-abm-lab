"""arxiv_cli — manage the literature_methods store.

Sub-commands:
  ingest    Query arxiv, extract with Groq, store.
            uv run python -m fingerprint_atlas.arxiv_cli --db <db> ingest \\
              --query 'cat:q-fin.TR' --max 50

  list      One-line summary per paper, filter by relevance / tag.
            --tag herding   --min-relevance 0.5   --limit 20

  show      Full record for one paper by arxiv_id.

  search    Simple substring search over title + abstract + mechanism_summary.

Usage examples:
  # ingest the 50 newest agent-based financial papers, with extraction:
  uv run python -m fingerprint_atlas.arxiv_cli --db <db> ingest \\
    --preset agent_based_recent --max 50

  # list the most relevant papers about LLM-as-agent:
  uv run python -m fingerprint_atlas.arxiv_cli --db <db> list \\
    --tag LLM-agent --limit 20

  # raw arxiv query without extraction (metadata only, free):
  uv run python -m fingerprint_atlas.arxiv_cli --db <db> ingest \\
    --query 'cat:q-fin.TR' --max 200 --no-extract
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap

from .arxiv_ingest import DEFAULT_QUERIES, DEFAULT_GROQ_MODEL, ingest
from .db import ensure_literature_schema, load_literature


def cmd_ingest(args) -> int:
    query = args.query
    if args.preset:
        if args.preset not in DEFAULT_QUERIES:
            print(f"unknown preset {args.preset!r}; choose from {list(DEFAULT_QUERIES)}",
                  file=sys.stderr)
            return 1
        query = DEFAULT_QUERIES[args.preset]
    if not query:
        print("either --query or --preset is required", file=sys.stderr)
        return 1

    summary = ingest(
        args.db, query=query, max_results=args.max,
        extract=not args.no_extract, groq_model=args.groq_model,
        min_relevance_to_keep=args.min_relevance_to_keep,
        verbose=not args.quiet,
    )
    print("\n--- summary ---")
    print(json.dumps({k: v for k, v in summary.items() if k != "errors"}, indent=2))
    if summary["errors"]:
        print(f"\nfirst 3 errors:")
        for e in summary["errors"][:3]:
            print("  -", e)
    return 0 if summary["n_errors"] == 0 else 1


def cmd_list(args) -> int:
    ensure_literature_schema(args.db)
    rows = load_literature(
        args.db, min_relevance=args.min_relevance, tag=args.tag,
        max_results=args.limit,
    )
    if not rows:
        print("no papers match the filter.")
        return 0
    print(f"{'rel':>4s}  {'year':>4s}  {'arxiv':<14s}  {'tags':<28s}  title")
    for r in rows:
        rel = f"{r['relevance_score']:.2f}" if r['relevance_score'] is not None else "  - "
        tags = ", ".join(r["mechanism_tags"][:3]) or "(no tags)"
        if len(tags) > 28:
            tags = tags[:25] + "..."
        title = r["title"][:70]
        print(f"{rel:>4s}  {r['year']:>4d}  {r['arxiv_id']:<14s}  {tags:<28s}  {title}")
    return 0


def cmd_show(args) -> int:
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    p = next((r for r in rows if r["arxiv_id"] == args.arxiv_id), None)
    if p is None:
        print(f"no paper with arxiv_id={args.arxiv_id!r}", file=sys.stderr)
        return 1
    print(f"=== {p['arxiv_id']} ===")
    print(f"title    : {p['title']}")
    print(f"authors  : {p['authors']}")
    print(f"year     : {p['year']}")
    print(f"category : {p['primary_category']}")
    print(f"url      : https://arxiv.org/abs/{p['arxiv_id'].split('v')[0]}")
    print()
    print("abstract:")
    for line in textwrap.wrap(p["abstract"], width=78):
        print(f"  {line}")
    if p["mechanism_summary"]:
        print("\nmechanism_summary:")
        for line in textwrap.wrap(p["mechanism_summary"], width=78):
            print(f"  {line}")
    if p["mechanism_tags"]:
        print(f"\nmechanism_tags          : {', '.join(p['mechanism_tags'])}")
    if p["stylized_facts_targeted"]:
        print(f"stylized_facts_targeted : {', '.join(p['stylized_facts_targeted'])}")
    if p["novelty_signal"]:
        print(f"novelty_signal          : {p['novelty_signal']}")
    if p["relevance_score"] is not None:
        print(f"relevance_score         : {p['relevance_score']}")
    print(f"extracted_by            : {p['extracted_by_model']}")
    if p.get("code_url"):
        src = p.get("code_url_source") or "?"
        print(f"code_url ({src:<8s})     : {p['code_url']}")
    if p.get("arxiv_comment"):
        print(f"arxiv_comment           : {p['arxiv_comment']}")
    print(f"ingested_at             : {p['ingested_at']}")
    return 0


def cmd_fetch_code_snapshots(args) -> int:
    """For every paper with a code_url but no snapshot, fetch README +
    top-level file tree from GitHub and cache it. Used by idea_plan to
    show the LLM real file/class structure rather than just titles.

    Unauthenticated GitHub API is rate-limited to 60/hr — set GITHUB_TOKEN
    env var to lift the cap to 5000/hr."""
    from .code_links import fetch_repo_snapshot
    from .db import load_code_snapshots, upsert_code_snapshot
    import time
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    targets = [r for r in rows if r.get("code_url")]
    if not targets:
        print("no rows with code_url. Run `backfill-code` first.")
        return 0
    cached = load_code_snapshots(args.db, [r["arxiv_id"] for r in targets])
    todo = [r for r in targets if r["arxiv_id"] not in cached]
    if not todo:
        print("all code_url rows already have snapshots.")
        return 0
    print(f"fetching snapshots for {len(todo)} paper(s)...")
    n_ok, n_no_readme, n_err = 0, 0, 0
    for i, r in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        snap = fetch_repo_snapshot(r["code_url"])
        upsert_code_snapshot(
            args.db, arxiv_id=r["arxiv_id"], code_url=r["code_url"],
            readme_excerpt=snap["readme_excerpt"], file_tree=snap["file_tree"],
            status=snap["status"], error_msg=snap["error_msg"],
        )
        tag = {"ok": "+", "no_readme": "~", "error": "!"}[snap["status"]]
        print(f"  {tag} {r['arxiv_id']:<14s} {snap['status']:<10s} {r['code_url']}")
        if snap["status"] == "ok":
            n_ok += 1
        elif snap["status"] == "no_readme":
            n_no_readme += 1
        else:
            n_err += 1
        # GitHub raw + API are independent endpoints, but be gentle.
        time.sleep(args.sleep)
    print(f"\nok={n_ok}  no_readme={n_no_readme}  error={n_err}")
    return 0


def cmd_backfill_code(args) -> int:
    """For every already-ingested paper without a code_url, try regex over
    abstract → arxiv author-comment → Papers with Code API. Older DB rows
    have no cached arxiv_comment, so we fetch it from arxiv on demand and
    persist it for future passes.

    --force re-checks papers that previously came back empty (useful when
    new sources are added or PWC indexes a new paper)."""
    from .code_links import resolve_code_url, fetch_arxiv_comment
    from .db import set_literature_code_url, set_arxiv_comment
    import time
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if args.force:
        todo = [r for r in rows if not r.get("code_url")]
    else:
        # The first run after this column was added has code_url=None for
        # everyone, so --force vs default look the same. Default keeps the
        # idempotent semantics for subsequent runs.
        todo = [r for r in rows if not r.get("code_url")]
    if not todo:
        print("all rows already have code_url.")
        return 0
    print(f"trying to backfill code_url for {len(todo)} paper(s)...")
    n_filled, n_skipped = 0, 0
    src_counts = {"abstract": 0, "comment": 0, "pwc": 0}
    for i, p in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        # Use cached comment if present; otherwise fetch it from arxiv (one
        # call) and persist for next time.
        comment = p.get("arxiv_comment")
        if comment is None:
            comment = fetch_arxiv_comment(p["arxiv_id"])
            if comment is not None:
                try:
                    set_arxiv_comment(args.db, p["arxiv_id"], comment)
                except KeyError:
                    pass
            # arxiv API rate-limits us implicitly via delay_seconds=3.0 in
            # fetch_arxiv_comment; no extra sleep needed here.
        try:
            url, source = resolve_code_url(p["arxiv_id"], p["abstract"], comment)
        except Exception as exc:
            print(f"  ! {p['arxiv_id']}: {exc}")
            continue
        if url:
            set_literature_code_url(args.db, p["arxiv_id"],
                                    code_url=url, source=source)
            print(f"  + {p['arxiv_id']} ({source}): {url}")
            n_filled += 1
            src_counts[source] = src_counts.get(source, 0) + 1
        else:
            n_skipped += 1
        if args.sleep:
            time.sleep(args.sleep)
    print(f"\nfilled {n_filled} (abstract={src_counts['abstract']}, "
          f"comment={src_counts['comment']}, pwc={src_counts['pwc']}), "
          f"skipped {n_skipped}.")
    return 0


def cmd_scan_pdfs_for_code(args) -> int:
    """Last-resort source: download the PDF for each paper without a code_url
    (and not yet PDF-scanned), parse first few pages with pypdf, regex for
    github. Many ABM/finance papers stash the link in the introduction
    rather than the abstract or arxiv comment.

    Best-effort: any per-paper failure is swallowed; the row is stamped
    pdf_scanned_at regardless so we don't retry on the next run."""
    from .code_links import extract_github_from_pdf
    from .db import set_literature_code_url, mark_pdf_scanned
    import time
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    todo = [r for r in rows
            if not r.get("code_url") and not r.get("pdf_scanned_at")]
    if not todo:
        print("no papers left to scan (every link-less row already scanned).")
        return 0
    print(f"scanning {len(todo)} PDF(s) — {args.max_pages} pages each, "
          f"{args.sleep:.1f}s between papers")
    n_filled, n_empty = 0, 0
    for i, p in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        try:
            url = extract_github_from_pdf(p["arxiv_id"], max_pages=args.max_pages)
        except Exception as exc:
            print(f"  ! {p['arxiv_id']}: {exc}")
            url = None
        if url:
            set_literature_code_url(args.db, p["arxiv_id"],
                                    code_url=url, source="pdf")
            print(f"  + {p['arxiv_id']} (pdf): {url}")
            n_filled += 1
        else:
            print(f"  - {p['arxiv_id']}: no github link in first {args.max_pages} pages")
            n_empty += 1
        # Stamp regardless so a future re-run doesn't redownload the PDF.
        try:
            mark_pdf_scanned(args.db, p["arxiv_id"])
        except KeyError:
            pass
        if args.sleep:
            time.sleep(args.sleep)
    print(f"\nfilled {n_filled}, no-link {n_empty}.")
    return 0


def cmd_diagnose_code(args) -> int:
    """Run all three code-link sources against ONE arxiv_id and print what
    each returns. Useful when backfill hit rate looks too low."""
    from .code_links import (
        extract_github_from_text, fetch_pwc_repo, fetch_arxiv_comment,
    )
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    p = next((r for r in rows if r["arxiv_id"] == args.arxiv_id), None)
    if p is None:
        print(f"no row for arxiv_id={args.arxiv_id!r} in DB; will try arxiv directly.")
        abstract = None
        cached_comment = None
    else:
        abstract = p["abstract"]
        cached_comment = p.get("arxiv_comment")
        print(f"=== {p['arxiv_id']} — {p['title']!r}")
        print(f"already-persisted code_url: {p.get('code_url')!r}")
    print()
    print("[1] abstract regex hit:")
    u1 = extract_github_from_text(abstract)
    print(f"    {u1!r}")
    print()
    print("[2] arxiv author-comment field:")
    comment = cached_comment
    if comment is None:
        print("    not cached, fetching from arxiv...")
        comment = fetch_arxiv_comment(args.arxiv_id)
    print(f"    raw comment: {comment!r}")
    u2 = extract_github_from_text(comment)
    print(f"    regex hit  : {u2!r}")
    print()
    print("[3] Papers with Code lookup:")
    u3 = fetch_pwc_repo(args.arxiv_id)
    print(f"    {u3!r}")
    print()
    print("[4] PDF body (first 4 pages):")
    if args.pdf:
        from .code_links import (
            extract_github_from_pdf, _download_pdf_bytes,
        )
        u4 = extract_github_from_pdf(args.arxiv_id)
        print(f"    regex hit  : {u4!r}")
        # Show what text was actually extracted, so a None hit can be
        # diagnosed (PDF is image-only? URL spelled differently?)
        try:
            from pypdf import PdfReader
            import io
            body = _download_pdf_bytes(args.arxiv_id)
            if not body:
                print("    (PDF download failed)")
            else:
                reader = PdfReader(io.BytesIO(body))
                joined = "\n".join(
                    (page.extract_text() or "")
                    for page in reader.pages[:4]
                )
                print(f"    extracted  : {len(joined)} chars from first 4 pages")
                # Highlight every line that mentions 'github' or 'gitlab'
                # — if there are zero, the link genuinely isn't in the body.
                hits = [ln for ln in joined.splitlines()
                        if "github" in ln.lower() or "gitlab" in ln.lower()]
                if hits:
                    print(f"    lines mentioning github/gitlab ({len(hits)}):")
                    for h in hits[:10]:
                        print(f"      | {h.strip()[:200]}")
                else:
                    print("    no 'github'/'gitlab' mention in extracted text")
                    print("    first 400 chars:")
                    print(f"      | {joined[:400].replace(chr(10), ' / ')}")
        except ImportError:
            print("    (pypdf not installed)")
        except Exception as exc:
            print(f"    (debug dump failed: {exc})")
    else:
        print("    (skipped; pass --pdf to actually download and scan)")
    return 0


def cmd_search(args) -> int:
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    needle = args.query.lower()
    matches = []
    for r in rows:
        haystack = " ".join([
            (r["arxiv_id"] or ""), (r["title"] or ""), (r["abstract"] or ""),
            (r["mechanism_summary"] or ""), (r["novelty_signal"] or ""),
            " ".join(r["mechanism_tags"]), (r["authors"] or ""),
        ]).lower()
        if needle in haystack:
            matches.append(r)
    if not matches:
        print(f"no matches for {args.query!r}")
        return 0
    print(f"{len(matches)} match(es):")
    for r in matches[:args.limit]:
        rel = f"{r['relevance_score']:.2f}" if r['relevance_score'] is not None else "  - "
        print(f"  [{rel}] {r['arxiv_id']:<14s} {r['title'][:70]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("--db", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="query arxiv + extract with Groq + store")
    g = p_in.add_mutually_exclusive_group()
    g.add_argument("--query", default=None, help="raw arxiv search query")
    g.add_argument("--preset", default=None,
                   help=f"named preset query: {list(DEFAULT_QUERIES)}")
    p_in.add_argument("--max", type=int, default=50, help="max papers per call")
    p_in.add_argument("--no-extract", action="store_true",
                      help="ingest metadata only (free, no Groq calls)")
    p_in.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
    p_in.add_argument("--min-relevance-to-keep", type=float, default=0.0,
                      help="papers extracted below this relevance keep metadata only")
    p_in.add_argument("--quiet", action="store_true")

    p_ls = sub.add_parser("list", help="one-line summary per paper")
    p_ls.add_argument("--tag", default=None)
    p_ls.add_argument("--min-relevance", type=float, default=None)
    p_ls.add_argument("--limit", type=int, default=50)

    p_sh = sub.add_parser("show", help="full paper record")
    p_sh.add_argument("arxiv_id")

    p_se = sub.add_parser("search", help="substring search over title + abstract + mechanism")
    p_se.add_argument("query")
    p_se.add_argument("--limit", type=int, default=20)

    p_bf = sub.add_parser(
        "backfill-code",
        help=("for already-ingested papers without code_url, run abstract "
              "regex → arxiv author-comment → Papers with Code API"),
    )
    p_bf.add_argument("--limit", type=int, default=0,
                      help="stop after N papers (0 = no limit)")
    p_bf.add_argument("--force", action="store_true",
                      help="re-check papers that previously came back empty")
    p_bf.add_argument("--sleep", type=float, default=0.0,
                      help=("seconds between papers (only useful when "
                            "fetching uncached arxiv comments; the arxiv "
                            "client already enforces a 3s delay internally)"))

    p_dc = sub.add_parser(
        "diagnose-code",
        help=("run all code-link sources against ONE arxiv_id and print "
              "what each returns — useful when backfill hit rate is low"),
    )
    p_dc.add_argument("arxiv_id")
    p_dc.add_argument("--pdf", action="store_true",
                      help="also download the PDF and scan first pages")

    p_sp = sub.add_parser(
        "scan-pdfs-for-code",
        help=("last-resort: download PDFs for papers without a code_url "
              "and grep first pages for github URL. Heavy — opt-in only."),
    )
    p_sp.add_argument("--limit", type=int, default=0,
                      help="stop after N papers (0 = no limit)")
    p_sp.add_argument("--max-pages", type=int, default=4,
                      help="how many leading pages to extract per PDF")
    p_sp.add_argument("--sleep", type=float, default=3.0,
                      help="seconds between papers (arxiv rate-limit padding)")

    p_fs = sub.add_parser(
        "fetch-code-snapshots",
        help=("for papers with code_url but no snapshot, fetch README + "
              "top-level file tree from GitHub. Set GITHUB_TOKEN to lift "
              "the 60/hr unauthenticated rate limit to 5000/hr."),
    )
    p_fs.add_argument("--limit", type=int, default=0,
                      help="stop after N papers (0 = no limit)")
    p_fs.add_argument("--sleep", type=float, default=1.0,
                      help="seconds between paper snapshots (rate-limit padding)")

    args = ap.parse_args()
    handlers = {"ingest": cmd_ingest, "list": cmd_list, "show": cmd_show,
                "search": cmd_search, "backfill-code": cmd_backfill_code,
                "diagnose-code": cmd_diagnose_code,
                "scan-pdfs-for-code": cmd_scan_pdfs_for_code,
                "fetch-code-snapshots": cmd_fetch_code_snapshots}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
