# Prompt-sensitivity notes (Stage 0.2)

## Why this file exists
The clean-probe decision is sensitive to the *phrasing* of the closing answer instruction, even though the FCLAgent Premise/Instruction/Information body and the literal assistant prefix `{"0": {"is_buy": "` are held fixed. This is a measurement-instrument risk to carry into Stage 2+: `v_ATH` effects must be shown robust to neutral wording, or a wording sweep must bound them.

## The observed drift
- An early *embellished* wording (`embellished_v0`: added `(True = buy more, False = sell)` + short-selling/cash caveats) gave **P(sell)=0.831** on the section-1 loss state.
- The section-1-faithful minimal wording (`sec1_faithful`) gives **P(sell)=0.687** (target 0.896).
- Reproduced section-1 signal: tight(|err|<=0.03)=False, qualitative(>=0.75)=False.

## Wording sweep on the section-1 loss state (smoke_loss)
| variant | P(sell) | out-of-group mass |
|---|---|---|
| sec1_faithful | 0.687 | 0.0000 |
| minimal | 0.747 | 0.0000 |
| orientation_explicit | 0.805 | 0.0000 |
| embellished_v0 | 0.831 | 0.0000 |

**P(sell) range across neutral wordings = 0.144.**

## Determinism
- Two forwards on the same state: bit_exact=True, abs_diff=0.00e+00 (greedy logit read => deterministic).

## Batched vs single
- max_abs_dev=0.00001, ok=True (left-padded batch matches single forward).

## Token-group membership (frozen)
- True group ids: [837, 1904, 2575, 3082, 8378, 21260]
- False group ids: [905, 3641, 3934, 4139, 7989, 31451]
- EXCLUDED semantic aliases (Yes/yes/1, No/no/0): see diagnostics.json `EXCLUDED_semantic_aliases`. They carry ~0 decision-slot mass; in-group mass 0.9997. Excluded because folding them in is a *semantic* judgement, not a spelling-variant fact.

## Implication for Stage 2+
Record this sensitivity as a known risk. If the section-1 signal depends on wording, `v_ATH` causal claims should be validated under multiple neutral wordings (or a wording sweep reported alongside the gate), so the effect is attributed to the activation direction and not to a brittle prompt phrasing.

## CANONICAL wording (FROZEN 2026-05-29)

**Canonical clean-probe wording = `sec1_faithful`** (= render.CLEAN_ANSWER), recorded in
`config.yaml: probe.canonical_wording`. Used for all Stage 1+ measurements.

Selection rationale:
- Matches section-1's stated literal closing ("Answer JSON only. is_buy must be True or
  False.") and the FCLAgent Appendix-A answer-format body → continuity with the design.
- In-group mass ~0.9997, indistinguishable across all 4 variants (no discriminating power).
- Sell-direction on the section-1 loss state is consistent across all 4 neutral wordings
  (P(sell) 0.687 / 0.747 / 0.805 / 0.831, all > 0.5). Chose the least-embellished /
  most spec-faithful variant to avoid baking an orientation hint ("True=buy, False=sell")
  into the prompt.
- The other 3 variants are retained for the sensitivity sweep ONLY.

Section-1's P(sell)=0.896 is treated as a wording-sensitive single point (sweep range
0.144). v_ATH causal claims in Stage 2+ must be shown robust across neutral wordings.
