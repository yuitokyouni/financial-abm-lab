# Research references: getting started

Zotero holds bibliographic metadata; Drive holds reference PDFs and page-numbered
text; GCS holds large datasets. Git holds identifiers, hashes and source-use notes.
The existing Fingerprint Atlas discovery/LLM pipeline and snapshot are unchanged.
No MCP server is required for coding agents using this CLI.

## What works now

```sh
python tools/research_assets.py refs list
python tools/research_assets.py refs show katahira2019
python tools/research_assets.py literature-search 'Speculation Game'
python tools/research_assets.py doctor
```

`doctor` without `--live` only checks configuration, not API connectivity. Exit 2
means configuration or live checks are incomplete; it is not a silent success.
The Atlas search reads `data/literature_methods.json` without modifying it.
Its results remain discovery summaries, not verified PDF evidence.

## One-time authentication (on a trusted machine)

Do not paste API keys or tokens into chat, Git, issues, PRs, or screenshots.
A ChatGPT Drive connection does NOT provide credentials to an unrelated CLI.

Zotero: sign into the existing account, visit
https://www.zotero.org/settings/keys , create a dedicated read-only key for the
personal library, and note the numeric user ID. Supply `ZOTERO_USER_ID` and
`ZOTERO_API_KEY` through the execution environment's secret store. `zotero-search`
never changes the library. `--limit` is 1..100 and `--start` pages through results.
Do not create a new Zotero account or change existing desktop sync settings.

Google: reuse suitable existing ADC credentials where available. Otherwise enable
the Drive API in the existing Google Cloud project and create/download an OAuth
client of type Desktop app. Google requires a custom OAuth client for Drive scopes
in ADC. Authenticate in an isolated gcloud configuration directory so the user's
existing default ADC is not overwritten:

```sh
# Set this in the same shell used to run the CLI; use an absolute private path.
export CLOUDSDK_CONFIG="$HOME/.config/fabm-gcloud"
gcloud auth application-default login \
  --client-id-file=/absolute/private/path/client_secret.json \
  --scopes=https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/devstorage.read_only
```

The CLI obtains short-lived tokens using `gcloud auth application-default
print-access-token`. `gcloud auth login` alone is a different credential store.
Alternatively inject short-lived `GOOGLE_DRIVE_ACCESS_TOKEN` and
`GOOGLE_GCS_ACCESS_TOKEN`. These expire and are a smoke-test option, not a permanent
automation strategy. Scopes limit operations, but user credentials can still read
other accessible files. For unattended agents, scope the identity/IAM/sharing to
research assets rather than giving access to the entire personal account.
Remote runners need their OWN approved authentication/secret provisioning; copying
this repository does not copy credentials. Do not make files public to fix a 403.

## Live checks and use

```sh
python tools/research_assets.py doctor --live
python tools/research_assets.py zotero-search 'Speculation Game'
python tools/research_assets.py refs fetch katahira2019
python tools/research_assets.py refs fetch katahira2019 --text
```

Without `--gcs-uri`, the live doctor explicitly leaves GCS untested and exits 2.
For GCS, select an existing permitted object and run a metadata-only probe:

```sh
python tools/research_assets.py doctor --live --gcs-uri gs://YOUR_BUCKET/exact/object
python tools/research_assets.py gcs-fetch gs://YOUR_BUCKET/exact/object \
  --generation KNOWN_GENERATION --sha256 KNOWN_SHA256 \
  --max-bytes 536870912 --output .cache/research-assets/data/object.parquet
```

Replace placeholders with verified values. Record exact URI, generation, hash,
license/access restrictions and byte size under the owning experiment. The CLI
creates no bucket, enables no billing, and changes no IAM. A budget notification
is not a storage-spend cap. Do not upload licensed market data before confirming
that its permitted use includes the intended cloud/AI environment.

## Local storage and safety

Downloads are opt-in, one asset at a time. Verified cached files are reused before
requesting a token. A missing hash blocks download. Downloads stage to a temporary
file; incorrect hashes, wrong PDF content, interrupted streams, or size/time
limits cannot replace an existing file. An existing mismatching output is retained
and produces an error. Pick a new path rather than automatically deleting it.

Default transfer limit: 128 MiB per object; at most two HTTP-status retries;
30-second network operation timeout; 300-second checked streaming limit. Socket
operations can overrun that wall-clock check by up to their timeout. Stream failures
are not automatically retried. Redirects are refused to avoid leaking credentials.
The limit is per transfer, NOT a global cache/disk quota or GCS billing cap.

Keep fetched PDFs/text/data inside `.cache/research-assets/` (already ignored).
Drive desktop streaming settings are separate: use streaming, not mirroring, and
do not mark the whole papers folder for offline access. Local scans of every PDF
still cause downloads. Do not relocate Zotero's database to Drive, delete synced
files to clear cache, or remove original attachments while migration is unverified.
Mac File Provider caches remain OS-managed; this CLI does not alter them.

## Migration status

`katahira2019`: project-supplied arXiv 1902.02040v1, uploaded to private Drive and
downloaded back with identical SHA-256. Page-numbered text is mechanical extraction,
not an authoritative transcription; inspect PDF pages for equations/figures.
The record is for future YH005 source checks, not a claim about historical-run
inputs. Zotero item key is still null: no account access or title-only auto-match
has been assumed. Existing Zotero PDFs/notes, old repository PDFs, existing Atlas
summaries, and historical experiment outputs remain untouched. Full library
migration, Zotero writeback, unattended refresh and GCS provisioning are not done.

Sources: Zotero Web API v3 basics; Google Drive download guide; gcloud ADC login
reference; GCS objects.get reference. See `docs/architecture/research-assets.md`.
