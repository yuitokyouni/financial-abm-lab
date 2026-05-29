# YH008 Stage 1 — REPORT v2 (P0: ATH construction fix re-measurement)

**run_id:** `20260529-120955_7de0bb4_P0`  ·  supersedes the ATH numbers of `20260529-092454_7de0bb4`.
**Updated gate:** `PASS_STAGE2_LOSS_CONDITIONAL`  (v1 was provisional `YEE_SHARMA_FALLBACK`).

## Fix
states.py now guarantees `ATH >= max(price, purchase)` for every state. The ATH contrast is: no_drawdown `ATH == max(price, purchase)` vs drawdown `ATH > price` — valid in BOTH gain and loss contexts (the prior loss x price-at-ATH cell was ill-posed: a loss implies price<purchase<=ATH, so price cannot sit at the all-time high).

## ATH asymmetry = P(sell|drawdown) - P(sell|no_drawdown), bootstrap K=1000

| framing | context | mean | 95% CI |
|---|---|---|---|
| clean-probe (canonical) | gain | -0.0014 | [-0.0043, +0.0015] |
| clean-probe (canonical) | loss | +0.0107 | [+0.0067, +0.0146] |
| clean-probe (canonical) | overall | +0.0043 | [+0.0017, +0.0070] |
| behavioral-framing | gain | +0.0039 | [-0.0020, +0.0095] |
| behavioral-framing | loss | -0.0704 | [-0.0834, -0.0573] |

## Disposition (recomputed; states clamped for validity)
- paired = +0.0233 [+0.0162, +0.0301]
- marginal = +0.0248 [+0.0151, +0.0345]
- out-of-group mass: median 2.46e-05, max 3.22e-05, flag-rate 0.000

## Verdict
ATH asymmetry is POSITIVE in the (now-valid) LOSS context => ATH effect is loss-conditional. Proceed to Stage 2 with v_ATH identification restricted to the loss context.

## Scope
P0 only (ATH construction fix + re-measure). P1+ (S_purchase pivot / profile prompting / Gemma) NOT touched — awaiting Yuito.

## ⚠ Robustness caveat (Stage 2 risk #1)
The loss-conditional ATH asymmetry SIGN is framing-dependent:
- clean-probe (canonical): loss **+0.0107** [+0.0067, +0.0146]  (human-like)
- behavioral-framing:      loss **-0.0704** [-0.0834, -0.0573]  (reversed)

The gate uses the canonical clean-probe (what Stage 2 steers on) -> PASS_STAGE2_LOSS_CONDITIONAL.
But the strong behavioral-framing reversal means the effect is NOT robust across prompt
framings. Per the Stage-2 requirement (v_ATH effects must be robust to neutral wording),
Stage 2 must: (a) identify v_ATH in the LOSS context on the canonical clean-probe, and
(b) verify the direction holds (or characterise the flip) under >=1 other neutral wording
before any causal claim. Magnitudes are small (~1pp clean), so adequately powered held-out
n is essential (addendum n_min). Recommend Yuito confirm PASS-with-caveat vs treat the
framing reversal as gate-failing.
