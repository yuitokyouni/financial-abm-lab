# Changelog

## [0.1.0] - 2026-05-25

Initial public release.

### Features

- **5 Agent-Based Model adapters**: SG (Katahira), CI (Chiarella-Iori), ZI (null model),
  LM (Lux-Marchesi), FW (Franke-Westerhoff)
- **4 Natural Experiment Records (NERs)**: US equity tick size (TSPP 2016),
  French FTT 2012, EU MiFID II 2018 tick size, JPX 2014 tick size
- **6 Stylized facts**: volatility clustering, leverage effect, gain/loss asymmetry,
  fat tails, absolute autocorrelation, squared return ACF
- **3 Intervention classes**: tick_size_increase, tick_size_decrease, transaction_tax
- **Scoring pipeline**: MDL weighting, static eligibility gate, causal method weighting
- **Provenance tracking**: data hash, git commit, RNG seed, W3C PROV-O tags
- **CLI**: `prism run`, `prism tensor`, `prism compare`, `prism latex-heatmap`,
  `prism latex-table`, `prism heatmap`, `prism market-data`
- **Visualization**: matplotlib heatmap, LaTeX heatmap (PDF/PGF), LaTeX table export
- **Real market data**: yfinance integration for empirical validation
- **CI/CD**: GitHub Actions with lint, test (Python 3.11-3.13), docs build
- **Documentation**: pdoc API docs, getting started tutorial, CONTRIBUTING guide

### Quality

- 351 tests, 97% coverage
- mypy strict mode (0 errors)
- ruff check + format clean
- PEP 561 py.typed marker
