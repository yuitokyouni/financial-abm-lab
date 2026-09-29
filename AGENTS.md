# Repository maintenance rules

- Read `docs/architecture/repository-layout.md` and the relevant experiment README before editing.
- Put experiment-owned code, configs, tests, notes and evidence under `experiments/<ID>/`.
- Put genuinely reusable code under `packages/`; shared packages must not import `experiments`.
- Keep the numerical model implementation single-sourced. A Python package may be experiment-local.
- Every experiment has `README.md` and `experiment.toml`. Do not fabricate missing experiments or results.
- Do not modify `imported/`, existing result files, source data or provenance manifests during layout work.
- Preserve `unwind-tape` as the compatibility link until the owner's external cron/launchd paths are migrated.
- Never delete local ignored data to resolve a path conflict. Explain and preserve it.
- Run `python tools/check_layout.py` and `uv run pytest -m "not slow"` after changes.
- YH012 requires its separately installed local LOBcore; follow its own README for tests.

- For paper-backed model rules, follow `docs/architecture/research-assets.md`; use registered canonical references when available and do not treat LLM summaries as source evidence.
