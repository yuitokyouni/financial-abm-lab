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
import re
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


def cmd_ingest_ids(args) -> int:
    """Targeted ingest of an explicit arxiv_id list. Reads ids from --ids
    (comma-sep) or one-per-line from --ids-file."""
    from .arxiv_ingest import ingest_by_ids
    ids: list[str] = []
    def _clean_id(token: str) -> str:
        # Strip leading/trailing whitespace AND drop any inline '# comment'.
        return token.split("#", 1)[0].strip()
    if args.ids:
        for tok in args.ids.split(","):
            cleaned = _clean_id(tok)
            if cleaned:
                ids.append(cleaned)
    if args.ids_file:
        with open(args.ids_file) as fh:
            for line in fh:
                cleaned = _clean_id(line)
                if cleaned:
                    ids.append(cleaned)
    if not ids:
        print("either --ids or --ids-file is required", file=sys.stderr)
        return 1
    summary = ingest_by_ids(
        args.db, ids, extract=not args.no_extract,
        groq_model=args.groq_model,
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
    (and not yet PDF-scanned), parse pages with pypdf, regex for github /
    gitlab / bitbucket. Many ABM/finance papers stash the link in the
    introduction / acknowledgments / refs rather than in the abstract.

    Best-effort: any per-paper failure is swallowed; the row is stamped
    pdf_scanned_at regardless so we don't retry on the next run.

    --rescan re-runs the scanner on rows that were already scanned (use
    after improving the extractor or to refresh a previously-wrong link).
    --filter-source LIST only re-scans rows whose existing code_url_source
    matches one of LIST (comma-sep, e.g. 'pdf' to revisit only PDF hits)."""
    from .code_links import extract_github_from_pdf
    from .db import set_literature_code_url, mark_pdf_scanned
    import time
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    filter_sources = (set(args.filter_source.split(","))
                      if args.filter_source else None)
    if args.rescan:
        todo = [r for r in rows
                if (filter_sources is None
                    or r.get("code_url_source") in filter_sources)]
    else:
        todo = [r for r in rows
                if not r.get("code_url") and not r.get("pdf_scanned_at")]
    if not todo:
        print("no papers left to scan (every link-less row already scanned).")
        return 0
    max_pages = args.max_pages if args.max_pages > 0 else None
    scope = f"first {max_pages} pages" if max_pages else "all pages"
    print(f"scanning {len(todo)} PDF(s) — {scope}, "
          f"{args.sleep:.1f}s between papers")
    n_filled, n_empty = 0, 0
    for i, p in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        try:
            url = extract_github_from_pdf(p["arxiv_id"], max_pages=max_pages)
        except Exception as exc:
            print(f"  ! {p['arxiv_id']}: {exc}")
            url = None
        if url:
            set_literature_code_url(args.db, p["arxiv_id"],
                                    code_url=url, source="pdf")
            print(f"  + {p['arxiv_id']} (pdf): {url}")
            n_filled += 1
        else:
            print(f"  - {p['arxiv_id']}: no repo link in {scope}")
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


def cmd_enrich_via_s2(args) -> int:
    """Backfill Semantic Scholar metadata for every literature row that
    doesn't have it yet. Adds tldr (often clearer than the abstract),
    influential_citation_count, and the S2 paperId for cross-API lookups.

    Per-paper status (200 / 404 / 429 / network) is printed so a low
    hit rate can be diagnosed (rate-limit blast vs paper genuinely
    not indexed). Rows that come back 404 are stamped `s2_fetched_at`
    so a re-run skips them; rows that hit 429 or network are NOT
    stamped, so the next run retries them."""
    from .semantic_scholar import (
        fetch_paper, sleep_for_rate_limit, _arxiv_base,
        _http_get_json_with_status, _S2_BASE, _PAPER_FIELDS,
    )
    import urllib.parse as _up
    from .db import set_s2_metadata
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if args.retry_missing:
        # Reconsider every row that doesn't actually have S2 data, regardless
        # of fetched_at. Useful after fixing the silent-429 swallowing bug,
        # where the old code stamped fetched_at on rows it never really
        # enriched.
        todo = [r for r in rows if not r.get("s2_paper_id")]
    else:
        todo = [r for r in rows
                if not r.get("s2_paper_id") and not r.get("s2_fetched_at")]
    if not todo:
        print("all rows already have S2 metadata. "
              "(use --retry-missing to re-fetch rows that came back empty)")
        return 0
    print(f"enriching {len(todo)} paper(s) via Semantic Scholar...")
    n_ok, n_404, n_429, n_other = 0, 0, 0, 0
    for i, r in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        url = (f"{_S2_BASE}/paper/ARXIV:{_up.quote(_arxiv_base(r['arxiv_id']))}"
               f"?fields={_PAPER_FIELDS}")
        status, raw = _http_get_json_with_status(url)
        # Single 429 retry in-loop (the generic _http_get_json wrapper does
        # this too, but we use the low-level call here for status visibility).
        if status == 429:
            sleep_for_rate_limit(12.0)
            status, raw = _http_get_json_with_status(url)
        if status == 200 and raw:
            tldr_obj = raw.get("tldr") or {}
            tldr = tldr_obj.get("text") if isinstance(tldr_obj, dict) else None
            infl = raw.get("influentialCitationCount")
            try:
                set_s2_metadata(
                    args.db, r["arxiv_id"],
                    s2_paper_id=raw.get("paperId"),
                    s2_tldr=tldr,
                    s2_influential_citation_count=infl,
                )
                print(f"  + {r['arxiv_id']:<16s} tldr={'Y' if tldr else 'N'} "
                      f"infl_cit={infl}")
                n_ok += 1
            except KeyError:
                pass
        elif status == 404:
            try:
                set_s2_metadata(
                    args.db, r["arxiv_id"],
                    s2_paper_id=None, s2_tldr=None,
                    s2_influential_citation_count=None,
                )
                print(f"  - {r['arxiv_id']:<16s} 404 (not indexed by S2)")
                n_404 += 1
            except KeyError:
                pass
        elif status == 429:
            print(f"  ! {r['arxiv_id']:<16s} 429 still rate-limited after backoff "
                  f"(NOT stamped — next run will retry)")
            n_429 += 1
        else:
            print(f"  ? {r['arxiv_id']:<16s} status={status} (NOT stamped)")
            n_other += 1
        sleep_for_rate_limit(args.sleep)
    print(f"\nenriched {n_ok}, 404 {n_404}, 429 {n_429}, other {n_other}.")
    if n_429 > 0:
        print("Tip: set SEMANTIC_SCHOLAR_API_KEY env var (free at "
              "https://www.semanticscholar.org/product/api#api-key-form) "
              "to lift the 100req/5min limit.")
    return 0


def cmd_coverage(args) -> int:
    """Render the (mechanism × stylized fact) coverage heatmap + markdown."""
    from .coverage import build_coverage, render_heatmap, render_markdown
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if not rows:
        print("no papers in literature_methods. Ingest first.", file=sys.stderr)
        return 1
    import os
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    cov = build_coverage(rows, top_rows=args.top_rows)
    png = os.path.join(out_dir, "coverage.png")
    md = os.path.join(out_dir, "coverage.md")
    render_heatmap(cov, png)
    with open(md, "w") as fh:
        fh.write(f"# Literature coverage matrix\n\n"
                 f"({cov['n_papers_classified']} / {cov['n_papers_total']} "
                 f"papers classified)\n\n")
        fh.write(render_markdown(cov))
        fh.write("\n")
    print(f"wrote {png}")
    print(f"wrote {md}")
    return 0


def cmd_atlas(args) -> int:
    """Render the literature_methods 2D map (PNG + CSV)."""
    from .literature_map import render_literature_map
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if not rows:
        print("no papers in literature_methods. Ingest first.", file=sys.stderr)
        return 1
    import os
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, "literature_map.png")
    csv = os.path.join(out_dir, "literature_map.csv")
    summary = render_literature_map(
        rows, png, csv_path=csv, top_labels=args.top_labels,
    )
    print(f"wrote {png}")
    print(f"wrote {csv}")
    print(json.dumps(summary, indent=2))
    return 0


def cmd_delete_rows(args) -> int:
    """Delete one or more literature_methods rows by arxiv_id.

    Use case: cleanup after an ingest that pulled the wrong papers
    (e.g. foundational_abm_ids.txt with truncated IDs where arxiv
    returned arbitrary papers from collision-cousin categories)."""
    import sqlite3
    ensure_literature_schema(args.db)
    ids = [s.strip() for s in args.arxiv_ids.split(",") if s.strip()]
    if not ids:
        print("no arxiv_ids given", file=sys.stderr)
        return 1
    rows = load_literature(args.db)
    by_id = {r["arxiv_id"]: r for r in rows}
    found = [aid for aid in ids if aid in by_id]
    missing = [aid for aid in ids if aid not in by_id]
    if missing:
        print(f"not in DB: {missing}", file=sys.stderr)
    if not found:
        return 1
    if not args.yes:
        print("would delete:")
        for aid in found:
            print(f"  {aid:<22s} {by_id[aid]['title'][:60]}")
        print(f"\nre-run with --yes to actually delete {len(found)} row(s).")
        return 0
    with sqlite3.connect(args.db) as con:
        for aid in found:
            con.execute(
                "DELETE FROM literature_methods WHERE arxiv_id = ?", (aid,)
            )
            print(f"  deleted {aid}")
        con.commit()
    print(f"\ndeleted {len(found)} row(s).")
    return 0


def cmd_extract_untagged(args) -> int:
    """Run LLM extraction on literature_methods rows that have no tags yet.

    Targets rows where `extracted_by_model` is NULL (never went through
    the LLM step — typically OA-only canon ingested by canon_ingest, and
    any rows that skipped extract=True). Only rows with a non-empty
    abstract are processed.

    Retry policy:
      - HTTP / network / rate-limit failures leave the row untagged and
        attempts unchanged — the next run will pick it up naturally.
      - LLM-returned-empty payloads (all-null summary + zero tags) bump
        extraction_attempts but leave extracted_by_model NULL, so the
        row is retried up to --max-attempts times (default 3), then
        parked.

    --sleep N inserts N seconds between calls to smooth TPM-based rate
    limits (Groq free tier is 8k TPM — a >3k-token request every 1s can
    trip this even with retry backoff)."""
    from time import sleep as _sleep
    from .arxiv_ingest import extract_paper_structured
    from .db import update_literature_extraction, record_extraction_attempt
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    max_attempts = args.max_attempts

    def _is_extraction_defective(row: dict) -> bool:
        """Row was 'extracted' but the payload is unusable. Either:
        (a) LLM gave nothing (empty summary + tags + relevance), OR
        (b) mechanism_tags contain non-ASCII — the extraction contract
            is English-only slugs; JA tokens split the coverage matrix
            on tag equality (bug that shipped when generate_japanese
            leaked into this path before the fix).
        Worth retrying under the corrected prompt.
        """
        if not row.get("extracted_by_model"):
            return False
        summary = (row.get("mechanism_summary") or "").strip()
        tags = row.get("mechanism_tags") or []
        rel = row.get("relevance_score")
        if not summary and not tags and rel is None:
            return True
        if any(not t.isascii() for t in tags):
            return True
        return False

    def _has_usable_abstract(row: dict) -> bool:
        a = (row.get("abstract") or "").strip()
        return bool(a) and not a.startswith("[no abstract available")

    untagged = [
        r for r in rows
        if not r.get("extracted_by_model")
        and _has_usable_abstract(r)
        and int(r.get("extraction_attempts") or 0) < max_attempts
    ]
    if args.retry_empty_past:
        defective = [r for r in rows
                      if _is_extraction_defective(r)
                      and _has_usable_abstract(r)]
        if defective:
            print(f"including {len(defective)} previously-defective row(s) "
                  f"for retry (empty payload or non-ASCII tags).")
            untagged.extend(defective)
    parked = [
        r for r in rows
        if not r.get("extracted_by_model")
        and int(r.get("extraction_attempts") or 0) >= max_attempts
    ]
    if parked:
        print(f"({len(parked)} row(s) parked — attempts ≥ {max_attempts}; "
              f"raise --max-attempts to keep trying.)")
    if not untagged:
        print("no untagged rows with usable abstract — nothing to do.")
        return 0

    if args.limit and len(untagged) > args.limit:
        untagged = untagged[: args.limit]

    print(f"found {len(untagged)} untagged row(s) to extract "
          f"({'DRY-RUN' if args.dry_run else 'live'}, "
          f"model={args.groq_model}, sleep={args.sleep}s).")

    if args.dry_run:
        for r in untagged[:20]:
            title = (r.get("title") or "")[:60]
            attempts = int(r.get("extraction_attempts") or 0)
            attempt_tag = f" (attempts={attempts})" if attempts else ""
            print(f"  would extract  {r['arxiv_id']:<22s}  {title}{attempt_tag}")
        if len(untagged) > 20:
            print(f"  ... and {len(untagged) - 20} more")
        return 0

    ok = empty = failed = 0
    for i, r in enumerate(untagged, start=1):
        paper = {
            "arxiv_id": r["arxiv_id"],
            "title": r.get("title") or "",
            "abstract": r.get("abstract") or "",
            "comment": r.get("arxiv_comment"),
        }
        try:
            ext = extract_paper_structured(paper, model=args.groq_model)
        except Exception as exc:
            failed += 1
            print(f"  [{i:>3d}/{len(untagged)}] FAIL {r['arxiv_id']:<22s} "
                  f"{type(exc).__name__}: {exc}",
                  file=sys.stderr)
            if args.sleep:
                _sleep(args.sleep)
            continue

        is_empty = (not ext["mechanism_summary"]
                    and not ext["mechanism_tags"]
                    and ext["relevance_score"] is None)
        if is_empty:
            record_extraction_attempt(args.db, r["arxiv_id"])
            empty += 1
            attempts_now = int(r.get("extraction_attempts") or 0) + 1
            print(f"  [{i:>3d}/{len(untagged)}] EMPTY {r['arxiv_id']:<22s} "
                  f"(attempt {attempts_now}/{max_attempts})")
        else:
            update_literature_extraction(
                args.db, r["arxiv_id"],
                mechanism_summary=ext["mechanism_summary"],
                mechanism_tags=ext["mechanism_tags"],
                stylized_facts_targeted=ext["stylized_facts_targeted"],
                novelty_signal=ext["novelty_signal"],
                relevance_score=ext["relevance_score"],
                extracted_by_model=ext["extracted_by_model"],
            )
            ok += 1
            tags = ", ".join(ext["mechanism_tags"][:3]) or "(summary-only)"
            print(f"  [{i:>3d}/{len(untagged)}] +ext  {r['arxiv_id']:<22s} "
                  f"{tags}")
        if args.sleep:
            _sleep(args.sleep)
    print(f"\ndone: extracted {ok}, empty {empty}, failed {failed}, "
          f"of {len(untagged)}.")
    return 0 if not failed else 2


def cmd_stylized_fact_other(args) -> int:
    """List papers whose stylized_facts_targeted contains 'other'.

    Use case: audit whether the LLM is dumping into the catch-all
    because (a) the enum is missing a legitimate fact, (b) the paper
    genuinely isn't about a stylized fact, or (c) the extractor was
    lazy. With --retag the row is re-run through extraction (the enum
    change may unstick it)."""
    from .arxiv_ingest import extract_paper_structured
    from .db import update_literature_extraction
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    only_other = []
    with_other = []
    for r in rows:
        facts = [f.strip().lower() for f in (r.get("stylized_facts_targeted") or [])]
        if not facts:
            continue
        if facts == ["other"]:
            only_other.append(r)
        elif "other" in facts:
            with_other.append(r)

    print(f"papers tagged with 'other' ONLY:  {len(only_other)}")
    print(f"papers with 'other' + something:  {len(with_other)}")
    total = len(only_other) + len(with_other)
    if not total:
        return 0

    subset = only_other + with_other
    if args.limit and len(subset) > args.limit:
        subset = subset[: args.limit]

    if not args.retag:
        for r in subset:
            facts = ", ".join(r.get("stylized_facts_targeted") or [])
            title = (r.get("title") or "")[:55]
            summary = (r.get("mechanism_summary") or "")[:90]
            print()
            print(f"  {r['arxiv_id']:<22s}  facts=[{facts}]")
            print(f"      title: {title}")
            print(f"      summary: {summary}")
        print(f"\n(showed {len(subset)}/{total}). "
              f"Re-run with --retag to re-extract them under the current "
              f"stylized-fact enum.")
        return 0

    print(f"re-extracting {len(subset)} row(s) with model={args.groq_model}...")
    ok = failed = still_other = 0
    for i, r in enumerate(subset, start=1):
        paper = {"arxiv_id": r["arxiv_id"], "title": r.get("title") or "",
                  "abstract": r.get("abstract") or "",
                  "comment": r.get("arxiv_comment")}
        try:
            ext = extract_paper_structured(paper, model=args.groq_model)
            update_literature_extraction(
                args.db, r["arxiv_id"],
                mechanism_summary=ext["mechanism_summary"],
                mechanism_tags=ext["mechanism_tags"],
                stylized_facts_targeted=ext["stylized_facts_targeted"],
                novelty_signal=ext["novelty_signal"],
                relevance_score=ext["relevance_score"],
                extracted_by_model=ext["extracted_by_model"],
            )
            new_facts = ext["stylized_facts_targeted"]
            if new_facts == ["other"] or (len(new_facts) == 1 and "other" in new_facts):
                still_other += 1
                mark = "still-other"
            else:
                ok += 1
                mark = ", ".join(new_facts[:3]) or "(no facts)"
            print(f"  [{i:>3d}/{len(subset)}]  {r['arxiv_id']:<22s} → {mark}")
        except Exception as exc:
            failed += 1
            print(f"  [{i:>3d}/{len(subset)}]  {r['arxiv_id']:<22s} FAIL "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"\ndone: {ok} reclassified, {still_other} still 'other', "
          f"{failed} failed.")
    return 0 if not failed else 2


def cmd_fix_arxiv_ids(args) -> int:
    """One-shot migration: scan DB for arxiv_ids that look like an old-style
    paper with the category prefix stripped (e.g. '0101326v1' that should
    be 'cond-mat/0101326v1'). Recover the canonical form by searching
    OpenAlex by the row's title — the arxiv API itself rejects the bare
    truncated id with HTTP 400 (needs the category prefix that was lost).

    Pre-2007 arxiv IDs are 7 digits, e.g. 0103089v1. New-style IDs are
    YYMM.NNNNN. Anything matching the old shape with no '/' is suspect."""
    from .openalex import search_by_title, sleep_for_rate_limit
    import sqlite3
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    suspect_re = re.compile(r"^\d{7}(v\d+)?$")
    suspects = [r for r in rows if suspect_re.match(r["arxiv_id"])]
    if not suspects:
        print("no rows with old-style arxiv_id missing a category prefix.")
        return 0
    print(f"found {len(suspects)} suspect row(s); recovering canonical "
          "arxiv_id via OpenAlex title search...")
    fixes: list[tuple[str, str]] = []
    n_miss = 0
    for r in suspects:
        result = search_by_title(r["title"], year=r.get("year"))
        if not result or not result.get("arxiv_id"):
            print(f"  - {r['arxiv_id']:<16s} no canonical id found "
                  f"(title: {r['title'][:50]}...)")
            n_miss += 1
            sleep_for_rate_limit(args.sleep)
            continue
        # Preserve version suffix from the original id if present
        version_match = re.search(r"(v\d+)$", r["arxiv_id"])
        canonical = result["arxiv_id"]
        if "/" not in canonical:
            print(f"  ? {r['arxiv_id']:<16s} OpenAlex returned non-prefixed "
                  f"id {canonical!r} (skipping)")
            n_miss += 1
            sleep_for_rate_limit(args.sleep)
            continue
        if version_match:
            canonical = canonical + version_match.group(1)
        if canonical == r["arxiv_id"]:
            print(f"  = {r['arxiv_id']}: already canonical")
            sleep_for_rate_limit(args.sleep)
            continue
        fixes.append((r["arxiv_id"], canonical))
        print(f"  + {r['arxiv_id']:<16s} → {canonical}")
        sleep_for_rate_limit(args.sleep)
    if args.dry_run:
        print(f"\n(dry-run) would update {len(fixes)} row(s), miss {n_miss}.")
        return 0
    if not fixes:
        print(f"\nnothing to update (miss {n_miss}).")
        return 0
    with sqlite3.connect(args.db) as con:
        for old, new in fixes:
            con.execute(
                "UPDATE literature_methods SET arxiv_id = ? WHERE arxiv_id = ?",
                (new, old),
            )
        con.commit()
    print(f"\nupdated {len(fixes)} row(s), miss {n_miss}.")
    return 0


def cmd_strip_arxiv_versions(args) -> int:
    """One-shot migration: drop the vN suffix from every literature_methods
    arxiv_id. Idempotent — arxiv_ids without a version are left alone.

    Companion to the same fix in `_extract_arxiv_id_from_entry`: without
    this pass, a DB that was ingested before the vN-strip fix will grow
    duplicate rows (e.g. 'cond-mat/0101326v1' from the legacy row AND
    'cond-mat/0101326' from the next ingest of the same paper).

    Conflict handling: if a row with the base id already exists we KEEP
    the base row and DELETE the vN one (the base is preferred because
    that's what new code will look up). All metadata columns from the
    vN row are lost — dry-run first to see what would be dropped.
    """
    import sqlite3
    ensure_literature_schema(args.db)
    with sqlite3.connect(args.db) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT arxiv_id, title FROM literature_methods "
            "WHERE arxiv_id GLOB '*v[0-9]' OR arxiv_id GLOB '*v[0-9][0-9]'"
        ).fetchall()
        if not rows:
            print("no rows with a vN suffix — nothing to do.")
            return 0

        base_ids = {r[0] for r in con.execute(
            "SELECT arxiv_id FROM literature_methods "
            "WHERE arxiv_id NOT GLOB '*v[0-9]' AND arxiv_id NOT GLOB '*v[0-9][0-9]'"
        ).fetchall()}

        renames: list[tuple[str, str]] = []
        conflicts: list[tuple[str, str, str]] = []
        for r in rows:
            base = re.sub(r"v\d+$", "", r["arxiv_id"])
            if base in base_ids:
                conflicts.append((r["arxiv_id"], base, r["title"]))
            else:
                renames.append((r["arxiv_id"], base))
                base_ids.add(base)

        print(f"found {len(rows)} row(s) with vN suffix:")
        for old, new in renames:
            print(f"  rename  {old:<24s} → {new}")
        for old, base, title in conflicts:
            print(f"  DELETE  {old:<24s} (base {base} already exists)")
            print(f"            title was: {title[:60]}")

        if args.dry_run:
            print(f"\n(dry-run) would rename {len(renames)}, "
                  f"delete {len(conflicts)}. Re-run with --yes to commit.")
            return 0
        if not args.yes:
            print(f"\nre-run with --yes to commit ({len(renames)} rename, "
                  f"{len(conflicts)} delete).")
            return 0

        for old, new in renames:
            con.execute(
                "UPDATE literature_methods SET arxiv_id = ? WHERE arxiv_id = ?",
                (new, old),
            )
        for old, _, _ in conflicts:
            con.execute(
                "DELETE FROM literature_methods WHERE arxiv_id = ?", (old,)
            )
        con.commit()
    print(f"\nrenamed {len(renames)}, deleted {len(conflicts)}.")
    return 0


def cmd_diagnose_concept(args) -> int:
    """Show what OpenAlex /concepts and /works return for a search query.
    Useful when 'canon' / 'genealogy' returns 'no concept matches'."""
    from .openalex import (
        _http_get_json_with_status, _OA_BASE, find_concept_id,
    )
    import urllib.parse as _up
    q = _up.quote(args.name)
    url1 = f"{_OA_BASE}/concepts?search={q}&per-page=5"
    print(f"GET {url1}")
    status, body = _http_get_json_with_status(url1)
    print(f"status: {status}")
    if body and isinstance(body.get("results"), list):
        print(f"  results ({len(body['results'])}):")
        for c in body["results"][:5]:
            print(f"    {c.get('id'):<40s}  {c.get('display_name')!r}  "
                  f"(works: {c.get('works_count')})")
    else:
        print(f"  body keys: {list(body.keys()) if body else None}")

    url2 = f"{_OA_BASE}/works?search={q}&per-page=5&select=id,title,concepts"
    print(f"\nGET {url2}")
    status, body = _http_get_json_with_status(url2)
    print(f"status: {status}")
    if body and isinstance(body.get("results"), list):
        print(f"  top works' concepts:")
        for w in body["results"][:5]:
            concepts = [(c.get("display_name"), c.get("id"))
                        for c in (w.get("concepts") or [])[:4]]
            print(f"    {(w.get('title') or '')[:55]!r}")
            for name, cid in concepts:
                print(f"      - {name} ({cid})")

    resolved = find_concept_id(args.name)
    print(f"\nfind_concept_id resolved to: {resolved!r}")
    return 0


def cmd_genealogy(args) -> int:
    """Build a forward-citation tree from a root paper and render it as
    an interactive HTML force-graph (vis-network, CDN-loaded — no install).

    The root can be specified two ways:
      --root-arxiv-id X   resolve via OpenAlex
      --root-concept Y    pick the top-cited paper under that concept (the
                          'canon') and use it as root
    """
    from .openalex import find_canon_papers, fetch_paper
    from .genealogy import build_tree, filter_tree, render_html
    import os
    if args.root_arxiv_id:
        meta = fetch_paper(args.root_arxiv_id)
        if not meta:
            print(f"could not resolve arxiv_id={args.root_arxiv_id!r} via OpenAlex",
                  file=sys.stderr)
            return 1
        root_oa_id = meta["oa_paper_id"]
        root_label = f"arxiv:{args.root_arxiv_id}"
        root_arxiv_id = args.root_arxiv_id
        root_title = meta.get("title")
        root_year = meta.get("year")
        root_cit = meta.get("cited_by_count")
    elif args.root_concept:
        print(f"finding canon paper under concept {args.root_concept!r}...")
        canon = find_canon_papers(args.root_concept, n=1,
                                    year_max=args.year_max)
        if not canon:
            print(f"no canon paper for concept {args.root_concept!r}",
                  file=sys.stderr)
            return 1
        root = canon[0]
        root_oa_id = root["oa_paper_id"]
        root_arxiv_id = root.get("arxiv_id")
        root_title = root.get("title")
        root_year = root.get("year")
        root_cit = root.get("cited_by_count")
        root_label = f"canon[{args.root_concept}]"
        print(f"root: {root_title!r} ({root_year}, {root_cit} cites)")
    else:
        print("--root-arxiv-id or --root-concept required", file=sys.stderr)
        return 1

    print(f"walking forward citations: depth={args.depth}, "
          f"per_node={args.per_node}, min_cited_by={args.min_cited_by}")
    print("(this can take a few minutes for depth=2)")
    tree = build_tree(
        root_oa_id, root_arxiv_id=root_arxiv_id, root_title=root_title,
        root_year=root_year, root_cit=root_cit,
        depth=args.depth, per_node=args.per_node,
        min_cited_by=args.min_cited_by, sleep=args.sleep,
    )
    if args.keywords:
        before = len(tree["nodes"])
        excluded = args.exclude_keywords.split(",") if args.exclude_keywords else []
        tree = filter_tree(tree, args.keywords.split(","), excluded)
        print(f"topical filter: kept {len(tree['nodes'])}/{before} nodes")
    print(f"\ntree: {len(tree['nodes'])} nodes, {len(tree['edges'])} edges")

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    os.makedirs(out_dir, exist_ok=True)
    title = f"{root_label}  ·  forward citations, depth {args.depth}"
    render_html(tree, args.out, title=title)
    print(f"wrote {args.out}")
    print(f"open in browser to view the interactive graph.")
    return 0


def cmd_canon(args) -> int:
    """Surface the canon (top-cited papers) under an OpenAlex concept.

    For each subfield (Minority Game / Leverage Effect / Order Book etc),
    the canon is the small set of papers that nearly every later paper in
    that subfield cites. Found by querying OpenAlex for highest-cited
    works under the concept tag. Optional --auto-ingest pulls the ones
    that are on arxiv into the literature DB."""
    from .openalex import find_canon_papers
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    already_in_db = {re.sub(r"v\d+$", "", r["arxiv_id"]) for r in rows}

    # find_canon_papers handles concept-id resolution AND a search
    # fallback for narrow subfields OpenAlex doesn't have as a concept.
    canon = find_canon_papers(args.concept, n=args.n, year_max=args.year_max)
    if not canon:
        print(f"no canon papers returned for {args.concept!r}.")
        return 1
    print(f"top {len(canon)} canon paper(s) for {args.concept!r}:")
    arxiv_candidates: list[str] = []
    for r in canon:
        aid = r.get("arxiv_id")
        in_db_flag = ""
        if aid and re.sub(r"v\d+$", "", aid) in already_in_db:
            in_db_flag = " [in DB]"
        elif aid:
            arxiv_candidates.append(aid)
        cit = r.get("cited_by_count") or 0
        year = r.get("year") or "?"
        title = (r.get("title") or "")[:65]
        arxiv_tag = f"arxiv:{aid}" if aid else "(no-arxiv)"
        print(f"  [{cit:>5d} cit] {year}  {arxiv_tag:<28s} {title}{in_db_flag}")

    if args.auto_ingest and arxiv_candidates:
        from .arxiv_ingest import ingest_by_ids
        print(f"\nauto-ingesting {len(arxiv_candidates)} arxiv-hosted canon "
              f"paper(s) not yet in DB...")
        summary = ingest_by_ids(
            args.db, arxiv_candidates, extract=True,
            groq_model=args.groq_model,
            min_relevance_to_keep=args.min_relevance_to_keep,
            verbose=True,
        )
        print(json.dumps({k: v for k, v in summary.items() if k != "errors"},
                          indent=2))
    elif not args.auto_ingest:
        print(f"\nto ingest the {len(arxiv_candidates)} arxiv-hosted canon "
              f"paper(s) not yet in DB: re-run with --auto-ingest")
    return 0


def cmd_glossary(args) -> int:
    """Personal English↔Japanese terminology dictionary.

    Subcommands:
      list    — print every entry grouped by domain
      lookup  — show one entry by English key
      search  — substring match across en / ja / notes
    """
    from .glossary import GLOSSARY, lookup, search, all_domains
    if args.sub == "list":
        by_dom: dict[str, list] = {}
        for e in GLOSSARY:
            by_dom.setdefault(e.get("domain", "general"), []).append(e)
        for dom in all_domains():
            entries = by_dom.get(dom, [])
            if not entries:
                continue
            print(f"\n=== {dom} ({len(entries)}) ===")
            for e in entries:
                print(f'  "{e["en"]}" → {e["ja_primary"]}')
                also = e.get("ja_also") or []
                if also:
                    print(f"      also: {', '.join(also)}")
                for a in (e.get("avoid") or []):
                    print(f"      reject: {a['bad']} — {a['why']}")
        return 0
    if args.sub == "lookup":
        if not args.term:
            print("usage: glossary lookup <en-term>", file=sys.stderr)
            return 2
        e = lookup(args.term)
        if not e:
            print(f"no entry for {args.term!r}", file=sys.stderr)
            return 1
        print(json.dumps(e, indent=2, ensure_ascii=False))
        return 0
    if args.sub == "search":
        if not args.term:
            print("usage: glossary search <query>", file=sys.stderr)
            return 2
        hits = search(args.term)
        if not hits:
            print(f"no match for {args.term!r}")
            return 0
        for e in hits:
            print(f'  [{e.get("domain","general"):<14}] '
                  f'"{e["en"]}" → {e["ja_primary"]}')
        return 0
    if args.sub == "prompt":
        from .glossary import format_for_prompt
        print(format_for_prompt(domain=args.domain))
        return 0
    print(f"unknown subcommand {args.sub!r}", file=sys.stderr)
    return 2


def cmd_gap_propose(args) -> int:
    """Run gap-mine, take top-N gaps, generate proposals via LLM, insert
    into the `proposals` table with proposal_type='gap_mine'."""
    from .gap_propose import propose_from_top_gaps
    import sqlite3
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    with sqlite3.connect(args.db) as con:
        runs = [{"model_name": r[0], "fingerprint_json": r[1]}
                 for r in con.execute(
                     "SELECT model_name, fingerprint_json FROM runs"
                 ).fetchall()]

    print(f"corpus: {len(rows)} papers, {len(runs)} runs")
    print(f"generating proposals for top {args.top} gaps "
          f"(model: {args.groq_model}, dry-run: {args.dry_run})...")
    created = propose_from_top_gaps(
        args.db, rows=rows, runs=runs, top_n=args.top,
        llm_model=args.groq_model, dry_run=args.dry_run,
    )
    print(f"\ngenerated {len(created)} proposal candidate(s):\n")
    for i, p in enumerate(created, 1):
        if "error" in p:
            g = p["_gap"]
            print(f"  [{i}] FAIL: {g['view']} {g['row']} × {g['col']}")
            print(f"      └─ {p['error']}")
            continue
        gap = p.get("_gap", {})
        pid = p.get("id")
        id_str = f"#{pid}" if pid is not None else "(dry)"
        print(f"  [{i}] {id_str} target={p['target_model']} "
              f"← gap {gap.get('view')} "
              f"{gap.get('row')} × {gap.get('col')}")
        print(f"      rationale: {p['rationale'][:160]}")
        if p.get("references"):
            print(f"      refs: {', '.join(p['references'][:3])}")
    return 0


def cmd_gap_mine(args) -> int:
    """Detect under-explored cells in the (subfield × stylized-fact),
    (abm_family × stylized-fact), and (technique × subfield) views.
    Surfaces the top-N research gaps sorted by salience."""
    from .gap_finder import find_gaps
    from .i18n import (
        translate_gap_row_col, family_gloss, fact_gloss, view_label,
        view_gloss,
    )
    import sqlite3
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    with sqlite3.connect(args.db) as con:
        runs = [{"model_name": r[0], "fingerprint_json": r[1]}
                 for r in con.execute(
                     "SELECT model_name, fingerprint_json FROM runs"
                 ).fetchall()]

    views, top = find_gaps(rows, runs, top_n=args.top)
    print(f"corpus: {len(rows)} papers, {len(runs)} runs")
    for v in views:
        nonzero = int((v.matrix > 0).sum()) if v.matrix.size else 0
        total = int(v.matrix.sum()) if v.matrix.size else 0
        ja = view_label(v.name)
        print(f"  view {v.name} [{ja}]: {v.matrix.shape[0]}×"
              f"{v.matrix.shape[1]}, {nonzero} non-zero, sum={total}")
        print(f"     └─ {view_gloss(v.name)}")

    print(f"\ntop {len(top)} gaps:\n")
    for g in top:
        row_ja, col_ja = translate_gap_row_col(g.view, g.row, g.col)
        print(f"  [{g.view}] sal={g.salience:.2f}  {row_ja[:36]:36} × "
              f"{col_ja[:22]:22}")
        print(f"      └─ {g.why}")
        # Gloss the keys so the user knows what they refer to
        if g.view == "B":
            fg = family_gloss(g.row)
            sg = fact_gloss(g.col)
            if fg:
                print(f"         {g.row}: {fg}")
            if sg:
                print(f"         {g.col}: {sg}")
        elif g.view == "A":
            sg = fact_gloss(g.col)
            if sg:
                print(f"         {g.col}: {sg}")
    if args.json:
        out = [{"view": g.view, "row": g.row, "col": g.col,
                "value": g.value, "salience": g.salience,
                "row_total": g.row_total, "col_total": g.col_total,
                "why": g.why} for g in top]
        print()
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_canon_atlas(args) -> int:
    """Sweep every subfield in subfields.SUBFIELDS, run canon detection,
    join with the local literature DB, render a single self-contained
    HTML page (heatmap + per-subfield detail sections).

    Optional --auto-ingest-missing pulls every arxiv-hosted canon paper
    not yet in DB through arxiv_ingest in one batch — single command to
    close the canon-coverage gap across the whole atlas."""
    from .canon_atlas import (build_atlas, render_html, missing_canon,
                                _oa_work_id)
    from .canon_ingest import is_openalex_synthetic_id
    from .subfields import SUBFIELDS
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    # Real arxiv ids only (skip oa: synthetic ids — those are matched via
    # db_oa_ids instead). OA work ids come from the oa_paper_id column.
    db_arxiv_ids = {r["arxiv_id"] for r in rows
                     if r.get("arxiv_id")
                     and not is_openalex_synthetic_id(r["arxiv_id"])}
    db_oa_ids: set[str] = set()
    for r in rows:
        work = _oa_work_id(r.get("oa_paper_id"))
        if work:
            db_oa_ids.add(work)

    subfields = SUBFIELDS
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        subfields = [s for s in SUBFIELDS if s["key"] in wanted]
        if not subfields:
            print(f"no subfield matches --only={args.only!r}. "
                  f"Available keys: "
                  f"{', '.join(s['key'] for s in SUBFIELDS)}", file=sys.stderr)
            return 1

    print(f"building canon atlas for {len(subfields)} subfield(s)...")
    print("(this takes ~30-60s — one OpenAlex call per subfield)")
    atlas = build_atlas(subfields, db_arxiv_ids=db_arxiv_ids,
                         db_oa_ids=db_oa_ids,
                         n_per_subfield=args.n, year_max=args.year_max,
                         sleep=args.sleep)

    # Print a one-line per-subfield summary so users can see progress
    # without opening the HTML. n_canon is the OpenAlex search hit count
    # (top-cited); coverage is n_in_db / n_canon — every canon paper is
    # now ingestable (arxiv path for arxiv-hosted, OA-metadata path for
    # journal-only).
    print()
    for entry in atlas:
        cov = entry["coverage"]
        cov_txt = ("ERR" if entry.get("error") else
                   ("  —" if cov is None else f"{int(round(cov * 100)):>3d}%"))
        marker = " (seed-fallback)" if entry.get("fallback_used") else ""
        print(f"  [{cov_txt}] {entry['n_in_db']:>2d}/{entry['n_canon']:>2d} "
              f"canon ({entry['n_on_arxiv']} on arxiv)  ·  {entry['name']}"
              f"{marker}")

    render_html(atlas, args.out)
    print(f"\nwrote {args.out}")

    failed = [entry for entry in atlas if entry.get("error")]
    if failed:
        # Distinguish transient upstream outages (5xx / 429) from lookup
        # misses so the user knows whether to retry vs edit subfields.py.
        errors = " ".join(str(e.get("error") or "") for e in failed)
        upstream = any(f"HTTP {c}" in errors for c in (429, 502, 503, 504))
        anon = not os.environ.get("OPENALEX_API_KEY")
        if upstream and anon:
            hint = (" — OpenAlex is 503'ing anonymous search traffic under "
                    "heavy load. Get a free API key at "
                    "https://openalex.org/settings/api and export it as "
                    "OPENALEX_API_KEY. Authenticated requests are served "
                    f"from the reliable pool. Fallback covered "
                    f"{sum(1 for e in atlas if e.get('fallback_used'))} "
                    "subfield(s) in this run.")
        elif upstream:
            hint = (" — OpenAlex 5xx/429 despite key set; retry in a few "
                    "minutes. Fallback covered "
                    f"{sum(1 for e in atlas if e.get('fallback_used'))} "
                    "subfield(s) in this run.")
        else:
            hint = ""
        print(f"\nERROR: OpenAlex lookup failed for {len(failed)} subfield(s); "
              f"coverage is incomplete and auto-ingest was skipped.{hint}",
              file=sys.stderr)
        return 2

    missing = missing_canon(atlas)
    n_arxiv = len(missing["arxiv"])
    n_oa = len(missing["oa_only"])
    if not n_arxiv and not n_oa:
        print("all canon papers are in DB — coverage is complete.")
        return 0

    print(f"\n{n_arxiv} arxiv-hosted + {n_oa} journal-only canon paper(s) "
          f"are not yet in DB.")

    if not args.auto_ingest_missing:
        print(f"re-run with --auto-ingest-missing to pull them "
              f"(arxiv path for {n_arxiv}, OA-metadata path for {n_oa}).")
        return 0

    if n_arxiv:
        from .arxiv_ingest import ingest_by_ids
        print(f"\n[arxiv path] ingesting {n_arxiv} canon paper(s)...")
        s_arxiv = ingest_by_ids(
            args.db, missing["arxiv"], extract=True,
            groq_model=args.groq_model,
            min_relevance_to_keep=args.min_relevance_to_keep,
            verbose=True,
        )
        print(json.dumps({k: v for k, v in s_arxiv.items() if k != "errors"},
                          indent=2))

    if n_oa:
        from .canon_ingest import ingest_canon_via_oa
        print(f"\n[OA-metadata path] ingesting {n_oa} journal-only canon "
              f"paper(s) (no PDF; abstract from OA inverted_index)...")
        s_oa = ingest_canon_via_oa(args.db, missing["oa_only"],
                                     sleep=args.sleep, verbose=True)
        print(json.dumps({k: v for k, v in s_oa.items() if k != "errors"},
                          indent=2))
    return 0


def cmd_dashboard(args) -> int:
    """Build the static multi-page research dashboard."""
    import os
    import sqlite3

    from .dashboard import build_dashboard

    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    with sqlite3.connect(args.db) as con:
        try:
            runs = [{"model_name": r[0], "fingerprint_json": r[1]}
                     for r in con.execute(
                         "SELECT model_name, fingerprint_json FROM runs"
                     ).fetchall()]
        except sqlite3.OperationalError:
            runs = []
    pages = build_dashboard(
        rows,
        args.out_dir,
        repo_root=os.getcwd(),
        canon_atlas=args.canon_atlas,
        runs=runs,
        db_path=args.db,
    )
    print(f"wrote {len(pages)} dashboard pages to {args.out_dir}")
    print(f"open {pages[0]}")
    return 0


def cmd_enrich_via_oa(args) -> int:
    """OpenAlex equivalent of enrich-via-s2 — no API key required, 10
    req/s rate limit. Stores cited_by_count + top concepts + OA paperId."""
    from .openalex import fetch_paper, sleep_for_rate_limit
    from .db import set_oa_metadata
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if args.retry_missing:
        todo = [r for r in rows if not r.get("oa_paper_id")]
    else:
        todo = [r for r in rows
                if not r.get("oa_paper_id") and not r.get("oa_fetched_at")]
    if not todo:
        print("all rows already have OpenAlex metadata. "
              "(use --retry-missing to re-fetch rows that came back empty)")
        return 0
    print(f"enriching {len(todo)} paper(s) via OpenAlex...")
    n_ok, n_miss = 0, 0
    for i, r in enumerate(todo):
        if args.limit and i >= args.limit:
            print(f"  (--limit {args.limit} reached, stopping)")
            break
        paper = fetch_paper(r["arxiv_id"])
        if paper:
            concepts_str = ", ".join(paper["concepts"][:3])
            try:
                set_oa_metadata(
                    args.db, r["arxiv_id"],
                    oa_paper_id=paper["oa_paper_id"],
                    oa_cited_by_count=paper["cited_by_count"],
                    oa_concepts=concepts_str,
                )
                cit = paper["cited_by_count"] or 0
                print(f"  + {r['arxiv_id']:<16s} cit={cit:<4d}  "
                      f"concepts=[{concepts_str[:55]}]")
                n_ok += 1
            except KeyError:
                pass
        else:
            try:
                set_oa_metadata(
                    args.db, r["arxiv_id"],
                    oa_paper_id=None, oa_cited_by_count=None,
                    oa_concepts=None,
                )
                print(f"  - {r['arxiv_id']:<16s} not found on OpenAlex")
                n_miss += 1
            except KeyError:
                pass
        sleep_for_rate_limit(args.sleep)
    print(f"\nenriched {n_ok}, missing {n_miss}.")
    return 0


def cmd_expand_via_oa(args) -> int:
    """OpenAlex equivalent of expand-via-s2. Walks each seed paper's
    referenced_works, resolves each ref to find the arxiv_id (if any),
    deduplicates against the existing DB, prints the top-K most-cited
    new candidates. --auto-ingest brings them in.

    Per-seed log includes n_refs so empty-referenced_works (common for
    recent papers in OpenAlex) is visible at a glance."""
    from .openalex import fetch_paper, fetch_references, sleep_for_rate_limit
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if args.from_arxiv_id:
        seed_papers = [r for r in rows if r["arxiv_id"] == args.from_arxiv_id]
        if not seed_papers:
            print(f"no row for arxiv_id={args.from_arxiv_id!r}", file=sys.stderr)
            return 1
    elif args.all_seeds_since:
        # Every DB row published >= YEAR. Older papers (≤2020) usually
        # have non-empty referenced_works in OpenAlex; recent ones get
        # auto-skipped by the n_refs==0 check below.
        seed_papers = sorted(
            (r for r in rows
             if r.get("year") is not None and r["year"] >= args.all_seeds_since),
            key=lambda r: r["year"],  # oldest first → richest citation data
        )
    else:
        seed_papers = sorted(
            (r for r in rows if r.get("relevance_score") is not None),
            key=lambda r: -(r["relevance_score"] or 0.0),
        )[:args.top_seeds]
    already_in_db = {re.sub(r"v\d+$", "", r["arxiv_id"]) for r in rows}
    candidates: dict[str, dict] = {}
    total_refs_walked = 0
    n_empty_seeds = 0
    print(f"walking references of {len(seed_papers)} seed paper(s)...")
    for i, seed in enumerate(seed_papers):
        if args.limit and i >= args.limit:
            print(f"(--limit {args.limit} reached, stopping seed walk)")
            break
        # Look up n_refs first so empty-referenced_works seeds get a
        # visible "no refs" message — otherwise the user sees "0 candidates"
        # at the end with no idea why.
        seed_paper = fetch_paper(seed["arxiv_id"])
        n_refs = len(seed_paper["referenced_works"]) if seed_paper else 0
        title = (seed.get("title") or "")[:60]
        if n_refs == 0:
            print(f"  - {seed['arxiv_id']} (n_refs=0)  {title}  "
                  "[empty referenced_works — common for recent papers in OpenAlex]")
            n_empty_seeds += 1
            continue
        refs_to_walk = min(n_refs, args.refs_per_seed)
        print(f"walking {refs_to_walk}/{n_refs} refs of {seed['arxiv_id']} — {title}")
        refs = fetch_references(seed["arxiv_id"], limit=args.refs_per_seed,
                                 sleep=args.sleep)
        total_refs_walked += len(refs)
        for ref in refs:
            aid = ref.get("arxiv_id")
            if not aid:
                continue
            base = re.sub(r"v\d+$", "", aid)
            if base in already_in_db:
                continue
            cur = candidates.get(base)
            if cur is None or ((ref.get("cited_by_count") or 0)
                                > (cur.get("cited_by_count") or 0)):
                candidates[base] = ref
        sleep_for_rate_limit(args.sleep)
    print(f"\nwalked {total_refs_walked} refs across "
          f"{len(seed_papers) - n_empty_seeds} non-empty seed(s); "
          f"{n_empty_seeds} seed(s) had empty referenced_works.")
    if not candidates:
        print("\nno new arxiv-hosted candidates discovered.")
        return 0
    ranked = sorted(candidates.values(),
                    key=lambda r: -(r.get("cited_by_count") or 0))
    print(f"\ndiscovered {len(ranked)} candidate(s):")
    for r in ranked[:args.top_candidates]:
        cit = r.get("cited_by_count") or 0
        print(f"  [{cit:>4d} cites] {r['arxiv_id']:<16s} "
              f"({r.get('year') or '?'})  {(r.get('title') or '')[:70]}")
    if args.auto_ingest:
        from .arxiv_ingest import ingest_by_ids
        ids = [r["arxiv_id"] for r in ranked[:args.top_candidates]]
        print(f"\nauto-ingesting {len(ids)} paper(s)...")
        summary = ingest_by_ids(
            args.db, ids, extract=True,
            groq_model=args.groq_model,
            min_relevance_to_keep=args.min_relevance_to_keep,
            verbose=True,
        )
        print(json.dumps({k: v for k, v in summary.items() if k != "errors"}, indent=2))
    else:
        print(f"\nto ingest these: re-run with --auto-ingest.")
    return 0


def cmd_diagnose_oa(args) -> int:
    """Single-paper deep-dive against OpenAlex."""
    from .openalex import _http_get_json_with_status, _arxiv_doi, _OA_BASE
    import urllib.parse as _up
    url = f"{_OA_BASE}/works/doi:{_up.quote(_arxiv_doi(args.arxiv_id))}"
    print(f"GET {url}\n")
    status, body = _http_get_json_with_status(url)
    print(f"status: {status}")
    if body is None:
        print("body  : None")
    else:
        print(f"        title  = {body.get('title')!r}")
        print(f"        cit    = {body.get('cited_by_count')}")
        concepts = [c.get("display_name") for c in (body.get("concepts") or [])[:5]
                    if isinstance(c, dict)]
        print(f"        concepts = {concepts}")
        print(f"        n_refs = {len(body.get('referenced_works') or [])}")
    return 0


def cmd_diagnose_s2(args) -> int:
    """Single-paper deep-dive: print the raw S2 response (status + body
    snippet) so a low-hit-rate enrich-via-s2 can be diagnosed."""
    from .semantic_scholar import (
        _arxiv_base, _http_get_json_with_status, _S2_BASE, _PAPER_FIELDS,
    )
    import urllib.parse as _up
    base = _arxiv_base(args.arxiv_id)
    url = (f"{_S2_BASE}/paper/ARXIV:{_up.quote(base)}"
           f"?fields={_PAPER_FIELDS}")
    print(f"GET {url}\n")
    status, body = _http_get_json_with_status(url)
    print(f"status: {status}")
    if body is None:
        print("body  : None (no parsed JSON)")
    else:
        # Show keys + a snippet of the most informative fields
        print(f"body  : keys = {sorted(body.keys())[:10]}")
        if "title" in body:
            print(f"        title  = {body['title']!r}")
        if "tldr" in body:
            tldr_text = (body["tldr"] or {}).get("text") if body["tldr"] else None
            print(f"        tldr   = {tldr_text!r}")
        if "influentialCitationCount" in body:
            print(f"        infl_cit = {body['influentialCitationCount']}")
        if "externalIds" in body:
            print(f"        externalIds = {body['externalIds']}")
    return 0


def cmd_expand_via_s2(args) -> int:
    """Walk each paper's references via S2 and report arxiv-hosted prior
    work that isn't yet in our DB. By default only PRINTS candidates so the
    user can review; pass --auto-ingest to bring them in via ingest-ids."""
    from .semantic_scholar import fetch_references, sleep_for_rate_limit
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if args.from_arxiv_id:
        seed_papers = [r for r in rows if r["arxiv_id"] == args.from_arxiv_id]
        if not seed_papers:
            print(f"no row for arxiv_id={args.from_arxiv_id!r}", file=sys.stderr)
            return 1
    else:
        # Default: walk references of the top N most-relevant papers.
        seed_papers = sorted(
            (r for r in rows if r.get("relevance_score") is not None),
            key=lambda r: -(r["relevance_score"] or 0.0),
        )[:args.top_seeds]
    already_in_db: set[str] = {
        re.sub(r"v\d+$", "", r["arxiv_id"]) for r in rows
    }
    candidates: dict[str, dict] = {}  # arxiv_base → ref entry
    for i, seed in enumerate(seed_papers):
        if args.limit and i >= args.limit:
            print(f"(--limit {args.limit} reached, stopping seed walk)")
            break
        print(f"walking references of {seed['arxiv_id']} — {seed['title'][:60]}")
        refs = fetch_references(seed["arxiv_id"], limit=args.refs_per_seed)
        for ref in refs:
            aid = ref.get("arxiv_id")
            if not aid:
                continue
            base = re.sub(r"v\d+$", "", aid)
            if base in already_in_db:
                continue
            # Prefer the entry with the higher influential citation count
            cur = candidates.get(base)
            if cur is None or ((ref.get("influential_citation_count") or 0)
                                > (cur.get("influential_citation_count") or 0)):
                candidates[base] = ref
        sleep_for_rate_limit(args.sleep)
    if not candidates:
        print("\nno new arxiv-hosted candidates discovered.")
        return 0
    ranked = sorted(
        candidates.values(),
        key=lambda r: -(r.get("influential_citation_count") or 0),
    )
    print(f"\ndiscovered {len(ranked)} candidate(s):")
    for r in ranked[:args.top_candidates]:
        infl = r.get("influential_citation_count")
        print(f"  [{infl or 0:>3d} infl cites] {r['arxiv_id']:<16s} "
              f"({r.get('year') or '?'})  {(r.get('title') or '')[:70]}")
    if args.auto_ingest:
        from .arxiv_ingest import ingest_by_ids
        ids = [r["arxiv_id"] for r in ranked[:args.top_candidates]]
        print(f"\nauto-ingesting {len(ids)} paper(s)...")
        summary = ingest_by_ids(
            args.db, ids, extract=True,
            groq_model=args.groq_model,
            min_relevance_to_keep=args.min_relevance_to_keep,
            verbose=True,
        )
        print(json.dumps({k: v for k, v in summary.items() if k != "errors"}, indent=2))
    else:
        print(f"\nto ingest these: re-run with --auto-ingest "
              "(or use ingest-ids with the printed arxiv_ids).")
    return 0


def cmd_list_code(args) -> int:
    """Inspect all surfaced code_url rows in one view — quick sanity check
    for false positives picked up by abstract / comment / pdf scanners."""
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    hits = [r for r in rows if r.get("code_url")]
    if not hits:
        print("no rows have code_url.")
        return 0
    by_source: dict[str, list[dict]] = {}
    for r in hits:
        by_source.setdefault(r.get("code_url_source") or "?", []).append(r)
    for src in sorted(by_source):
        print(f"\n--- source={src} ({len(by_source[src])}) ---")
        for r in sorted(by_source[src], key=lambda r: r["arxiv_id"]):
            print(f"  {r['arxiv_id']:<14s} {r['code_url']:<70s} "
                  f"{(r['title'] or '')[:60]}")
    print(f"\ntotal: {len(hits)} code_url(s) across {len(rows)} papers "
          f"({100 * len(hits) / len(rows):.0f}% coverage)")
    return 0


def cmd_set_code_url(args) -> int:
    """Manual override: set or clear a paper's code_url.

    --clear marks the row as "no code link" by writing NULL; further
    backfill / scan-pdfs runs will leave it alone because the row also
    has pdf_scanned_at stamped (clear marks it stamped so we don't loop)."""
    from .db import set_literature_code_url, mark_pdf_scanned
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    if not any(r["arxiv_id"] == args.arxiv_id for r in rows):
        print(f"no row for arxiv_id={args.arxiv_id!r}", file=sys.stderr)
        return 1
    if args.clear:
        set_literature_code_url(args.db, args.arxiv_id,
                                code_url=None, source="manual_clear")
        try:
            mark_pdf_scanned(args.db, args.arxiv_id)
        except KeyError:
            pass
        print(f"{args.arxiv_id}: code_url cleared (will not be re-scanned)")
        return 0
    if not args.url:
        print("either --url URL or --clear is required", file=sys.stderr)
        return 1
    set_literature_code_url(args.db, args.arxiv_id,
                            code_url=args.url, source="manual")
    print(f"{args.arxiv_id}: code_url = {args.url}")
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
    print("[4] PDF body (all pages):")
    if args.pdf:
        from .code_links import (
            extract_github_from_pdf, _download_pdf_bytes,
        )
        u4 = extract_github_from_pdf(args.arxiv_id)
        print(f"    regex hit  : {u4!r}")
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
                    for page in reader.pages
                )
                print(f"    extracted  : {len(joined)} chars across "
                      f"{len(reader.pages)} pages")
                # Highlight every line that mentions a code host or other
                # repo-sharing keyword. Zero hits = link genuinely not in
                # the paper.
                needles = ("github", "gitlab", "bitbucket", "zenodo",
                           "huggingface", "https://", "source code",
                           "available at", "code at")
                lc = joined.lower()
                hits = [ln for ln in joined.splitlines()
                        if any(n in ln.lower() for n in needles)]
                if hits:
                    print(f"    lines mentioning code-link keywords "
                          f"({len(hits)}):")
                    for h in hits[:20]:
                        print(f"      | {h.strip()[:200]}")
                else:
                    print("    no code-link keywords found at all")
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
    ap.add_argument("--db", default=None,
                     help="path to abm_knowhow.db; required by every command "
                          "except `glossary` (which is DB-free)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="query arxiv + extract with Groq + store")
    g = p_in.add_mutually_exclusive_group()
    g.add_argument("--query", default=None, help="raw arxiv search query")
    g.add_argument("--preset", default=None,
                   help=f"named preset query: {list(DEFAULT_QUERIES)}")
    p_in.add_argument("--max", type=int, default=50, help="max papers per call")
    p_in.add_argument("--no-extract", action="store_true",
                      help="ingest metadata only (free, no Groq calls)")
    p_in.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_in.add_argument("--min-relevance-to-keep", type=float, default=0.0,
                      help="papers extracted below this relevance keep metadata only")
    p_in.add_argument("--quiet", action="store_true")

    p_ii = sub.add_parser(
        "ingest-ids",
        help=("targeted ingest of explicit arxiv_ids (e.g. for foundational "
              "papers the broad query passes miss)"),
    )
    g_ii = p_ii.add_mutually_exclusive_group(required=True)
    g_ii.add_argument("--ids", help="comma-separated arxiv_ids "
                                     "(e.g. '1909.03185,1611.04839')")
    g_ii.add_argument("--ids-file", help=("one arxiv_id per line, # comments "
                                           "and blanks ignored"))
    p_ii.add_argument("--no-extract", action="store_true")
    p_ii.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_ii.add_argument("--min-relevance-to-keep", type=float, default=0.0)
    p_ii.add_argument("--quiet", action="store_true")

    p_ls = sub.add_parser("list", help="one-line summary per paper")
    p_ls.add_argument("--tag", default=None)
    p_ls.add_argument("--min-relevance", type=float, default=None)
    p_ls.add_argument("--limit", type=int, default=50)

    p_sh = sub.add_parser("show", help="full paper record")
    p_sh.add_argument("arxiv_id")

    p_se = sub.add_parser("search", help="substring search over title + abstract + mechanism")
    p_se.add_argument("query")
    p_se.add_argument("--limit", type=int, default=20)

    p_eu = sub.add_parser(
        "extract-untagged",
        help=("run LLM extraction on rows that have no tags yet — mostly "
              "OA-only canon ingested by canon_ingest without an "
              "extraction pass. Idempotent; safe to re-run."),
    )
    p_eu.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                       help=("LLM used for extraction. Accepts a Groq-hosted "
                             "model id or 'openai/<id>'."))
    p_eu.add_argument("--limit", type=int, default=0,
                       help="stop after N papers (0 = all untagged)")
    p_eu.add_argument("--dry-run", action="store_true",
                       help="list what would be extracted, without calling the LLM")
    p_eu.add_argument("--sleep", type=float, default=0.0,
                       help="seconds between calls (smooth TPM rate limits; "
                            "Groq free tier is 8k TPM — 3.0 is a safe pace)")
    p_eu.add_argument("--max-attempts", type=int, default=3,
                       help="skip rows whose extraction_attempts already "
                            "reached this cap (default 3). Prevents infinite "
                            "retries on papers the LLM has repeatedly failed "
                            "to extract from.")
    p_eu.add_argument("--retry-empty-past", action="store_true",
                       help="also retry rows that WERE extracted but came "
                            "back completely empty (no summary + no tags + "
                            "no relevance). Useful right after a prompt or "
                            "generate_japanese fix.")

    p_so = sub.add_parser(
        "stylized-fact-other",
        help=("list / re-classify papers whose stylized_facts_targeted "
              "landed in 'other' (audit the extractor's catch-all bucket)"),
    )
    p_so.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                       help="LLM used when --retag is set")
    p_so.add_argument("--limit", type=int, default=0,
                       help="stop after N papers (0 = all matching)")
    p_so.add_argument("--retag", action="store_true",
                       help="re-run extraction on each match (useful after "
                            "expanding the stylized-fact enum). Idempotent.")

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

    p_cv = sub.add_parser(
        "coverage",
        help=("render the (mechanism × stylized fact) coverage matrix as "
              "a PNG heatmap + markdown table"),
    )
    p_cv.add_argument("--out-dir", default="notebooks/coverage/")
    p_cv.add_argument("--top-rows", type=int, default=15,
                      help="number of top mechanism tags to include")

    p_at = sub.add_parser(
        "atlas",
        help=("render the literature 2D map (PNG + CSV) — TF-IDF over "
              "tags+concepts+title, projected via SVD, colored by tag"),
    )
    p_at.add_argument("--out-dir", default="notebooks/literature_map/")
    p_at.add_argument("--top-labels", type=int, default=12,
                      help="annotate the K most-cited papers")

    p_dl = sub.add_parser(
        "delete-rows",
        help=("delete literature_methods rows by arxiv_id (comma-sep). "
              "Dry-run by default; pass --yes to commit"),
    )
    p_dl.add_argument("arxiv_ids", help="comma-separated arxiv_ids")
    p_dl.add_argument("--yes", action="store_true",
                      help="actually delete (default: dry-run)")

    p_fa = sub.add_parser(
        "fix-arxiv-ids",
        help=("one-shot migration: re-query arxiv for rows whose arxiv_id "
              "is an old-style 7-digit number missing the category prefix "
              "(e.g. '0101326v1' → 'cond-mat/0101326v1')"),
    )
    p_fa.add_argument("--dry-run", action="store_true",
                      help="print planned updates without modifying the DB")
    p_fa.add_argument("--sleep", type=float, default=0.5,
                      help="seconds between OpenAlex title searches")

    p_sv = sub.add_parser(
        "strip-arxiv-versions",
        help=("one-shot migration: drop vN suffix from every literature_methods "
              "arxiv_id (companion to the ingest-side vN strip). "
              "Dry-run by default; --yes to commit."),
    )
    p_sv.add_argument("--dry-run", action="store_true",
                      help="print planned changes without touching the DB")
    p_sv.add_argument("--yes", action="store_true",
                      help="commit the migration (default: safe print-only)")

    p_dc2 = sub.add_parser(
        "diagnose-concept",
        help=("show raw OpenAlex /concepts and /works responses for a "
              "search query — useful when canon/genealogy returns 'no "
              "concept matches'"),
    )
    p_dc2.add_argument("name", help="concept display name to search for")

    p_gn = sub.add_parser(
        "genealogy",
        help=("interactive HTML force-graph of forward citations from a "
              "root paper (the 'genealogy tree' of a subfield)"),
    )
    p_gn_src = p_gn.add_mutually_exclusive_group(required=True)
    p_gn_src.add_argument("--root-arxiv-id",
                          help="paper to use as the tree's root")
    p_gn_src.add_argument("--root-concept",
                          help="auto-pick the top-cited paper under this "
                               "OpenAlex concept as root")
    p_gn.add_argument("--year-max", type=int, default=None,
                      help="for --root-concept: exclude root candidates "
                           "after this year")
    p_gn.add_argument("--depth", type=int, default=2,
                      help="forward-citation walk depth (1 or 2 recommended)")
    p_gn.add_argument("--per-node", type=int, default=20,
                      help="max children per node (top-cited kept)")
    p_gn.add_argument("--min-cited-by", type=int, default=0,
                      help="filter children with fewer than this many citations")
    p_gn.add_argument(
        "--keywords",
        help=("comma-separated topical terms; removes non-matching branches "
              "and merges duplicate titles"),
    )
    p_gn.add_argument(
        "--exclude-keywords",
        help="comma-separated terms to reject even when --keywords matches",
    )
    p_gn.add_argument("--sleep", type=float, default=0.5)
    p_gn.add_argument("--out", default="notebooks/genealogy/tree.html")

    p_cn = sub.add_parser(
        "canon",
        help=("surface the top-cited 'canon' papers under an OpenAlex "
              "concept (e.g. 'Minority game' / 'Leverage effect'). "
              "--auto-ingest pulls the arxiv-hosted ones into DB"),
    )
    p_cn.add_argument("concept",
                      help="concept display name (e.g. 'Minority game') "
                           "OR OpenAlex concept id (CXXXXXXX)")
    p_cn.add_argument("--n", type=int, default=30,
                      help="how many top-cited papers to surface")
    p_cn.add_argument("--year-max", type=int, default=None,
                      help="exclude papers published after this year")
    p_cn.add_argument("--auto-ingest", action="store_true")
    p_cn.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_cn.add_argument("--min-relevance-to-keep", type=float, default=0.0)

    p_gl = sub.add_parser(
        "glossary",
        help=("personal EN↔JA terminology dict. Subcommands: list / "
              "lookup <en> / search <query> / prompt [--domain X]"),
    )
    p_gl.add_argument("sub", choices=["list", "lookup", "search", "prompt"])
    p_gl.add_argument("term", nargs="?", default=None)
    p_gl.add_argument("--domain", default=None,
                      help="for `prompt`: scope to a domain "
                           "(financial-abm / ml / stats / general)")

    p_gp = sub.add_parser(
        "gap-propose",
        help=("run gap-mine, take the top-N gaps, LLM-draft a concrete "
              "proposal per gap, insert each into the proposals table "
              "with proposal_type='gap_mine'"),
    )
    p_gp.add_argument("--top", type=int, default=5,
                      help="number of gaps to draft proposals for")
    p_gp.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_gp.add_argument("--dry-run", action="store_true",
                      help="generate proposals but DO NOT insert into DB")

    p_gm = sub.add_parser(
        "gap-mine",
        help=("detect under-explored cells across 3 views (subfield × "
              "stylized-fact / family × fact / technique × subfield); "
              "print top-N gaps ranked by salience"),
    )
    p_gm.add_argument("--top", type=int, default=20)
    p_gm.add_argument("--json", action="store_true",
                      help="emit machine-readable JSON of the ranked gaps")

    p_ca = sub.add_parser(
        "canon-atlas",
        help=("sweep every subfield in subfields.SUBFIELDS, run canon "
              "detection per subfield, render a single HTML page with "
              "coverage heatmap + per-subfield detail. "
              "--auto-ingest-missing pulls every missing canon arxiv paper."),
    )
    p_ca.add_argument("--out", default="notebooks/canon_atlas/atlas.html")
    p_ca.add_argument("--n", type=int, default=8,
                      help="how many top-cited papers per subfield")
    p_ca.add_argument("--year-max", type=int, default=None,
                      help="exclude canon candidates after this year")
    p_ca.add_argument("--sleep", type=float, default=0.5,
                      help="seconds between OpenAlex calls (rate-limit pad)")
    p_ca.add_argument("--only", default=None,
                      help="comma-separated subfield keys to limit to "
                           "(default: all 25). Use canon-atlas without "
                           "--only to see available keys.")
    p_ca.add_argument("--auto-ingest-missing", action="store_true")
    p_ca.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_ca.add_argument("--min-relevance-to-keep", type=float, default=0.0)

    p_dash = sub.add_parser(
        "dashboard",
        help=("build a multi-page static dashboard for corpus coverage, "
              "PCA fingerprints, market heatmaps, and proposal analytics"),
    )
    p_dash.add_argument("--out-dir", default="dashboard")
    p_dash.add_argument("--canon-atlas", default="canon_atlas.html")

    p_eo = sub.add_parser(
        "enrich-via-oa",
        help=("backfill OpenAlex metadata (cited_by_count + concepts + "
              "OA paperId). No API key required; 10 req/s limit."),
    )
    p_eo.add_argument("--limit", type=int, default=0)
    p_eo.add_argument("--sleep", type=float, default=0.5,
                      help="seconds between API calls (OpenAlex caps at 10/sec)")
    p_eo.add_argument("--retry-missing", action="store_true",
                      help="ignore oa_fetched_at; re-fetch all rows without oa_paper_id")

    p_xo = sub.add_parser(
        "expand-via-oa",
        help=("OpenAlex citation graph 1-hop expansion. Like expand-via-s2 "
              "but uses OpenAlex (no API key required)."),
    )
    p_xo.add_argument("--from-arxiv-id", default=None)
    p_xo.add_argument("--top-seeds", type=int, default=10)
    p_xo.add_argument("--all-seeds-since", type=int, default=None, metavar="YEAR",
                      help=("walk references of EVERY DB paper published in "
                            "YEAR or later (overrides --top-seeds). Recent "
                            "papers with empty referenced_works auto-skip."))
    p_xo.add_argument("--refs-per-seed", type=int, default=50)
    p_xo.add_argument("--top-candidates", type=int, default=20)
    p_xo.add_argument("--limit", type=int, default=0)
    p_xo.add_argument("--sleep", type=float, default=0.5)
    p_xo.add_argument("--auto-ingest", action="store_true")
    p_xo.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help=("LLM used for the extraction / classification step. "
                            "Accepts a Groq-hosted model id (e.g. 'llama-3.1-70b') "
                            "or an openai/-prefixed id (e.g. 'openai/gpt-4o-mini') "
                            "which routes to the OpenAI API instead."))
    p_xo.add_argument("--min-relevance-to-keep", type=float, default=0.0)

    p_do = sub.add_parser(
        "diagnose-oa",
        help="inspect raw OpenAlex response for one arxiv_id",
    )
    p_do.add_argument("arxiv_id")

    p_ds = sub.add_parser(
        "diagnose-s2",
        help=("inspect the raw Semantic Scholar response for ONE arxiv_id "
              "— useful when enrich-via-s2 hit rate is suspiciously low"),
    )
    p_ds.add_argument("arxiv_id")

    p_es = sub.add_parser(
        "enrich-via-s2",
        help=("backfill Semantic Scholar metadata (tldr + influential "
              "citation count + paperId) for every literature row"),
    )
    p_es.add_argument("--limit", type=int, default=0,
                      help="stop after N papers (0 = no limit)")
    p_es.add_argument("--sleep", type=float, default=4.0,
                      help="seconds between API calls (S2 free tier ≈ 100/5min)")
    p_es.add_argument("--retry-missing", action="store_true",
                      help=("ignore s2_fetched_at; re-fetch every row that "
                            "doesn't actually have s2_paper_id set"))

    p_xs = sub.add_parser(
        "expand-via-s2",
        help=("walk each paper's references via S2 and report arxiv-hosted "
              "prior work not yet in the DB. --auto-ingest brings them in."),
    )
    p_xs.add_argument("--from-arxiv-id", default=None,
                      help="walk references of this single paper only")
    p_xs.add_argument("--top-seeds", type=int, default=10,
                      help="without --from-arxiv-id, walk top N "
                           "highest-relevance papers as seeds")
    p_xs.add_argument("--refs-per-seed", type=int, default=50,
                      help="max references to fetch per seed paper")
    p_xs.add_argument("--top-candidates", type=int, default=20,
                      help="how many candidates to print / ingest")
    p_xs.add_argument("--limit", type=int, default=0,
                      help="stop after N seed papers (0 = no limit)")
    p_xs.add_argument("--sleep", type=float, default=4.0)
    p_xs.add_argument("--auto-ingest", action="store_true",
                      help="run ingest-ids on the top candidates")
    p_xs.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL,
                      help="model for the LLM extraction step in --auto-ingest")
    p_xs.add_argument("--min-relevance-to-keep", type=float, default=0.0)

    p_lc = sub.add_parser(
        "list-code",
        help=("list all rows with a code_url, grouped by source — quick "
              "sanity check for false positives"),
    )

    p_sc = sub.add_parser(
        "set-code-url",
        help=("manual override: set or clear one row's code_url "
              "(survives subsequent backfill / scan runs)"),
    )
    p_sc.add_argument("arxiv_id")
    g_sc = p_sc.add_mutually_exclusive_group(required=True)
    g_sc.add_argument("--url", help="full repo URL to set")
    g_sc.add_argument("--clear", action="store_true",
                      help="clear the code_url and mark row 'no link'")

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
    p_sp.add_argument("--max-pages", type=int, default=0,
                      help=("how many leading pages to extract per PDF "
                            "(0 = all pages; useful default since many "
                            "papers put the link in acknowledgments / refs)"))
    p_sp.add_argument("--sleep", type=float, default=3.0,
                      help="seconds between papers (arxiv rate-limit padding)")
    p_sp.add_argument("--rescan", action="store_true",
                      help=("re-scan rows that already have code_url and/or "
                            "pdf_scanned_at — use after improving the "
                            "extractor or to refresh wrong links"))
    p_sp.add_argument("--filter-source", default=None,
                      help=("comma-sep code_url_source values to rescan, "
                            "e.g. 'pdf' to only revisit PDF-derived hits"))

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
    # `--db` is required for every command except DB-free utilities.
    _db_free = {"glossary"}
    if args.cmd not in _db_free and not args.db:
        ap.error(f"--db is required for `{args.cmd}`")
    handlers = {"ingest": cmd_ingest, "ingest-ids": cmd_ingest_ids,
                "extract-untagged": cmd_extract_untagged,
                "stylized-fact-other": cmd_stylized_fact_other,
                "list": cmd_list, "show": cmd_show,
                "search": cmd_search, "backfill-code": cmd_backfill_code,
                "diagnose-code": cmd_diagnose_code,
                "scan-pdfs-for-code": cmd_scan_pdfs_for_code,
                "fetch-code-snapshots": cmd_fetch_code_snapshots,
                "list-code": cmd_list_code,
                "set-code-url": cmd_set_code_url,
                "enrich-via-s2": cmd_enrich_via_s2,
                "expand-via-s2": cmd_expand_via_s2,
                "diagnose-s2": cmd_diagnose_s2,
                "enrich-via-oa": cmd_enrich_via_oa,
                "expand-via-oa": cmd_expand_via_oa,
                "diagnose-oa": cmd_diagnose_oa,
                "fix-arxiv-ids": cmd_fix_arxiv_ids,
                "strip-arxiv-versions": cmd_strip_arxiv_versions,
                "delete-rows": cmd_delete_rows,
                "atlas": cmd_atlas,
                "coverage": cmd_coverage,
                "canon": cmd_canon,
                "canon-atlas": cmd_canon_atlas,
                "gap-mine": cmd_gap_mine,
                "gap-propose": cmd_gap_propose,
                "glossary": cmd_glossary,
                "dashboard": cmd_dashboard,
                "genealogy": cmd_genealogy,
                "diagnose-concept": cmd_diagnose_concept}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
