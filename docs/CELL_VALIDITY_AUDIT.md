# PRISM Cell Validity Audit — Phase B

## Overview

PRISM has 4 NERs × 5 adapters × 6 facts = 120 cells. This audit determines which
cells are scientifically valid based on whether the ground-truth deltas actually
measure the same quantities as PRISM's 6 return-distribution stylized facts.

## PRISM's 6 Facts (Measured Quantities)

All six are computed from daily log-return time series using `estimators.py` v0.2.0:

| Fact ID | Quantity | Definition |
|---------|----------|------------|
| volatility_clustering | GARCH(1,1) persistence | α + β from σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1} |
| leverage_effect | Return-vol correlation | Corr(r_t, r²_{t+1}) |
| gain_loss_asymmetry | Skewness | Adjusted Fisher-Pearson skewness of returns |
| fat_tails | Excess kurtosis | Fisher's kurtosis (κ - 3) of returns |
| abs_autocorrelation | ACF of |r_t| at lag 1 | Autocorrelation of absolute returns |
| squared_return_acf | ACF of r²_t at lag 1 | Autocorrelation of squared returns |

## NER-by-NER Audit

### 1. JPX 2014 (`jpx_2014_jp_tick`) — VALID

**Event:** JPX tick size decrease (JPY 1.0 → 0.1) for TOPIX 100 stocks, 2014-01-14.

**Ground truth source:** Empirically re-derived using PRISM's own estimators + DiD
on real daily returns (yfinance, 15 treatment + 10 control stocks, 6-month pre/post).

**Cited references:** `empirical_prism_estimator_v0.2.0`, `yfinance_topix100_2013-2014`

**Validity:** All 6 fact-deltas are valid. Same quantity measured by same code on
real data. Bootstrap CI95 with 2000 resamples.

**Valid cells:** 6 facts × 5 adapters = **30 cells valid**

---

### 2. TSPP 2016 (`tspp_2016_us_equity`) — INVALID (external_claim)

**Event:** SEC Tick Size Pilot, US small-caps, tick $0.01 → $0.05, 2016-10-03.

**Cited references:**
- "SEC DERA, Tick Size Pilot Assessment Reports, 2018"

**What the SEC DERA reports actually measure:**
- Quoted and effective bid-ask spreads
- Realized spread and price impact
- Trading volume and share turnover
- Odd-lot statistics
- Market maker participation
- Limit order book depth

**What PRISM needs:** GARCH persistence, leverage correlation, skewness, kurtosis, ACF.

**Category error:** The SEC DERA reports contain NO measurement of return-distribution
stylized facts. The delta values in this NER (e.g., vol_clustering δ=0.03, fat_tails
δ=0.5) cannot have come from the cited source — they are fabricated external claims.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

**Recovery path:** Re-derive empirically using yfinance daily returns for TSPP
treatment/control stocks (data is publicly available, ~1200 treatment stocks with
known CUSIP lists from SEC).

---

### 3. French FTT 2012 (`french_ftt_2012_eu`) — INVALID (external_claim)

**Event:** French transaction tax (0.2% on buy side), large-caps > EUR 1B, 2012-08-01.

**Cited references:**
- Colliard & Hoffmann, "Financial Transaction Taxes, Market Composition, and
  Liquidity," Journal of Finance, 2017
- Capelle-Blancard & Havrylchyk, "The Impact of the French Securities Transaction
  Tax on Market Liquidity and Volatility," JIMF, 2016

**What Colliard & Hoffmann (2017) actually measure:**
- Bid-ask spreads (quoted, effective, realized)
- Order flow composition (informed vs. uninformed)
- Adverse selection component of spread
- Trading volume
- Market maker inventory risk

**What Capelle-Blancard & Havrylchyk (2016) actually measure:**
- Trading volume and turnover
- Price volatility (realized volatility = stdev of returns, NOT GARCH persistence)
- Tax revenue

**Category error:** Neither paper measures GARCH persistence, leverage correlation,
return skewness, excess kurtosis, or return ACF. Capelle-Blancard reports "volatility"
but this is simple realized vol — a different quantity from GARCH(1,1) α+β.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

**Recovery path:** Re-derive using yfinance daily returns for French large-caps
(treated) vs. comparable European stocks (control). Data is available; the treatment
list is the ~100 stocks on the Euronext Paris SBF 120 with market cap > EUR 1B at
the time.

---

### 4. MiFID II 2018 (`mifid2_2018_eu_tick`) — INVALID (external_claim)

**Event:** MiFID II tick size harmonization, EU large-caps, tick ~EUR 0.005 → 0.01,
2018-01-03.

**Cited references:**
- Aquilina, Budish & O'Neill, "Quantifying the High-Frequency Trading Arms Race,"
  QJE, 2022
- Comerton-Forde, Gregoire & Zhong, "Inverted Fee Venues and Market Quality,"
  JFE, 2019

**What Aquilina, Budish & O'Neill (2022) actually measure:**
- Latency arbitrage and sniping rates
- Speed technology investment
- Trading costs attributable to speed races
- Tick size is analyzed only as a moderator of latency arbitrage

**What Comerton-Forde, Gregoire & Zhong (2019) actually measure:**
- Bid-ask spreads and depth
- Market share across venues
- Maker/taker fee effects on order routing
- Inverted vs. standard fee venue quality

**Category error:** Neither paper reports GARCH persistence, leverage correlation,
return skewness, kurtosis, or return ACF. The delta values in this NER are fabricated.

**Status:** All 6 fact-deltas are **invalid**. 0/30 cells valid.

**Recovery path:** Re-derive using daily return data for EU stocks affected by MiFID II
tick changes vs. control group (Swiss or UK stocks). Identification is more complex here
due to the broad scope of MiFID II changes (not tick-only).

---

## Summary

| NER | Valid Facts | Invalid Facts | Total Valid Cells | Status |
|-----|-----------|---------------|-------------------|--------|
| jpx_2014_jp_tick | 6/6 | 0/6 | 30 | VALID (empirically derived) |
| tspp_2016_us_equity | 0/6 | 6/6 | 0 | INVALID (external_claim) |
| french_ftt_2012_eu | 0/6 | 6/6 | 0 | INVALID (external_claim) |
| mifid2_2018_eu_tick | 0/6 | 6/6 | 0 | INVALID (external_claim) |
| **Total** | **6/24** | **18/24** | **30/120** | |

## Conclusion

Only 30 out of 120 cells (25%) are scientifically valid — all from the JPX 2014 NER.
The other 90 cells use fabricated delta values attributed to papers that measure
different quantities (spreads/volume/depth vs. return-distribution stylized facts).

The 3 invalid NERs could be rescued by applying the same empirical re-derivation
pipeline used for JPX 2014 (fetch daily returns → DiD with PRISM estimators →
replace external_claim). This requires identifying appropriate treatment/control
stock lists and pre/post periods for each event.
