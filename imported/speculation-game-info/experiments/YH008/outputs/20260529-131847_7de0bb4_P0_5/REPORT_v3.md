# YH008 — REPORT v3 (P0.5: direction-robustness of loss-conditional ATH)

**run_id:** `20260529-131847_7de0bb4_P0_5`  ·  extends P0 `20260529-120955_7de0bb4_P0`.
**Decision:** `PASS_STAGE2_LOSS_CONDITIONAL_CONFIRMED`

## Loss-context ATH asymmetry across 3 neutral clean-probe wordings (n=113 pairs, K=1000)
| wording | ATH_loss mean | 95% CI | out-mass max | sign |
|---|---|---|---|---|
| sec1_faithful | +0.0107 | [+0.0066, +0.0147] | 0.0000 | positive |
| minimal | +0.0288 | [+0.0220, +0.0361] | 0.0000 | positive |
| plain | +0.0277 | [+0.0240, +0.0314] | 0.0000 | positive |
| behavioral-framing (P0) | -0.0704 | [-0.0834, -0.0573] | — | flip(neg) |

## Disposition proxy by framing (from existing data, K=1000)
- clean-probe: +0.0172 [+0.0102, +0.0249]
- behavioral-framing: +0.2599 [+0.2435, +0.2778]
(disposition direction is POSITIVE in both framings => robust phenotype, a viable Stage-2 pivot target even if ATH fails.)

## Verdict
All 3 neutral clean-probe wordings give a POSITIVE loss-context ATH asymmetry (CI excludes 0). Direction is stable within the clean-probe family; the behavioral-framing inversion is a reason-generation artifact. Prepare Stage 2 (clean-probe, loss-conditional v_ATH).

## Scope
P0.5 only. Stage 2 NOT touched. P1 (S_purchase pivot) NOT touched.
