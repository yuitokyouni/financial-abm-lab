# Canon Atlas: Next Actions

## Current state

The canon-atlas pipeline now:

- treats natural-language queries as exact title/abstract searches instead of
  auto-promoting them to broad OpenAlex concepts;
- uses shorter, curated queries for all 25 subfields;
- applies per-subfield title terms to reject full-text false positives;
- distinguishes OpenAlex failures from valid empty result sets;
- refuses `--auto-ingest-missing` when any subfield lookup failed;
- short-circuits repeated requests after an HTTP 429 in the same process.

The accidental `source_kind='openalex'` batch of 20 rows was removed from
`../test/knowhow/abm_knowhow.db`. The two valid arXiv-ingested Minority Game
papers remain. A pre-cleanup backup is at:

`/tmp/abm_knowhow-before-canon-cleanup.db`

As of 2026-06-29 17:50 JST, the shared OpenAlex daily budget was exhausted.
The generated `canon_atlas.html` therefore correctly shows `ERROR` for all
subfields and must not be treated as a coverage snapshot.

## Priority: persist search results

`canon-atlas` currently queries OpenAlex for every subfield on every run.
Implement a SQLite cache so rendering and coverage analysis do not depend on
live API availability.

Suggested tables:

```sql
CREATE TABLE canon_search_snapshots (
    id INTEGER PRIMARY KEY,
    subfield_key TEXT NOT NULL,
    query TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,          -- ok | empty | rate_limited | error
    error_message TEXT,
    UNIQUE(subfield_key, query, fetched_at)
);

CREATE TABLE canon_search_results (
    snapshot_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    oa_paper_id TEXT NOT NULL,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    year INTEGER,
    cited_by_count INTEGER,
    doi TEXT,
    accepted INTEGER NOT NULL,     -- passed subfield relevance guard
    rejection_reason TEXT,
    PRIMARY KEY(snapshot_id, oa_paper_id)
);
```

Keep rejected candidates. They are necessary for auditing and improving
subfield rules without spending another API request.

## Required CLI behavior

1. `canon-atlas` uses the newest successful cached snapshot by default.
2. `canon-atlas --refresh` performs live OpenAlex queries and stores each
   successful or failed snapshot.
3. If refresh fails, render the newest successful cache and show a visible
   "stale as of TIMESTAMP" warning. Do not replace good cached data with an
   empty result.
4. `--max-cache-age HOURS` optionally refreshes only stale subfields.
5. `--offline` must make zero network calls and fail clearly when a subfield
   has no successful snapshot.
6. `--auto-ingest-missing` may only ingest candidates from successful,
   accepted snapshots.
7. After ingestion, rebuild coverage from the DB before writing the final
   HTML. The current flow writes HTML before ingestion, leaving stale coverage.

## Coverage improvements

- Show both canon coverage (`covered accepted canon / accepted canon`) and
  local corpus breadth (matching DB papers per subfield).
- Track coverage history so regressions and newly added subfields are visible.
- Inject a curated seed paper into a subfield when `seed_arxiv` is configured;
  do not rely on the search phrase to rediscover a founder paper with a
  different title.
- Deduplicate journal/preprint variants by DOI, normalized title, and OpenAlex
  merged-work relationships before computing the denominator.
- Add an explicit review queue for rejected and low-confidence candidates.
- Never interpret `0/0`, transport failure, or rate limiting as 100% coverage.

## Tests and acceptance

Add tests proving:

- a second default run makes zero OpenAlex calls;
- `--refresh` writes snapshots and results transactionally;
- a failed refresh preserves and renders stale successful data;
- rejected candidates cannot be auto-ingested;
- post-ingestion HTML reflects the updated DB;
- duplicate preprint/journal records count once;
- seed papers are included even when their titles do not contain the query;
- all-error runs return non-zero and never print "coverage is complete".

Acceptance command after the OpenAlex budget resets:

```bash
uv run python -m fingerprint_atlas.arxiv_cli \
  --db ../test/knowhow/abm_knowhow.db canon-atlas \
  --refresh --out canon_atlas.html

uv run python -m fingerprint_atlas.arxiv_cli \
  --db ../test/knowhow/abm_knowhow.db canon-atlas \
  --offline --out canon_atlas_offline.html
```

The second command must reproduce the same accepted canon and coverage with
zero network access.
