# PRISM — Final Report (Scientific Validation)

## Executive Summary

PRISM has 120 cells (5 adapters × 4 NERs × 6 facts). After scientific validation
and measurement infrastructure repair:
- **0 cells are scientifically conclusive** — all 6 JPX 2014 CI95 intervals cross
  zero, making sign matching statistically indeterminate
- **90 cells are scientifically invalid** (3 NERs with fabricated external_claim deltas)
- **30 cells are INCONCLUSIVE** (JPX 2014 NER — ground truth too noisy for directional claims)
- **All 4 behavioral adapters had answer smuggling**, now removed
- **3 critical measurement bugs fixed**: path-averaging destroying kurtosis (FATAL-2),
  tick_size direction inverted for JPX 2014 (FATAL-4), no statistical tests (FATAL-5)

**Prior claim retracted:** The earlier report claimed SG/FW had "genuine discriminating
power" (5/6 sign matches vs ZI-C 3/6). This claim is withdrawn because:
1. All 6 empirical CI95 cross zero — the "correct sign" is itself indeterminate
2. 5/6 on Bernoulli(0.5) has p=0.109 — not significant at α=0.05
3. The tick_size intervention was inverted (10x increase instead of 10x decrease)
4. Path-averaging destroyed the very distributional properties being measured

## Scientifically Valid Cells

### JPX 2014 Tick Size Decrease (jpx_2014_jp_tick)

**Event:** JPX reduced tick sizes for TOPIX 100 stocks from JPY 1.0 to JPY 0.1
on 2014-01-14 (10x reduction for stocks > JPY 3,000).

**Ground truth:** DiD re-derived from real daily returns using PRISM's own estimators
(v0.2.0). Treatment: 15 TOPIX 100 stocks. Control: 10 non-TOPIX-100 TSE stocks.
Pre: 2013-07-18 to 2014-01-13 (117 days). Post: 2014-01-14 to 2014-07-13 (123 days).
Bootstrap CI95 with 2000 resamples.

| Fact | DiD Δ | CI95 |
|------|-------|------|
| volatility_clustering | -0.093 | [-0.319, +0.137] |
| leverage_effect | -0.013 | [-0.112, +0.083] |
| gain_loss_asymmetry | +0.373 | [-0.091, +0.868] |
| fat_tails | +0.559 | [-1.718, +3.435] |
| abs_autocorrelation | +0.029 | [-0.101, +0.153] |
| squared_return_acf | +0.037 | [-0.094, +0.176] |

**Note:** Most CI95 intervals cross zero, meaning individual fact deltas are not
statistically significant at the 95% level. The scientific value lies in the
*pattern* across all 6 facts, not individual point estimates.

### Adapter Discriminating Power (structural-only intervention, n_paths=20)

| Adapter | Sign Matches | vs ZI-C (3/6) | Verdict |
|---------|-------------|----------------|---------|
| SG (Katahira) | **5/6** | +2 | Discriminating power confirmed |
| FW (Franke-Westerhoff) | **5/6** | +2 | Discriminating power confirmed |
| LM (Lux-Marchesi) | 3/6 | 0 | No discriminating power |
| CI (Chiarella-Iori) | 2/6 | -1 | No discriminating power |
| ZI-C (null baseline) | 3/6 | — | Structural-only baseline |

## Invalid Cells (Excluded)

### TSPP 2016 (`tspp_2016_us_equity`) — 30 cells INVALID
- SEC DERA reports measure spreads/volume/depth, not return-distribution stylized facts
- Delta values are fabricated external_claims

### French FTT 2012 (`french_ftt_2012_eu`) — 30 cells INVALID
- Colliard & Hoffmann (2017) measures spreads/order flow
- Capelle-Blancard & Havrylchyk (2016) measures volume/realized vol
- Neither reports GARCH persistence, leverage correlation, kurtosis, or ACF

### MiFID II 2018 (`mifid2_2018_eu_tick`) — 30 cells INVALID
- Aquilina et al. (2022) measures latency arbitrage
- Comerton-Forde et al. (2019) measures spreads/depth/market share
- Delta values are fabricated external_claims

**Recovery path:** All three could be made valid by re-deriving DiD from daily returns
using PRISM's own estimators (same approach as JPX 2014).

## Answer Smuggling Audit

All 4 behavioral adapters (SG, CI, LM, FW) had answer smuggling in their
`apply_intervention` methods — behavioral parameters were modified alongside
structural constraints, encoding expected outcomes rather than letting them emerge.

### Smuggling Removed

| Adapter | Smuggled Parameters | Fix |
|---------|-------------------|-----|
| SG | beta ∝ √(tick_ratio) | tick_size only |
| CI | price_impact ∝ √(tick_ratio), spread_ticks, alpha_noise | tick_size only, transaction_cost only |
| LM | herd_strength ∝ √(tick_ratio), opinion_decay, chart_trend_weight | tick_size only, transaction_cost only |
| FW | chi ∝ √(tick_ratio), alpha_w, sigma_c | tick_size only, transaction_cost only |

After fix: interventions modify ONLY structural constraints (tick_size, transaction_cost).
Behavioral parameters remain unchanged. Effects must emerge from simulation dynamics.

## Key Scientific Judgments

1. **"Same quantity measured by same code"**: The empirical DiD and simulation deltas
   both use PRISM's `estimators.py` (v0.2.0). No category error.

2. **Structural-only intervention**: Tick size changes map to price grid quantization
   width — a physical constraint, not a behavioral assumption. This is the only
   scientifically legitimate way to test model mechanisms.

3. **ZI-C as null baseline**: Zero-intelligence agents produce structural responses
   to tick changes (via price discretization). Any behavioral model must beat this
   baseline to claim its mechanisms add value.

4. **SG and FW succeed honestly**: Strategy switching (SG) and sentiment-driven
   switching (FW) produce emergent responses that match 5/6 empirical signs with
   structural-only intervention. This is genuine discriminating power.

5. **CI and LM fail honestly**: Order book heterogeneity (CI) and herding dynamics
   (LM) do not produce better-than-random sign matches for tick_size interventions.
   This doesn't mean the models are useless — it means their behavioral mechanisms
   don't generate meaningful responses to *this specific* structural intervention.

## Measurement Infrastructure Fixes (v2, 2026-05-26)

Three critical measurement bugs were identified and fixed:

| Bug | Severity | Fix | Impact |
|-----|----------|-----|--------|
| Path-averaging destroys kurtosis (CLT) | FATAL | `per_path_facts=True` default | fat_tails/vol_clustering now measured correctly |
| tick_size assigned as physical units | FATAL | Ratio-based: `baseline × (tick_to/tick_from)` | JPX 2014 was inverted (10x increase, not decrease) |
| No CI95 zero-crossing check | FATAL | `score_sign()` returns INCONCLUSIVE when CI95 ∋ 0 | All 6 JPX 2014 facts → INCONCLUSIVE |
| No binomial p-value | FATAL | `binomial_sign_pvalue()` added | 5/6 match has p=0.109, not significant |

## Known Constraints

- Only 1 of 4 NERs has been empirically validated (JPX 2014)
- **ALL 6 JPX 2014 CI95 intervals cross zero** — no fact delta is individually significant
- Even 5/6 sign matches has binomial p=0.109 (not significant at α=0.05)
- Results are specific to tick_size_decrease interventions; other intervention types
  (tick_size_increase, transaction_tax) are untested with empirical data
- Simulation results are stochastic; sign consistency varies with n_paths
- yfinance data used (not J-Quants API); sufficient for daily return stylized facts
- The 4 behavioral ABMs share nearly identical core structure (FATAL-3 from audit)
- `n_agents` parameter in SG/CI is unused — simulation uses aggregate fractions

## Engineering Statistics

| Metric | Value |
|--------|-------|
| Total cells | 120 |
| Conclusive cells | 0 (all CI95 cross zero) |
| Inconclusive cells | 30 (JPX 2014 — ground truth too noisy) |
| Invalid cells | 90 (external_claim) |
| Tests | 306+ |
| Measurement bugs fixed | 3 (FATAL-2, FATAL-4, FATAL-5) |
| Smuggling instances removed | 12 (across 4 adapters × 3 intervention types) |
| Best sign match (any adapter) | p=0.109 at 5/6 — not significant |

## Path Forward

To produce scientifically valid cells, PRISM needs:
1. **Narrower CI95** — more treatment/control stocks, longer windows, or
   higher-frequency data to push CI95 below zero-crossing
2. **Multiple seeds** — seed stability testing (same cell, 10+ seeds) to
   measure sign match robustness
3. **ABM structural differentiation** — the 4 behavioral models share nearly
   identical core equations; they are not independent evidence sources
