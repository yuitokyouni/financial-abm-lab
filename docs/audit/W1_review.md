# Week 1 review — 2026-08-23

Covers Week 1 (8/16–8/22 per the calendar §4) plus the 8/23 slip day.
Authority split unchanged: claims are `W1D1_claims_freeze.md`, dates and gates
are `sieve_12_week_calendar_2026-08-16.md` §4, work items are `BACKLOG.md`,
and the evidence contract is `sieve/docs/contract/`. Nothing is duplicated
here; this file is the acceptance record.

**"Repo-held" is used in this file only for content merged to `main`.** Both
session branches were integrated to `main` on 2026-08-23 before the review
began (§1), so the term is used only where that is true.

---

## 1. Deviations

| # | deviation | recorded |
|---|---|---|
| D1 | **spec freeze 8/22→8/23 (1 day slip; the 8/22 session was not run). The floor the 8/24 work consumes directly (3 schemas + exact fixture) was already satisfied by the W1D6 output, so there is no downstream effect — conditional on the `main` integration completing today.** | integration completed 2026-08-23, §1 below |
| D2 | The 8/20 output sat on a branch for two days and was consequently invisible to the 8/21 session, which recorded the calendar and claims freeze as "not present in either repository" and inferred content it could have read. Corrected by the rule added to `BACKLOG.md`: a session branch is integrated to `main` the same day, and content before integration is not called repo-held. | §1, and the correction in §2 |
| D3 | The core event-log field set was **inferred** on 8/21 and was wrong in 2 of 8 slots (`event_id`, `actor_id` in place of order/trade ID and cause ID). Corrected on 8/23 against the calendar original and blocked by a test. | `sieve/docs/contract/evidence_contract_v0.1.md` §7 |

## 2. Branch inventory and integration (8/23, before anything else)

| repo | finding |
|---|---|
| `financial-abm-lab` | `9c9fc07` and `78419d5` are both on `origin/claude/w1d1-claims-freeze-revision-wubnix`, together with `c51cf59` and `4fdafd7`. **Not lost.** Carried `W1D1_claims_freeze.md`, `sieve_12_week_calendar_2026-08-16.md` (header 3 lines + change note), and the BACKLOG commit-rule and delegation-record lines. Merged to `main` (`c1f718a`), then the W1D6 branch merged (`dd32446`). `BACKLOG.md` auto-merged, both sections retained; no conflict outside it. |
| `sieve` | the W1D6 output (3 schemas, 2 fixtures, contract docs, tests) was on `origin/claude/schema-v2-fixture-7c82kx`. Merged to `main` (`9fbb47c`). **No re-submission from the session log was needed.** |
| 8/18 quarantine table (`F8-R1`–`R3`) | **absent.** `F8-R` returns zero hits across both repositories, every branch. |
| 8/19 comparison table (`sieve/docs/contract/schema.md`) | **absent** from every branch of both repositories. |

Both `main` branches pushed. No force-push, no history rewrite.

## 3. Week 1 deliverables — status

The calendar's Week 1 line: *"Contract draft, YH007 quarantine table, incident
report skeleton."*

| # | deliverable | status | evidence |
|---|---|---|---|
| ① | **Evidence Contract draft** | **complete, repo-held, awaiting "凍結可"** | `sieve/docs/contract/` (7 documents) + 6 hand-authored schemas + `fixtures/canary/` + 3 worked examples. Freeze checklist 10/10 with six knowingly-open items listed. Freeze declaration block present as DRAFT. |
| ② | **YH007 quarantine table** | **NOT FOUND — recorded as lost, not reconstructed** | `F8-R`: 0 hits, both repos, all branches. The verification-scope note it was to carry is preserved verbatim below and is applied nowhere. |
| ③ | **incident report skeleton** | **NOT FOUND** | no skeleton document in either repository. The raw material is present and unchanged in `BACKLOG.md` ("incident report 材料"), but the skeleton itself was never committed. |

**Preserved verbatim, for whenever ② is recovered or rewritten** — the note to
be attached to the `verified` rows of F8-R1–R3:

> 対応差計算に対して成立、run 再生成は /tmp 未 digest により対象外

**追補③ was not applied.** Its four items are conditioned on the incident
report skeleton being recovered, and it was not. Nothing from it was
half-applied. The four items are listed as open in §6 so they are not lost.

## 4. Acceptance — with output attached

Per the rule that "it ran, so it is done" is not accepted. Commands run at
`sieve@f0fdc2a`. The calendar's 8/23 task (review the agent's PRs and test
results, add no features) is discharged here rather than counted separately.

**Canary fixtures** — `python3 fixtures/canary/run_canary.py`

```
exact-lob-min        exact     MATCH               both digests reproduce exactly
semantic-lob-min     semantic  MATCH               30 assertions held
```

**Contract tests** — `pytest tests/unit/test_contract_{canary,hash_domain,examples}.py tests/unit/test_canonicalization_parity.py -q`

```
........................................................s   [100%]
56 passed, 1 skipped in 0.87s
```

The one skip is the sieve-vs-canary canonicalization parity check, which needs
`sieve` importable (numpy). Every CI job installs the package, so it runs
there; the byte rules it compares are pinned unconditionally by a second test
in the same file.

**Lint** — `ruff check src tests tools fixtures`

```
All checks passed!
```

**Exact fixture digests** (what 8/24's hash chain consumes)

```
event_log      9518f58250af92fe8584e564759fe49223fc6da946491d4a6dbc831c717e206f
stats_vector   461bbbc85b7200c602c4dd39d020d740a3e4da0087ff658019c08f82a79c8ead
```

**§2.1 resolution** — `docs/contract/conformance_map.v1.json`

```
26 items; FAIL: 26 ; new fields: 9
```

**Defect found by the work, not by a test written for it**: core-ising
`order_id` (calendar §2.1 slot 7) immediately exposed a real id-uniqueness bug
in the reference engine — a fully-filled order reused the next order's id.
Fixed, and now covered.

## 5. 8/24 prerequisites

Calendar 8/24: *"integrate the effective config → event log → bundle hash chain
and the canary CI."*

| prerequisite | | evidence / note |
|---|---|---|
| 3 schemas | **○** | `RunManifest.v2` 2.0.0, `EventLog` 1.1.0, `CanaryResult` 1.0.0 — plus 3 Cont harness schemas |
| canonical digest defined | **○** | `canonicalization.md`, 4 canonical forms; contract digest vs byte digest separated, and the chain uses the canonical side |
| fixture format | **○** | 3 parts + tolerance-basis vocabulary; 2 fixtures instantiate it |
| CanaryResult | **○** | emitted, self-validating, 2 worked examples |
| canary CI hook | **○** | `run_canary.py` exit code **is** the verdict (0/1/2/3); stdlib only, sub-second, no parsing needed |
| L1 route | **○** | G1 resolved: inline `l1`, profile-required |
| **Engine 1 exact fixture** | **× by design** | `pending_generation`. Minted 8/24 in a fixed container against the **full** runtime fingerprint domain. The toy fixture's narrowed domain is a harness self-test and is not a precedent — stated in both the fixture and the registry. |
| effective_config → event log → bundle chaining | **× not started** | out of Week 1 scope; it is the 8/24 task itself. The two ends exist (`effective_config_digest`, `event_log` contract digest) and `RunManifest.outputs[]` records `canonical_form` per digest, so nothing has to be redesigned to chain them. |

**G0 risk**: none of the above is a blocker for starting 8/24. The single
schedule risk is that 8/24 must both mint Engine 1's fixture *and* build the
chain, and only the second was originally on that day.

## 6. Open items

**Lost or unrecovered**

1. 8/18 quarantine table (`F8-R1`–`R3`) — 0 hits. Yuito's call whether to
   rewrite or close.
2. 8/19 comparison table, 20 items — absent; the item-by-item check against the
   freeze could not be performed.
3. incident report skeleton — absent; 追補③ therefore not applied.
4. the 2026-08-19 Level-I decision — not located. G1 was resolved on the
   options as stated, not against it.

**Gated on ③ being recovered (追補③, unapplied)**

5. recurrence type = parallel authority: fold (a) in, keep sub-types as a
   field, count 5, and record §7 ↔ claims §2 as a case where the countermeasure
   worked.
6. the φ/σ theory-consistency observation, to be labelled "one consistency
   observation, unverified", with no strong inferential wording.
7. pairing-convention fault injection (last-wins mispairing against a synthetic
   AR(1) series at known φ/σ; no Kronos needed) — to be filed.
8. add the pre-execution norm to the BACKLOG commit-rule line (executing
   already-instructed content early is permitted with the reason recorded;
   early execution that changes content is not).

**Contract gaps still open at the freeze**

9. G7 — comparison-table strictness; deferred post-G0.
10. Parquet content canonicalization — no canonical form; nothing binds to a
    byte digest, so it costs nothing today.
11. G9–G11's underlying asymmetries — resolved by placement, not by fixing
    `MetricSpec` / `TestResult` / `MetricRequirements`. Filed post-G0.

**Backlog accumulation** — `BACKLOG.md` now carries the W1D6 section (17 items)
plus the W1D7 section. Nothing from Week 1 was closed silently.

**B12** — unchanged, trigger unchanged: before contact with reproduction #1.
