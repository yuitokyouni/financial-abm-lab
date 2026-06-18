# atlas — Intervention Atlas Minimum Viable Arena (spec 002)

Contract-first implementation of the MVA (`specs/002-minimum-viable-arena.md`). A
model that satisfies `model_contract_v1` (`docs/model_contract_v1.md`) becomes
eligible for an Atlas row; nothing here ranks model validity (spec 002 §1 non-goal).

| Module | Role | spec 002 §13 task |
|---|---|---|
| `contract` | `model_contract_v1` surface + C0/C1/C2 conformance + `ContractModel` adapter | 1 |
| `intervention` | the four B2 schemes (a/b/c/d) the P1 run needs; θ=0 identity | 4 |
| `profiles` | the six GT-free scoring-profile axes (radar, no scalar validity rank) | 2 |
| `registry` | frozen semantic-labeling layer (kept out of the CI gate) + diversity | 3 |
| `row` | `AtlasRow` schema + `emit_row` (dogfood the contract over `abm_models`) | 3, 5 |
| `reference_atlas` | first internal reference atlas + launch-readiness check | 5 |
| `ignition` | frozen "no external infra before P1 GO + diagnostic case" rule | 6 |

## Regenerate the reference atlas

```bash
uv run python -m atlas.reference_atlas   # → docs/atlas/reference_atlas_v0.json
uv run pytest packages/atlas/tests -q
```

## Honest current state

`launch_ready = False`: the only blocking criterion is an intervention dimension
that separates SF-equivalent models (spec 002 §10.4). Canonical models are C0/C2
with **no exposed C1 channel** yet — the intervention-response column is
`pending_c1` for every row. This is the true state (the order-book channel work,
PROV-ABM-atlas Finding 0002, unlocks C1), recorded rather than faked.
