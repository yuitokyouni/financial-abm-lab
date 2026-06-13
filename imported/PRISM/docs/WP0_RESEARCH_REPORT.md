# WP0 Research Report — PRISM

**Date:** 2026-05-25
**Status:** Complete
**Author:** Claude (autonomous agent)

---

## 1. Executive Summary

WP0 addresses three questions before any code is written:
1. **Data availability** — Can we obtain micro-level data for the SEC Tick Size Pilot and French/Italian FTTs?
2. **Novelty confirmation** — Is the "seam" (stitching causal inference ΔF with ABM comparative statics ΔF̂ via shared fact estimators) genuinely novel?
3. **Open questions** — Preliminary positions on the 5 open items in §12 of the requirements.

**Verdict:** WP0 passes. The "seam" is novel (with Collver 2017 as closest predecessor — must be cited), MVP data is obtainable (free FINRA/SEC pilot data sufficient for daily-frequency facts), and Phase 1 can proceed.

---

## 2. Literature Review

### 2.1 LOB-Bench (Nagy et al. 2025)

LOB-Bench (ICML 2025, PMLR 267:45437-45460) is the current state-of-the-art benchmark for evaluating generative models of limit order books. It evaluates:

- **Distributional evaluation**: 14 unconditional score distributions (spread, interarrival time, orderbook imbalance, etc.) plus conditional distributions. Distances via L1 and Wasserstein-1.
- **Discriminator scores**: Neural network adversarial scores.
- **Market impact metrics**: Price-response functions for 6 event types.

**Data:** LOBSTER data for NASDAQ equities (GOOG, INTC) from January 2023. Current leaderboard: LOBS5 autoregressive state-space model dominates.

**Relation to PRISM:** LOB-Bench measures *static realism*. PRISM measures *intervention response fidelity*. Static realism is demoted to an "eligibility gate" (§6.1), not the scoring axis. These are orthogonal: a model could score perfectly on LOB-Bench yet fail PRISM if its mechanisms produce incorrect intervention responses.

**Underdetermination:** Guerini & Moneta (2017): "given a set of statistical dependencies, there is an indefinite number of relations of causal dependence that might have generated that regularity." Lamperti (2018) confirms: "many different combinations of traders' behavioural rules are compatible with the same observed dynamics." This is exactly what motivates PRISM.

### 2.2 Agent-Based FTT / Tick-Size / Policy Literature

| Study | What it does | Relation to PRISM |
|-------|-------------|-------------------|
| Westerhoff & Dieci (2006) | ABM with Tobin tax; comparative statics of volatility vs tax rate | Canonical ABM+FTT. Comparative statics only — no real ΔF comparison. |
| Pellizzari & Westerhoff (2009) | Tax effectiveness depends on microstructure | Same gap: ABM-internal only. |
| Chiarella & Iori (2002) | Continuous double auction ABM, heterogeneous agents | Candidate 2nd adapter. No intervention validation. |
| Paddrik et al. (2012) | Flash crash ABM validated against May 6, 2010 | Event-based validation, but single event, qualitative. |
| **Collver (2017, SEC DERA)** | **ABM built alongside Tick Size Pilot; compared predictions to empirical results** | **Closest direct predecessor. Must be cited.** |
| **Zhao & Cui (2020)** | **ABM simulating tick size effects on market quality (Frontiers in Physics)** | **ABM precedent for tick-size intervention, but no formal DiD comparison.** |
| Lussange et al. (2023) | Multi-agent RL, tick size effects | Qualitative directional agreement only. |
| Amendola & Pereira (2025, JEBO) | State-dependent IRFs in ABMs | Closest methodological parallel, but macro (K+S model), within-model only. |

### 2.3 Empirical Microstructure DiD Studies (Ground Truth Supply)

#### SEC Tick Size Pilot (2016–2018)

**Design:** Randomized controlled experiment. ~1,600 small-cap NMS stocks (market cap ≤$3B, price ≥$2, ADTV ≤1M shares).

| Group | ~Securities | Quoting | Trading | Trade-At |
|-------|-----------|---------|---------|----------|
| Control | ~400 | $0.01 | $0.01 | No |
| G1 | ~400 | **$0.05** | $0.01 | No |
| G2 | ~400 | **$0.05** | **$0.05** | No |
| G3 | ~400 | **$0.05** | **$0.05** | **Yes** |

Timeline: Pre-data collection April 2016; pilot start October 3, 2016; termination September 28, 2018.

**Key DiD studies with ground-truth ΔF estimates:**

- **SEC DERA Staff Paper (2018)** — Official assessment. Spreads and volatility increased for all test groups. NBBO depth increased: G1 +335%, G2 +369%, G3 +471%. Price efficiency decreased. **PRISM relevance: VERY HIGH** — the volatility increase is directly relevant for PRISM's vol-related facts.
- **SEC DERA Revisiting Paper (2022)** — Refined methodology with causal impact visualization for differentially tick-constrained stocks.
- **Rindi & Werner (2020, JFE 136(3):879-899)** — Quoted/effective spreads increased; depth increased. Cost for retail-sized orders +~50%. Market maker profits +~40%. For tick-constrained stocks, trading costs more than doubled.
- **Griffith & Roseman (2019, JBF 101:104-121)** — For stocks with pre-pilot spread <$0.05: significant liquidity decrease. For stocks with spread ≥$0.05: non-binding.
- **Albuquerque, Song & Yao (2020, JFE 138(3):700-724)** — Stock price decrease of 1.75-3.2% for small-spread treatment stocks. Clean identification.
- **Comerton-Forde et al. (2019)** — Cross-venue effects: wider ticks shifted trading to sub-penny venues.

#### French FTT (August 2012)
- **Colliard & Hoffmann (2017, JFE 72(6))** — Canonical study. DiD: French treated vs. Dutch/German controls. FTT reduced volume ~20%, widened spreads, *increased* volatility. Informational efficiency decreased.
- **Capelle-Blancard & Havrylchyk (2016)** — Confirmed volume reduction, smaller price impact than expected.

#### Italian FTT (March 2013)
- **Coelho (2016)** — DiD: volume dropped ~15%, spreads widened.
- **Alderighi et al. (2018)** — Distinguished equity tax from HFT levy effects.
- **Cappelletti et al. (2017, ECB WP 1949)** — ECB perspective DiD.
- **Fricke et al. (2021, JFE)** — Cross-country FTT comparison.

### 2.4 Novelty Assessment

**Claim:** "The seam — stitching causal inference on real data with ABM comparative statics using shared fact estimators, in a fully reproducible tensor — is novel."

**Assessment: CONFIRMED as novel, with critical predecessors to cite.**

What does NOT exist:
1. A framework that *systematically* maps ABM intervention parameters to real intervention canonical parameters (AIS)
2. A shared fact estimator library applied identically to both real and simulated data
3. A provenance layer ensuring bit-reproducibility of the comparison
4. A tensor output (mechanism × intervention × fact) rather than scalar model rankings

**Closest predecessors:**
- **Collver (2017, SEC DERA)** — ABM vs. Tick Pilot, informal visual comparison, no shared estimators or provenance. Must cite as direct ancestor.
- **Zhao & Cui (2020)** — ABM studying tick size effects, finds quality weakens with wider ticks (consistent with pilot), but no formal DiD comparison framework.
- **Paddrik et al. (2012)** — Flash crash validation, qualitative, single event.

| Feature | LOB-Bench | Collver 2017 | Zhao & Cui 2020 | Guerini-Moneta | PRISM |
|---------|-----------|--------------|-----------------|----------------|-------|
| Static distributional comparison | Yes | Partial | Partial | No | Gate only |
| Intervention response comparison | No | Yes (informal) | Yes (within-model) | No | **Core axis** |
| Shared fact estimator library | No | No | No | No | **Yes** |
| Multiple causal methods for ground truth | No | No | No | No | **Yes** |
| Provenance/reproducibility layer | No | No | No | No | **Yes (PROV-O)** |
| Mechanism × intervention tensor | No | No | No | No | **Yes** |

**Conclusion:** The seam is novel. PRISM formalizes what Collver (2017) did as a one-off into a reproducible evaluation device.

### 2.5 Speculation Game (SG) as First Adapter

The Speculation Game (Katahira et al. 2019, Physica A 527:121422):
1. **3-action**: Buy/sell/hold — enables non-uniform holding periods
2. **Round-trip mechanism**: Strategy evaluation via capital gains from completed round trips
3. **Cognitive/realistic world duality**: Quinary cognitive threshold for price history

Reproduces 10/11 Cont (2001) stylized facts under a single parameter setting.

**Suitability:** Round-trip cost → natural transaction tax mapping. Cognitive threshold → natural tick size mapping. High fact reproducibility → likely passes eligibility gate. Simple enough for Phase 1 proof of concept.

**Limitations:** No explicit LOB (no depth/queue facts). Toy model. Tick→cognitive threshold mapping is not one-to-one.

---

## 3. Data Availability Assessment

### 3.1 SEC Tick Size Pilot — PRIMARY (Phase 1)

| Source | Granularity | LOB Depth | Cost | Feasibility |
|--------|------------|-----------|------|-------------|
| **FINRA/SEC Appendix B.I** | Daily per security per venue | NBBO depth | **Free** | **HIGH** — purpose-built pilot data |
| **SEC MIDAS** | Daily aggregate | None | **Free** | **HIGH** — all NMS securities |
| **Pilot Securities Lists** | Static | N/A | **Free** | **HIGH** — treatment/control mapping |
| **LOBSTER** | Event/nanosecond | Up to 200 levels | ~$5-7.5K/yr | **HIGH** (NASDAQ only) |
| **NYSE TAQ (WRDS)** | Millisecond | Top-of-book | Institutional | **HIGH** (if university access) |
| **Yahoo Finance** | Daily OHLCV | None | **Free** | **MEDIUM** (daily only) |

**MVP Data Strategy (phased):**

**Phase 1 (free, immediate):**
1. Download FINRA pilot securities lists (treatment/control assignments)
2. Download FINRA/SEC Appendix B.I daily market quality statistics
3. Download SEC MIDAS per-security metrics (2016-Q1 through 2019-Q1)
4. Daily closing prices from Yahoo Finance for return computation

This is **sufficient** to compute daily-frequency leverage effect, volatility clustering, and gain/loss asymmetry, and to run DiD comparing treatment vs control groups.

**Phase 2 (institutional access):**
5. NYSE TAQ via WRDS for millisecond trades/quotes → 5-min realized volatility
6. LOBSTER for NASDAQ pilot stocks if full LOB reconstruction needed for SG calibration

**Verdict: FEASIBLE.** Free data sufficient for MVP facts.

### 3.2 French FTT (August 2012) — SECONDARY (Phase 2)

| Source | Granularity | Cost | Feasibility |
|--------|------------|------|-------------|
| **BEDOFIH** | Tick-level LOB | Free (academic) | **MEDIUM** (French network required) |
| **Refinitiv** | Tick-level | >$10K/yr | **LOW** |
| **Yahoo Finance** | Daily OHLCV | **Free** | **MEDIUM** |
| **Colliard & Hoffmann replication data** | Research dataset | **Check** | **Check** |

Treatment/control: French stocks >€1B (treated) vs Dutch/German (control).

**Verdict: FEASIBLE at daily level.** Free daily data sufficient for Phase 2 facts.

### 3.3 Italian FTT (March 2013) — TERTIARY (Phase 2+)

Daily data freely available via Yahoo Finance. Lower priority.

### 3.4 Stylized Facts Computability

| Fact | Min Freq | Min Obs/Stock | Daily Sufficient? |
|------|----------|--------------|-------------------|
| Volatility clustering | Daily | ~250 days | **Yes** (GARCH persistence) |
| Leverage effect | Daily | ~50-100 days | **Yes** (EGARCH parameter) |
| Gain/loss asymmetry | Daily | ~100 days | **Yes** (skewness/quantiles) |
| Fat tails | Daily | ~100 days | **Yes** (kurtosis/Hill) |
| Bid-ask spread | Tick | N/A | **No** (needs quote data) |
| Market depth | Tick | N/A | **No** (needs LOB data) |

**Key finding:** All three MVP facts computable from free daily data. Tick data adds richness but is not blocking.

---

## 4. Positions on Open Questions (§12)

### 4.1 Where to deep-dive first: (a) AIS, (b) facts DAG, or (c) first natural experiment?

**Position: (c) first, with (a) minimally scaffolded.**

Tick Size Pilot is the first cell. AIS needs just enough to map "tick size increase" → grid width. Full AIS generalization is premature before one working cell. Facts DAG is Phase 3+.

Plan: Phase 1: hardcode `tick_size_increase`. Phase 2: extract AIS when `transaction_tax` is added. Phase 3+: generalize.

### 4.2 Second mechanism family

**Position: Chiarella-Iori (2002) continuous double auction model.**

"Statically equivalent but intervention-divergent" vs SG. Different agent rules (chartist/fundamentalist vs 3-action speculation), different tick-size propagation (price grid quantization vs round-trip cost). Published code exists.

### 4.3 MDL description_length (v0.1)

```
description_length = n_free_params + α · structural_complexity
```
- `n_free_params`: continuously-valued free parameters
- `structural_complexity`: count of distinct behavioral rules / agent types
- `α = 1.0` initially

Deliberately naive. Versioned and auditable per §6.4. Refinement after multiple cells.

### 4.4 Public release strategy

**PRISM core** (scoring, facts, adapters, provenance): **MIT license**. Benefits from open scrutiny.
**Atlas** (NER corpus): **CC-BY-SA**, versioned, with CONTRIBUTING guide. Gatekeeping ensures rigor.

### 4.5 Match threshold for Phase 1

**Sign consistency only.** sign(ΔF̂) == sign(ΔF). Magnitude (ΔF̂ within ci95) reported but not a pass/fail gate. Baseline calibration will be immature in Phase 1; magnitude gate would reject all models.

---

## 5. Risk Assessment Update

| Risk | Status | Mitigation |
|------|--------|------------|
| Data unavailability | **MITIGATED** | Free FINRA/SEC pilot data sufficient for daily-frequency MVP. |
| Novelty refuted | **CLEAR** | No framework stitches ΔF with ΔF̂ systematically. Collver 2017 closest but informal. |
| "Westerhoff did it first" | **ADDRESSABLE** | Westerhoff = ABM-internal. Collver = informal one-off. PRISM = systematic framework. |
| AIS premature abstraction | **MITIGATED** | Hardcode 2 classes, generalize at 3rd. |
| Calibration unreliability | **ACCEPTED** | Δ-based scoring + sign-only Phase 1 threshold. |
| Collver objection | **ADDRESSABLE** | Cite as ancestor. Differentiate: ad hoc vs systematic with shared estimators + provenance. |

---

## 6. Recommended Phase 1 Plan

1. **Data acquisition**: Download free FINRA pilot data + SEC MIDAS + Yahoo Finance daily prices.
2. **Fact Estimator Library v0.1**: `volatility_clustering`, `leverage_effect`, `gain_loss_asymmetry`.
3. **NER #1**: `tspp_2016_us_equity` from SEC DERA (2018) + Rindi & Werner (2020) findings.
4. **SG Adapter**: Speculation Game as first `ModelAdapter`.
5. **Scorer v0.1**: Sign-consistency + magnitude reporting.
6. **Provenance v0.1**: Minimal W3C PROV (data hashes, code versions, RNG seeds).
7. **End-to-end**: `prism run --adapter sg --ner tspp_2016 --facts leverage,volclust,gainloss`.

---

## 7. References

1. Nagy, Z. et al. (2025). LOB-Bench. *ICML 2025, PMLR 267:45437-45460*.
2. SEC DERA (2018). Tick Size Pilot Plan and Market Quality. *SEC White Paper*.
3. SEC DERA (2022). Tick Sizes and Market Quality: Revisiting the Tick Size Pilot. *SEC Working Paper*.
4. Rindi, B. & Werner, I.M. (2020). Tick Size, Liquidity for Small and Large Orders, and Price Informativeness. *JFE* 136(3):879-899.
5. Griffith, T.G. & Roseman, B.S. (2019). Making Cents of Tick Sizes. *JBF* 101:104-121.
6. Albuquerque, R., Song, S., & Yao, C. (2020). The Price Effects of Liquidity Shocks. *JFE* 138(3):700-724.
7. Colliard, J.-E. & Hoffmann, P. (2017). Financial Transaction Taxes, Market Composition, and Liquidity. *JF* 72(6).
8. Capelle-Blancard, G. & Havrylchyk, O. (2016). The Impact of the French Securities Transaction Tax. *IRFA*.
9. Coelho, M. (2016). Dodging Robin Hood.
10. Alderighi, S. et al. (2018). The Italian Financial Transaction Tax.
11. Cappelletti, G. et al. (2017). The Italian FTT. *ECB WP 1949*.
12. Fricke, D. et al. (2021). FTTs and Informational Efficiency. *JFE*.
13. Westerhoff, F. & Dieci, R. (2006). Keynes–Tobin Transaction Taxes. *JEDC* 30(2):293-322.
14. Chiarella, C. & Iori, G. (2002). Microstructure of Double Auction Markets. *QF* 2:346-353.
15. **Collver, C. (2017). An Agent-Based Model of the Tick Size Pilot. *SEC DERA*.**
16. **Zhao, X. & Cui, L. (2020). Tick Size and Market Quality Using an Agent-Based Model. *Frontiers in Physics* 8:135.**
17. Paddrik, M. et al. (2012). An ABM of the E-Mini S&P 500. *CFTC Working Paper*.
18. Cont, R. & Bouchaud, J.-P. (2000). Herd Behavior and Aggregate Fluctuations. *Macroeconomic Dynamics*.
19. Cont, R. (2001). Empirical Properties of Asset Returns: Stylized Facts. *QF*.
20. Katahira, K. et al. (2019). Development of an Agent-Based Speculation Game. *Physica A* 527:121422.
21. LeBaron, B. (2006). Agent-based Computational Finance. *Handbook of Computational Economics*.
22. Comerton-Forde, C. et al. (2019). Inverted Fee Venues. *JFE*.
23. Guerini, M. & Moneta, A. (2017). A Method for ABM Validation. *JEDC*.
24. Lamperti, F. (2018). An Information Theoretic Criterion for Simulation Models. *Econometrics and Statistics*.
25. Lussange, J. et al. (2023). Multi-agent RL and Tick Size Effects.
26. Amendola, N. & Pereira, M.C. (2025). State-dependent IRFs in ABMs. *JEBO*.
27. Fagiolo, G. et al. (2017). Validation of ABMs. *LEM WP 2017/23*.
28. Bouchaud, J.-P., Matacz, A., & Potters, M. (2001). Leverage Effect in Financial Markets.

---

## Appendix A: FTT Ground Truth Disagreement

An important finding from the literature review: **French FTT ground truth is not fully settled.** Studies disagree on key effect signs:

| Metric | Colliard & Hoffmann (2017) | Capelle-Blancard & Havrylchyk (2016) | Parwada et al. (2022) |
|--------|---------------------------|--------------------------------------|----------------------|
| Volume | DOWN (~10%) | DOWN (15-30%) | DOWN |
| Spread | **UP** (significant) | **NEUTRAL** (no significant effect) | **UP** |
| Volatility | Not primary focus | **NEUTRAL** | Not primary focus |

This disagreement is **exactly what PRISM's NER design anticipates**: §3.1 allows multiple `causal_method` entries per NER, with robustness assessed by "whether the sign agrees across identification strategies." For Phase 2, the NER should record multiple ground truth estimates. Volume DOWN is robust across all studies; spread and volatility effects are disputed.

Similarly for **Italian FTT**, Cappelletti et al. (2016) find spreads UP and volatility UP, while Capelle-Blancard (2017) finds both NEUTRAL. The HFT levy component adds additional complexity.

This validates PRISM's design decision to support multiple causal methods and assess sign robustness rather than relying on a single "correct" ΔF.

## Appendix B: Additional References (from FTT research)

29. Parwada, J., Rui, O., & Shen, S. (2022). Financial Transaction Tax and Market Quality: Evidence from France. *IRF* 22(1):90-113.
30. Cipriani, M., Guarino, A., & Uthemann, A. (2022). FTTs and Informational Efficiency: A Structural Estimation. *JFE* 146(3):1044-1072.
31. Hvozdyk, L. & Rustanov, S. (2016). The Effect of FTT on Market Liquidity and Volatility: An Italian Perspective. *IRFA* 45:62-78.
32. Galvani, V. & Ackman, A. (2021). FTT, Liquidity, and Informational Efficiency: Evidence from Italy. *Heliyon* 7(3).
33. Capelle-Blancard, G. (2017). Curbing the Growth of Stock Trading? Order-to-Trade Ratios and FTTs. *JIMFIM* 49:48-73.
34. Chicheportiche, R. & Bouchaud, J.-P. (2014). The Fine-Structure of Volatility Feedback.
