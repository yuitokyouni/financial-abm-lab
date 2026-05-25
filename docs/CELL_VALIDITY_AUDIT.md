# PRISM Cell Validity Audit — Phase B

## Overview

PRISM has 4 NERs × 5 adapters × 6 facts = 120 cells. This audit determines which
cells are scientifically valid based on whether the ground-truth deltas actually
measure the same quantities as PRISM's 6 return-distribution stylized facts.

## PRISM's 6 Facts (Measured Quantities)

All six are computed from daily log-return time series using `estimators.py` v0.2.0:

| Fact ID | Quantity | Definition |
|---------|----------|------------|
| volatility_clustering | GARCH(1,1) persistence | alpha + beta from sigma^2_t = omega + alpha*r^2_{t-1} + beta*sigma^2_{t-1} |
| leverage_effect | Return-vol correlation | Corr(r_t, r^2_{t+1}) |
| gain_loss_asymmetry | Skewness | Adjusted Fisher-Pearson skewness of returns |
| fat_tails | Excess kurtosis | Fisher's kurtosis (kappa - 3) of returns |
| abs_autocorrelation | ACF of |r_t| at lag 1 | Autocorrelation of absolute returns |
| squared_return_acf | ACF of r^2_t at lag 1 | Autocorrelation of squared returns |

## NER-by-NER Audit

### 1. JPX 2014 (`jpx_2014_jp_tick`) — VALID, INCONCLUSIVE

**Event:** JPX tick size decrease (JPY 1.0 to 0.1) for TOPIX 100 stocks, 2014-01-14.

**Ground truth source:** Empirically re-derived using PRISM's own estimators + DiD
on real daily returns (yfinance, 40 treatment + 20 control stocks, 12-month pre/post,
5000 bootstrap resamples).

**Cited references:** `empirical_prism_estimator_v0.2.0`, `yfinance_topix100_40stocks_243d`

**Validity:** Process is scientifically sound — same quantity measured by same code
on real data. However, all 6 CI95 intervals cross zero.

| Fact | delta_hat | CI95 | Crosses 0? |
|------|-----------|------|-----------|
| volatility_clustering | -0.065 | [-0.223, +0.077] | YES |
| leverage_effect | -0.020 | [-0.065, +0.028] | YES |
| gain_loss_asymmetry | +0.057 | [-0.210, +0.327] | YES |
| fat_tails | +0.702 | [-0.738, +2.210] | YES |
| abs_autocorrelation | -0.035 | [-0.103, +0.032] | YES |
| squared_return_acf | -0.056 | [-0.124, +0.009] | YES |

**Simulation results (5 seeds x 20 paths each):**
- ZI-C: 0/6 conclusive, model deltas ~10^-4
- SG: 0/6 conclusive, model deltas ~10^-4 to 10^-2

**Valid cells:** 6 facts x 5 adapters = **30 cells valid but INCONCLUSIVE**

---

### 2. TSPP 2016 (`tspp_2016_us_equity`) — INVALID (external_claim)

**Event:** SEC Tick Size Pilot, US small-caps, tick $0.01 to $0.05, 2016-10-03.

**Cited references:** SEC DERA, Tick Size Pilot Assessment Reports, 2018

**What the SEC DERA reports actually measure:**
- Quoted and effective bid-ask spreads
- Realized spread and price impact
- Trading volume and share turnover
- Odd-lot statistics
- Market maker participation
- Limit order book depth

**Category error:** The SEC DERA reports contain NO measurement of return-distribution
stylized facts. The delta values in this NER are fabricated external claims.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

---

### 3. French FTT 2012 (`french_ftt_2012_eu`) — INVALID (external_claim)

**Event:** French transaction tax (0.2% on buy side), large-caps > EUR 1B, 2012-08-01.

**Cited references:**
- Colliard & Hoffmann (2017) — measures spreads, order flow composition, adverse selection
- Capelle-Blancard & Havrylchyk (2016) — measures volume, realized volatility (simple stdev, not GARCH)

**Category error:** Neither paper measures GARCH persistence, leverage correlation,
return skewness, excess kurtosis, or return ACF.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

---

### 4. MiFID II 2018 (`mifid2_2018_eu_tick`) — INVALID (external_claim)

**Event:** MiFID II tick size harmonization, EU large-caps, 2018-01-03.

**Cited references:**
- Aquilina, Budish & O'Neill (2022) — measures latency arbitrage and sniping rates
- Comerton-Forde, Gregoire & Zhong (2019) — measures spreads, depth, market share

**Category error:** Neither paper reports return-distribution stylized facts.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

---

## Summary

| NER | Valid Facts | Status | Conclusive? |
|-----|-----------|--------|------------|
| jpx_2014_jp_tick | 6/6 | VALID | NO (all CI95 cross zero) |
| tspp_2016_us_equity | 0/6 | INVALID | N/A |
| french_ftt_2012_eu | 0/6 | INVALID | N/A |
| mifid2_2018_eu_tick | 0/6 | INVALID | N/A |
| **Total** | **6/24** | — | **0 conclusive** |

## Root Cause

The fundamental issue is a **category mismatch**: PRISM measures return-distribution
stylized facts (kurtosis, GARCH persistence, leverage effect, skewness, ACF), but the
available natural experiments involve microstructure interventions (tick size changes,
transaction taxes) whose effects are primarily on microstructure quantities (spreads,
depth, price impact, execution quality).

At the daily frequency, these microstructure effects are too small relative to noise
to produce statistically significant changes in return-distribution facts. The CI95
intervals are wide because the signal-to-noise ratio is inherently low for this
intervention-measurement combination.

This is not a bug — it is a valid scientific finding about the relationship between
microstructure interventions and return-distribution properties.
