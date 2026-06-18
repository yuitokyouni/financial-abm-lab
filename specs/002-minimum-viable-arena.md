# Spec 002 — Minimum Viable Arena (Intervention Atlas)

- Status: draft v1 (2026-06-18)
- Author: Yuito
- Depends on: `specs/001-monorepo-consolidation.md` (Stage B canonicalization), `imported/PROV-ABM-atlas/docs/program_claims_v1.md` (P1), `imported/PROV-ABM-atlas/docs/model_contract_v0.md`
- Decisions: center = reference atlas / submission gate = CI, semantic labeling = frozen registry / scoring = profile, not scalar rank / ignition gated on P1 GO + diagnostic case

---

## 1. Purpose

The Minimum Viable Arena (MVA) is not a leaderboard and does not rank model validity.

The MVA defines the smallest public-facing reference artifact needed for Intervention Atlas to become useful before external submissions arrive. Its purpose is to place canonical ABM implementations in a common coordinate system: model contract compliance, stylized-fact profile, intervention response, claim admissibility, and audit profile.

The MVA is successful if it is independently useful as a comparison reference for ABM papers, even with zero external submissions.

## 2. Non-goals

- The MVA does not provide a validity leaderboard.
- The MVA does not score whether a model is realistic.
- The MVA does not accept external submissions before ignition.
- The MVA does not build a full leaderboard UI, challenge platform, or review workflow before the first diagnostic result exists.
- The MVA does not couple Atlas publication to full PROV-ABM certification beyond the minimum provenance required by `model_contract_v1`.

## 3. Core claim

Arena formation should begin from a contract, not from a leaderboard.

The contract defines what a model must expose in order to be placed on the same map as other models. The first reference atlas is produced by dogfooding this contract during Stage B monorepo canonicalization and the P1 paper-grade run.

The initial arena is therefore a byproduct of canonicalization and paper-grade experimentation, not a separate infrastructure project.

## 4. Dependencies

The MVA depends on Stage B monorepo consolidation.

Stage B consolidates multiple historical implementations into `packages/abm_models`. A model entering `packages/abm_models` should also become eligible for an Atlas row if it satisfies `model_contract_v1`. This makes three tasks identical:

1. canonical implementation,
2. model contract compliance,
3. first Atlas row generation.

The first Atlas rows should come from existing repository material, including CB, LM, ALW, ZI, SG, CI, FW, Genoa-style ZI+, and order-book variants where available.

**Historical implementations are only source material. They are not Atlas rows until they pass the contract and produce comparable outputs.** Source material (history) and a canonical row (a contract-passing, comparable unit) are not the same thing; conflating them overestimates density.

## 5. model_contract_v1

A model must expose the following minimal surface:

```python
reset(seed)
step(action=None)
observe()
intervene(do)
emit_prov()
```

The contract must be sufficient to generate:

1. deterministic reruns under fixed seeds,
2. a provenance bundle,
3. a stylized-fact profile,
4. an intervention response vector,
5. a claim admissibility report,
6. an audit profile.

The contract should be small enough that a single model file or thin adapter can satisfy it.

## 6. CI gates and semantic labeling

A model row is generated only if CI verifies:

1. schema compliance,
2. deterministic execution under fixed seed,
3. successful `prov.json` emission,
4. successful SF battery execution,
5. successful intervention surface detection,
6. successful profile artifact generation,
7. successful one-command rerun.

CI does not decide whether a model is economically meaningful. CI does not decide whether the model implementation is the canonical interpretation of a paper.

**Operational dependence is not eliminated; it is confined to the semantic layer.** Questions such as "is this implementation really LM?" or "which mechanism label should this intervention response be placed under?" resist full automation. The submission gate is CI; semantic labeling (mechanism identity, label placement) is managed by a frozen registry, not by the gate.

## 7. Reference Atlas artifact

The launch artifact is a static reference atlas, not a submission platform.

Rows are canonical models. Columns are:

1. model family,
2. mechanism label,
3. contract status,
4. SF profile,
5. intervention response signature,
6. claim admissibility profile,
7. audit profile,
8. replication stability,
9. failure transparency note.

The first reference atlas should contain N=8–12 canonical rows.

**N is not the main criterion. Diversity is required.** The initial atlas should include at least:

1. one null or negative-control model,
2. one stylized-facts-oriented model,
3. one learning or feedback model,
4. one order-book or microstructure model,
5. one model with known failure or non-separation behavior,
6. one model used in the P1 intervention experiment.

A bare row count is not a reference atlas; the diversity constraint is what makes the coordinate system informative.

## 8. Scoring profile

The MVA uses profiles, not scalar validity ranks. The profile axes are:

1. claim admissibility,
2. audit completeness,
3. intervention coverage,
4. mechanism separability profile,
5. replication stability,
6. failure transparency.

`may/must gap` is included as a **component of audit completeness**. It is not the sole leaderboard objective.

The profile is intended to create improvement incentives without pretending to rank model validity.

## 9. Failure house

The MVA should make negative and failed results citable when they are structured.

A failure entry is admissible only if it satisfies:

1. contract compliance,
2. declared target claim,
3. reproducible run bundle,
4. failure taxonomy assignment,
5. clear distinction between implementation failure, non-identification, non-separation, and unsupported validity claim.

**The failure house is not a dumping ground for incomplete models. It is a registry of reproducible negative evidence.** A failure lacking these conditions is merely an unfinished model, not negative evidence.

## 10. Launch acceptance criteria

The MVA is launch-ready when all of the following hold:

1. `model_contract_v1` is frozen.
2. At least 8 canonical model rows pass CI.
3. Each row produces the full artifact bundle: provenance, SF profile, intervention response vector, claim admissibility report, audit profile, and failure note where applicable.
4. At least one intervention dimension separates models that are not separated by the SF profile.
5. Every row can be reproduced with a documented one-command rerun.
6. The static reference atlas is usable as a comparison reference without external submissions.

The MVA is not launch-ready merely because a leaderboard UI exists.

## 11. Ignition gate

External submissions, public leaderboard infrastructure, and challenge-style workflows must not be built before ignition.

Ignition requires:

1. P1 reaches GO or a clearly publishable PARTIAL.
2. At least one **diagnostic case** exists: a surprising separation, surprising equivalence, or documented failure of a known model under the contract.
3. The reference atlas already contains enough canonical rows to be cited independently.

> Naming note: internally this diagnostic case is the "scalp" (dragging a strong existing model onto the board). Externally it must be presented as a *diagnostic case* / *surprising equivalence-or-separation result*, never as "taking down" a model — an adversarial posture makes this read as an attack benchmark rather than an arena.

Only after ignition should the project add:

1. external submission templates,
2. public issue-based review,
3. contributor documentation,
4. leaderboard or profile-browser UI,
5. versioned public releases.

## 12. Anti-patterns

- Do not build the leaderboard before the contract.
- Do not optimize for scalar rank.
- Do not market the atlas as a validity benchmark.
- Do not treat historical code as canonical until it passes the contract.
- Do not let failure entries become unreproducible anecdotes.
- Do not couple Atlas membership to full PROV-ABM certification beyond the minimum contract surface.
- Do not build submission infrastructure before the first diagnostic result exists.

## 13. Immediate tasks

1. Promote `docs/model_contract_v0.md` to `model_contract_v1`.
2. Define the six scoring profile axes as artifact schemas.
3. Modify Stage B canonicalization so that every model entering `packages/abm_models` can emit an Atlas row.
4. Implement the intervention schemes required for the P1 run.
5. Generate the first internal reference atlas from canonical models.
6. Freeze the ignition rule: no external submission infrastructure before P1 GO or publishable PARTIAL plus one diagnostic case.
