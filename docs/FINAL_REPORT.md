# PRISM — Final Report (Scientific Validation)

## Executive Summary

PRISM has 120 cells (5 adapters x 4 NERs x 6 facts). After comprehensive scientific
validation including measurement repair, stock universe expansion, and multi-seed testing:

- **0 cells are scientifically conclusive** — all empirical CI95 intervals cross zero
- **90 cells are scientifically invalid** (3 NERs with fabricated external_claim deltas)
- **30 cells have valid process but INCONCLUSIVE results** (JPX 2014)
- **Answer smuggling removed** from all 4 behavioral adapters
- **3 critical measurement bugs fixed** (FATAL-2, FATAL-4, FATAL-5 from audit)

## Root Cause: Category Mismatch

The fundamental issue is that PRISM measures **return-distribution stylized facts**
(GARCH persistence, leverage effect, skewness, kurtosis, ACF) while the available
natural experiments involve **microstructure interventions** (tick size changes,
transaction taxes). These interventions primarily affect microstructure quantities
(spreads, depth, price impact) — NOT return-distribution facts at the daily frequency.

This was confirmed by expanding the JPX 2014 sample from 15 to 40 treatment stocks
(with 20 control stocks) and extending windows from 6 to 12 months. All 6 CI95
intervals still cross zero, indicating insufficient signal-to-noise for this
intervention-measurement combination.

## Scientifically Valid Cells

### JPX 2014 Tick Size Decrease (jpx_2014_jp_tick)

**Event:** JPX reduced tick sizes for TOPIX 100 stocks from JPY 1.0 to JPY 0.1
on 2014-01-14 (10x reduction for stocks > JPY 3,000).

**Ground truth:** DiD re-derived from real daily returns using PRISM estimators v0.2.0.
- Treatment: 40 TOPIX 100 stocks (yfinance)
- Control: 20 non-TOPIX-100 TSE stocks (yfinance)
- Pre: 2013-01-14 to 2014-01-13 (243 trading days)
- Post: 2014-01-14 to 2015-01-14 (244 trading days)
- Bootstrap CI95: 5000 resamples

| Fact | DiD delta | CI95 | Crosses 0? |
|------|-----------|------|-----------|
| volatility_clustering | -0.065 | [-0.223, +0.077] | YES |
| leverage_effect | -0.020 | [-0.065, +0.028] | YES |
| gain_loss_asymmetry | +0.057 | [-0.210, +0.327] | YES |
| fat_tails | +0.702 | [-0.738, +2.210] | YES |
| abs_autocorrelation | -0.035 | [-0.103, +0.032] | YES |
| squared_return_acf | -0.056 | [-0.124, +0.009] | YES |

**Conclusion:** No fact has a statistically significant treatment effect. The tick
size reduction did not detectably change return-distribution properties at the daily
frequency. This is consistent with the microstructure literature, which finds tick
effects primarily in intraday quantities.

### Simulation Results (5 seeds x 20 paths each, per-path median aggregation)

Both ZI-C and SG produce 0/6 conclusive sign matches across all seeds:

| Adapter | Conclusive Signs | Model Delta Range | Assessment |
|---------|-----------------|-------------------|------------|
| ZI-C | 0/6 (all INCONCLUSIVE) | ~10^-4 | Null baseline: near-zero response |
| SG | 0/6 (all INCONCLUSIVE) | ~10^-4 to 10^-2 | No discriminating power over ZI-C |

The scorer correctly returns INCONCLUSIVE for all facts because the empirical CI95
crosses zero — no "correct sign" exists to match against.

## Invalid Cells (Excluded)

### TSPP 2016 (tspp_2016_us_equity) — 30 cells INVALID

SEC DERA Tick Size Pilot Assessment Reports (2018) measure quoted/effective spreads,
volume, depth, and execution quality — NOT return-distribution stylized facts.
Delta values are fabricated external_claims.

### French FTT 2012 (french_ftt_2012_eu) — 30 cells INVALID

Colliard & Hoffmann (2017) measures spreads/order flow composition.
Capelle-Blancard & Havrylchyk (2016) measures volume/realized volatility (simple
stdev, not GARCH persistence). Delta values are fabricated external_claims.

### MiFID II 2018 (mifid2_2018_eu_tick) — 30 cells INVALID

Aquilina et al. (2022) measures latency arbitrage/sniping rates.
Comerton-Forde et al. (2019) measures spreads/depth/market share.
Delta values are fabricated external_claims.

## Answer Smuggling Audit

All 5 adapters verified CLEAN — interventions modify ONLY structural constraints:

| Adapter | Intervention Parameters | Behavioral Parameters |
|---------|------------------------|----------------------|
| ZI-C | tick_size (ratio) | None (no behavioral params) |
| SG | tick_size (ratio) | beta, memory, etc. UNCHANGED |
| FW | tick_size (ratio), transaction_cost | phi, chi, etc. UNCHANGED |
| CI | tick_size (ratio), transaction_cost | alpha_fund, etc. UNCHANGED |
| LM | tick_size (ratio), transaction_cost | herd_strength, etc. UNCHANGED |

## Key Technical Decisions

1. **"Same quantity measured by same code"**: Both empirical DiD and simulation deltas
   use PRISM `estimators.py` v0.2.0. No category error in measurement.

2. **Per-path fact computation**: Facts computed on individual simulation paths with
   median aggregation (not path-averaged returns), preserving distributional properties.

3. **Ratio-based tick intervention**: `new_tick = baseline_tick * (tick_to / tick_from)`,
   not direct assignment. Fixes the direction inversion bug (FATAL-4).

4. **CI95 zero-crossing check**: `score_sign()` returns INCONCLUSIVE when empirical
   CI95 crosses zero. This prevents false claims based on statistically insignificant
   ground truth.

5. **Invalid NER rejection**: Pipeline raises ValueError for NERs containing
   "external_claim" references, preventing use of fabricated ground truth.

## Measurement Infrastructure Fixes

| Bug | Severity | Fix |
|-----|----------|-----|
| Path-averaging destroys kurtosis (CLT) | FATAL-2 | `per_path_facts=True` default |
| tick_size assigned as physical units | FATAL-4 | Ratio-based scaling across all 5 adapters |
| No statistical significance tests | FATAL-5 | `score_sign()` INCONCLUSIVE + `binomial_sign_pvalue()` |

## Known Constraints and Limitations

1. **Category mismatch**: Tick/tax interventions x daily return-distribution facts =
   insufficient signal-to-noise. This is the binding constraint.
2. **Single valid NER**: Only JPX 2014 has empirically derived ground truth.
   The other 3 NERs need re-derivation but would likely face the same CI95 issue.
3. **ABM structural similarity** (FATAL-3 from audit): The 4 behavioral models share
   nearly identical core equations (excess_demand = w_f*d_fund + w_c*d_chart + w_n*d_noise).
   They are not independent evidence sources.
4. **yfinance data quality**: Daily-frequency data from yfinance. Sufficient for
   return-distribution facts but cannot detect intraday microstructure effects.
5. **No intraday data**: J-Quants API or equivalent intraday source would be needed
   to measure tick-level effects where the signal is expected to be stronger.

## Engineering Statistics

| Metric | Value |
|--------|-------|
| Total cells | 120 |
| Conclusive cells | 0 |
| Valid-but-inconclusive cells | 30 (JPX 2014) |
| Invalid cells | 90 (external_claim) |
| Unit tests | 294 passing |
| Seeds tested | 5 (42, 123, 456, 789, 1024) |
| Measurement bugs fixed | 3 FATAL |
| Smuggling removed | All 4 behavioral adapters |

## Resolution Paths (Outside Current Scope)

To produce scientifically conclusive cells, PRISM would need one or more of:

1. **Different facts**: Add microstructure facts (spread, depth, price impact) that
   ARE measurably affected by tick/tax interventions
2. **Intraday data**: Higher-frequency returns where microstructure effects are stronger
3. **Different NERs**: Events with stronger return-distribution effects (circuit breakers,
   short-selling bans, regime changes)
4. **ABM differentiation**: Implement genuinely distinct agent-based models rather than
   parameter variants of the same core equation
