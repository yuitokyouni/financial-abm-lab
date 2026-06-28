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


def cmd_fix_arxiv_ids(args) -> int:
    """One-shot migration: scan DB for arxiv_ids that look like an old-style
    paper with the category prefix stripped (e.g. '0101326v1' that should
    be 'cond-mat/0101326v1'). Re-query arxiv to get the canonical entry_id
    and UPDATE the row in place.

    Pre-2007 arxiv IDs are 7 digits, e.g. 0103089v1. New-style IDs are
    YYMM.NNNNN (4 + 4-5 digits). Anything matching the old-shape that
    lacks a '/' is suspect."""
    from .arxiv_ingest import _extract_arxiv_id_from_entry
    import sqlite3
    ensure_literature_schema(args.db)
    rows = load_literature(args.db)
    # Look-7-digits-no-slash: old-style id with the prefix dropped.
    suspect_re = re.compile(r"^\d{7}(v\d+)?$")
    suspects = [r for r in rows if suspect_re.match(r["arxiv_id"])]
    if not suspects:
        print("no rows with old-style arxiv_id missing a category prefix.")
        return 0
    print(f"found {len(suspects)} suspect row(s); re-querying arxiv to "
          "recover the canonical id...")
    try:
        import arxiv
    except ImportError:
        print("arxiv SDK not available", file=sys.stderr)
        return 1
    fixes: list[tuple[str, str]] = []
    for r in suspects:
        # arxiv accepts the truncated form as id_list and returns the
        # full canonical entry_id (incl. category prefix) in the result.
        base = re.sub(r"v\d+$", "", r["arxiv_id"])
        try:
            search = arxiv.Search(id_list=[base])
            client = arxiv.Client(page_size=1, delay_seconds=3.0)
            results = list(client.results(search))
        except Exception as exc:
            print(f"  ! {r['arxiv_id']}: arxiv lookup failed ({exc})")
            continue
        if not results:
            print(f"  - {r['arxiv_id']}: not found on arxiv (skipping)")
            continue
        canonical = _extract_arxiv_id_from_entry(results[0].entry_id)
        if canonical == r["arxiv_id"]:
            print(f"  = {r['arxiv_id']}: already canonical, no fix needed")
            continue
        fixes.append((r["arxiv_id"], canonical))
        print(f"  + {r['arxiv_id']:<16s} → {canonical}")
    if args.dry_run:
        print(f"\n(dry-run) would update {len(fixes)} row(s).")
        return 0
    if not fixes:
        print("\nnothing to update.")
        return 0
    with sqlite3.connect(args.db) as con:
        for old, new in fixes:
            con.execute(
                "UPDATE literature_methods SET arxiv_id = ? WHERE arxiv_id = ?",
                (new, old),
            )
        con.commit()
    print(f"\nupdated {len(fixes)} row(s).")
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
    else:
        seed_papers = sorted(
            (r for r in rows if r.get("relevance_score") is not None),
            key=lambda r: -(r["relevance_score"] or 0.0),
        )[:args.top_seeds]
    already_in_db = {re.sub(r"v\d+$", "", r["arxiv_id"]) for r in rows}
    candidates: dict[str, dict] = {}
    total_refs_walked = 0
    n_empty_seeds = 0
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
    p_ii.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
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

    p_fa = sub.add_parser(
        "fix-arxiv-ids",
        help=("one-shot migration: re-query arxiv for rows whose arxiv_id "
              "is an old-style 7-digit number missing the category prefix "
              "(e.g. '0101326v1' → 'cond-mat/0101326v1')"),
    )
    p_fa.add_argument("--dry-run", action="store_true",
                      help="print planned updates without modifying the DB")

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
    p_xo.add_argument("--refs-per-seed", type=int, default=50)
    p_xo.add_argument("--top-candidates", type=int, default=20)
    p_xo.add_argument("--limit", type=int, default=0)
    p_xo.add_argument("--sleep", type=float, default=0.5)
    p_xo.add_argument("--auto-ingest", action="store_true")
    p_xo.add_argument("--groq-model", default=DEFAULT_GROQ_MODEL)
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
    handlers = {"ingest": cmd_ingest, "ingest-ids": cmd_ingest_ids,
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
                "fix-arxiv-ids": cmd_fix_arxiv_ids}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
