# Research asset architecture

The existing Fingerprint Atlas pipeline already discovers arXiv papers, enriches
metadata, asks an LLM for structured mechanism/stylized-fact annotations, and
stores a literature snapshot. That pipeline is **discovery/analysis**, not the
canonical store for papers used to implement an experiment.

For implementation provenance, use:

```text
Zotero (metadata/notes) ----+
                            +--> references/catalog.json --> coding agent
Drive (canonical PDF) ------+                              --> experiment
GCS (large datasets) --------------------------------------> experiment
```

The two paths stay separate:

1. Discovery: Fingerprint Atlas / arXiv may find and annotate candidate papers.
2. Adoption: once a paper is actually used as an implementation source, register
   a stable reference ID plus Zotero key, Drive file ID, DOI/arXiv ID and PDF
   SHA-256 in `references/catalog.json`.
3. Execution: remote agents fetch only adopted PDFs/data into the ignored
   `.cache/research-assets/` directory and verify hashes before use.

This avoids silently replacing an implementation source when an arXiv/publication
version changes.

## Minimal catalog record

```json
{
  "id": "katahira2019",
  "title": "Development of an agent-based speculation game ...",
  "doi": null,
  "arxiv_id": "1902.02040",
  "zotero_item_key": null,
  "drive_file_id": null,
  "sha256": null,
  "used_by": ["YH005"],
  "notes": "Identifiers are filled only after verification."
}
```

Fields may be null while migration is incomplete. Never guess Zotero or Drive
identifiers.

## Agent rule

Before changing a model rule whose behavior comes from a paper, inspect the
experiment README/spec, resolve its registered reference, fetch the canonical
PDF when available, and cite the relevant section/equation in the change notes.
If the PDF is unavailable, say so rather than treating an LLM summary as the
source.

## Authentication

Credentials are runtime configuration and must never be committed. For remote
agents use narrowly scoped, read-only credentials where possible. GCS access is
delegated to Google Cloud's normal authenticated CLI/ADC rather than embedding a
service-account key in this repository.
