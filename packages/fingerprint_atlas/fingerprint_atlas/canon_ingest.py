"""canon_ingest — ingest journal-only canon papers from OpenAlex metadata.

The arxiv ingestion pipeline (`arxiv_ingest.ingest_arxiv_ids`) only works
for papers with a real arxiv_id. But financial-ABM canon — Schwert 1989,
Engle 1982, Brock-Hommes 1998, Fama-French 1993 etc — is mostly
pre-arxiv-era journal papers.

This module ingests them via OpenAlex metadata alone (title, authors,
year, abstract reconstructed from inverted_index, concepts, cite count).
No PDF is fetched. Rows are stored with:
  - arxiv_id     = 'oa:Wxxxxxxx'  (synthetic, satisfies UNIQUE constraint)
  - source_kind  = 'openalex'
  - oa_paper_id  = full OA URI

Downstream tools that build arxiv URLs or scan PDFs must check
source_kind != 'arxiv' before treating arxiv_id as a real arxiv handle.

LLM mechanism-extraction can still run on these rows — the abstract
gives enough signal — but PDF-based extraction won't apply.
"""
from __future__ import annotations

import datetime as _dt
import re
import sqlite3
from typing import Any

from .db import (ensure_literature_schema, upsert_literature_metadata,
                  set_oa_metadata)
from .openalex import fetch_work_full, sleep_for_rate_limit


def _synthetic_arxiv_id(oa_paper_id: str) -> str | None:
    """Turn 'https://openalex.org/W2091653681' into 'oa:W2091653681'."""
    m = re.search(r"(W\d+)", oa_paper_id or "")
    if not m:
        return None
    return f"oa:{m.group(1)}"


def is_openalex_synthetic_id(arxiv_id: str | None) -> bool:
    """True for the 'oa:Wxxxx' synthetic ids minted here."""
    return bool(arxiv_id) and arxiv_id.startswith("oa:W")


def _already_in_db(db_path: str, synthetic_id: str) -> bool:
    with sqlite3.connect(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM literature_methods WHERE arxiv_id = ?",
            (synthetic_id,),
        ).fetchone()
    return row is not None


def ingest_canon_via_oa(db_path: str, oa_work_ids: list[str], *,
                         sleep: float = 0.3,
                         verbose: bool = False) -> dict[str, Any]:
    """For each OpenAlex work id, fetch full metadata + insert into
    literature_methods as a source_kind='openalex' row.

    Idempotent (re-running on the same ids is a no-op). Returns a summary
    dict {requested, added, skipped, errors}.
    """
    ensure_literature_schema(db_path)
    summary: dict[str, Any] = {
        "requested": len(oa_work_ids), "added": 0, "skipped": 0,
        "errors": [],
    }
    now = _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S") + "Z"

    for i, oa_id in enumerate(oa_work_ids):
        synthetic = _synthetic_arxiv_id(oa_id)
        if not synthetic:
            summary["errors"].append({"oa_id": oa_id, "why": "bad-id"})
            continue
        if _already_in_db(db_path, synthetic):
            summary["skipped"] += 1
            if verbose:
                print(f"  [{i+1:>3d}] skip (already in DB): {synthetic}")
            continue

        work = fetch_work_full(oa_id)
        if not work:
            summary["errors"].append({"oa_id": oa_id, "why": "fetch-failed"})
            if verbose:
                print(f"  [{i+1:>3d}] FETCH FAIL: {oa_id}")
            if sleep:
                sleep_for_rate_limit(sleep)
            continue

        # Skip works missing fields the DB schema requires NOT NULL.
        title = work.get("title")
        year = work.get("year")
        if not title or not year:
            summary["errors"].append({
                "oa_id": oa_id,
                "why": f"missing required field (title={bool(title)},"
                       f" year={bool(year)})",
            })
            if verbose:
                print(f"  [{i+1:>3d}] SKIP (missing metadata): {oa_id}")
            if sleep:
                sleep_for_rate_limit(sleep)
            continue

        published_date = (work.get("published_date")
                           or f"{year}-01-01")  # synthesize if absent
        abstract = work.get("abstract") or ""
        if not abstract:
            # OpenAlex has ~10% of works with no abstract_inverted_index;
            # synthesize a placeholder so the NOT NULL constraint holds and
            # downstream LLM extraction can be retried later if abstract
            # surfaces.
            abstract = f"[no abstract available from OpenAlex for {synthetic}]"
        upsert_literature_metadata(
            db_path,
            arxiv_id=synthetic,
            title=title,
            authors=work.get("authors") or "",
            year=int(year),
            published_date=published_date,
            primary_category=None,
            abstract=abstract,
            source_kind="openalex",
        )
        # Also stash OA metadata into the dedicated columns so
        # downstream tools (literature_map, coverage) see citation count
        # + concepts identically to arxiv rows.
        set_oa_metadata(
            db_path,
            arxiv_id=synthetic,
            oa_paper_id=work.get("oa_paper_id"),
            oa_cited_by_count=work.get("cited_by_count"),
            oa_concepts=", ".join(work.get("concepts") or []),
        )
        summary["added"] += 1
        if verbose:
            cit = work.get("cited_by_count") or 0
            print(f"  [{i+1:>3d}] +DB ({cit:>5d} cit, {year}): "
                  f"{title[:60]}")

        if sleep:
            sleep_for_rate_limit(sleep)

    return summary
