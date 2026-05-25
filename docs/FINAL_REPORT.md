# PRISM — Final Project Report

## Project Summary

PRISM (Provenance-backed Reproducible Intervention-response Scoring of Mechanisms) is a scoring framework that evaluates financial agent-based models by testing whether they respond to real-world structural interventions the same way actual markets do. Unlike traditional ABM calibration that asks "can the model reproduce static stylized facts?", PRISM asks "does the model respond to structural interventions the same way real markets do?"

The framework produces a fully reproducible phase-diagram tensor (mechanism family x intervention class x stylized fact -> match degree), with provenance sealing, MDL complexity weighting, and causal method weighting.

## Completed Phases

### Phase 1: MVP
- Core types and ModelAdapter protocol
- GARCH(1,1) fact estimator library with bootstrap CI
- Sign + magnitude scorer
- W3C PROV-O provenance tracker
- NER loader + first NER (TSPP 2016 US equity tick size)
- SG adapter (Katahira 2019) + pipeline + CLI

### Phase 2: Diagnostic Intervention + 2nd Mechanism
- French FTT 2012 NER (transaction tax intervention)
- CI adapter (Chiarella-Iori order book model)
- `run_tensor()` full tensor execution + divergence analysis
- `prism tensor` CLI command

### Phase 3: MDL Weighting + Static Eligibility Gate
- MDL weighting: w_mdl = 1/(1+log2(k))
- Static eligibility gate for baseline fact range checking
- Causal method weighting hierarchy (RCT=1.0 > DiD_FE=0.9 > ... > OLS=0.5)
- Phase-diagram heatmap visualization

### Phase 4: Extensibility
- ZI-C adapter (null model benchmark)
- Fat tails (excess kurtosis) + absolute autocorrelation facts
- Causal method comparison (`prism compare`)
- GitHub Actions CI

### Phase 5: Data Connection + Refinement
- Per-path fact estimation
- GARCH optimizer improvement + squared_return_acf fact
- Real market data via yfinance
- mypy strict compliance

### Phase 6: Advanced Analysis + Documentation
- MiFID II 2018 EU tick size NER (3rd NER)
- LM adapter (Lux-Marchesi 1999 herding model)
- JPX 2014 tick size decrease NER (4th NER)
- tick_size_decrease intervention class for all adapters
- FW adapter (Franke-Westerhoff 2012 sentiment switching)
- LaTeX heatmap + table export for publication
- Final tensor: 5 adapters x 4 NERs x 6 facts = 120 cells

### Phase 7: Documentation + Release Preparation
- README with architecture diagram, CLI reference, API examples
- Getting started tutorial
- Paper figure generation script
- pyproject.toml metadata, CONTRIBUTING.md, LICENSE (MIT)
- PEP 561 py.typed marker
- Public API exports (`from prism import run_cell, run_tensor`)

### Phase 8: Test Hardening + CI Strengthening
- CLI tests (28 tests, 99% CLI coverage)
- Market data mock tests (network-independent)
- Python 3.13 CI matrix
- Dead code removal
- 85% coverage threshold enforced

### Phase 9: Test Strengthening + API Docs + v0.1.0
- Pipeline unit tests (32 tests, pipeline.py 25% -> 99%)
- Version bump to v0.1.0
- pdoc API documentation generation
- Total: 351 tests, 97% coverage

### Phase 10: CI/CD + Release Infrastructure
- GitHub Pages deployment workflow (pdoc API docs)
- CI docs verification step
- Release workflow (GitHub Release + TestPyPI on version tags)
- CHANGELOG.md for v0.1.0
- v0.1.0 tag created

## Key Technical Decisions

1. **Protocol-based adapter interface**: Used Python's `Protocol` (structural subtyping) instead of ABC inheritance, enabling adapter authors to implement the interface without importing PRISM types.

2. **YAML NER format**: Natural experiments stored as human-readable YAML with ground-truth deltas, CI95 intervals, causal method tags, and literature references — bridging empirical evidence with simulation.

3. **MDL weighting over AIC/BIC**: Adopted description-length-based weighting w_mdl = 1/(1+log2(k)) to penalize model complexity without assuming specific data distribution.

4. **Static eligibility gate**: Pre-screens baseline simulations for plausible stylized-fact ranges before scoring intervention responses, preventing garbage-in scoring.

5. **Provenance sealing**: Every result cell carries a data hash, git commit, RNG seed, and W3C PROV-O type tags for full reproducibility auditing.

6. **Hatch build system**: Chose hatchling for modern PEP 621 compliance and clean src-layout support.

## Known Constraints

- NER ground-truth deltas are tagged as `external_claim` — recomputation from raw data is not yet implemented
- Real market data tests depend on yfinance + network access (skipped in some CI environments)
- TestPyPI publishing requires a `testpypi` GitHub environment with trusted publishing configured
- GitHub Pages requires repository settings to enable Pages from GitHub Actions

## Recommendations for Future Work

1. **Additional NERs**: Japanese stamp duty changes, Swiss exchange tick reforms, SEC Rule 606 disclosure
2. **Additional adapters**: Santa Fe Artificial Stock Market, ABIDES (JPMorgan), BSE (Dave Cliff)
3. **Bayesian scoring**: Replace point-estimate matching with posterior overlap scoring
4. **Sensitivity analysis**: Systematic parameter sweep for each adapter
5. **Web dashboard**: Interactive tensor explorer with Plotly/Dash
6. **Raw data pipeline**: Automated download + fact estimation from actual market microstructure data
7. **PyPI publication**: Promote from TestPyPI to production PyPI once stable

## Final Statistics

| Metric | Value |
|--------|-------|
| Adapters | 5 (SG, CI, ZI, LM, FW) |
| NERs | 4 |
| Stylized facts | 6 |
| Intervention classes | 3 |
| Tensor cells | 120 |
| Tests | 351 |
| Coverage | 97% |
| mypy strict errors | 0 (26 files) |
| Python versions | 3.11, 3.12, 3.13 |
| Version | 0.1.0 |
