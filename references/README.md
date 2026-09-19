# Research references

This directory stores **identifiers and provenance, not copyrighted paper PDFs**.

The repository separates four concerns:

- Zotero: bibliographic metadata, tags, collections, notes.
- Google Drive: the canonical PDF files used as implementation references.
- Google Cloud Storage: large research datasets and large run artifacts.
- Git: stable identifiers, hashes, experiment links, and reproducibility metadata.

`catalog.json` is the machine-readable bridge. A reference may start with only an
arXiv ID/DOI and later acquire a Zotero item key and Drive file ID. Do not invent
missing identifiers.

Remote agents should use `python tools/research_assets.py refs ...` instead of
depending on a workstation-specific Zotero or Google Drive filesystem path.
Downloaded files belong in `.cache/research-assets/` and are never committed.

## Credentials

No credentials belong in Git. The CLI reads:

- `ZOTERO_USER_ID`
- `ZOTERO_API_KEY`
- `GOOGLE_DRIVE_ACCESS_TOKEN` (short-lived OAuth bearer token)
- Google Cloud authentication through the installed `gcloud` CLI / ADC.

Zotero and Drive support is deliberately read-only in this first integration.
Registration/migration is kept separate so an agent cannot silently rewrite the
research library.
