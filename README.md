# PRISM

**Provenance-backed Reproducible Intervention-response Scoring of Mechanisms**

PRISM is a scoring framework that evaluates financial agent-based models (ABMs) by passing them through a corpus of natural experiments with known structural changes. It compares the stylized-fact changes predicted by each model against changes observed in real market data, producing a fully reproducible **phase-diagram tensor** (mechanism family x intervention class x stylized fact -> match degree).

Unlike traditional ABM calibration which asks "can the model reproduce static stylized facts?", PRISM asks "does the model respond to structural interventions the same way real markets do?"

## Architecture

```
NER Corpus (YAML)          Model Adapters (Python)
  tspp_2016_us_equity        SG  — Speculation Game (Katahira 2019)
  french_ftt_2012_eu         CI  — Chiarella-Iori order book
  mifid2_2018_eu_tick        ZI  — Zero Intelligence (null model)
  jpx_2014_jp_tick           LM  — Lux-Marchesi herding
                             FW  — Franke-Westerhoff sentiment
        |                          |
        v                          v
  +-----------------------------------------+
  |          PRISM Pipeline                 |
  |  calibrate -> intervene -> simulate     |
  |  -> estimate facts -> score deltas      |
  +-----------------------------------------+
        |
        v
  Phase-Diagram Tensor (5 x 4 x 6 = 120 cells)
  + MDL weighting + causal method weighting
  + static eligibility gate
  + W3C PROV-O provenance sealing
```

## Installation

```bash
git clone https://github.com/yuitokyouni/PRISM.git
cd PRISM
pip install -e ".[dev]"
```

For visualization and real market data calibration (optional):

```bash
pip install -e ".[dev,viz,real-data]"
```

Requires Python >= 3.11.

## Quick Start

### Run a single cell

```bash
prism run \
  --adapter sg \
  --ner tspp_2016_us_equity \
  --facts volclust,leverage,gainloss,fattails,absacf,sqacf \
  --seed 42 --n-paths 20
```

### Run the full tensor

```bash
prism tensor \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu,mifid2_2018_eu_tick,jpx_2014_jp_tick \
  --facts volclust,leverage,gainloss,fattails,absacf,sqacf \
  --seed 42 --n-paths 20 --output results.json
```

### Generate a heatmap

```bash
prism heatmap \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu,mifid2_2018_eu_tick,jpx_2014_jp_tick \
  --facts volclust,leverage,gainloss,fattails,absacf,sqacf \
  --output phase_diagram.png
```

### Generate LaTeX figures and tables

```bash
prism latex-heatmap \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu \
  --facts volclust,leverage,gainloss \
  --output fig_heatmap.pdf

prism latex-table \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu \
  --facts volclust,leverage,gainloss \
  --output table_results.tex
```

## Model Adapters

| ID | Model | Reference | Free Params | Intervention Classes |
|----|-------|-----------|:-----------:|---------------------|
| `sg` | Speculation Game | Katahira et al. (2019) | 7 | tick_size_increase, tick_size_decrease, transaction_tax |
| `ci` | Chiarella-Iori | Chiarella & Iori (2002) | 9 | tick_size_increase, tick_size_decrease, transaction_tax |
| `zi` | Zero Intelligence | Gode & Sunder (1993) | 4 | tick_size_increase, tick_size_decrease, transaction_tax |
| `lm` | Lux-Marchesi | Lux & Marchesi (1999, 2000) | 8 | tick_size_increase, tick_size_decrease, transaction_tax |
| `fw` | Franke-Westerhoff | Franke & Westerhoff (2012) | 6 | tick_size_increase, tick_size_decrease, transaction_tax |

All adapters conform to the `ModelAdapter` protocol (`src/prism/types.py`), making it straightforward to add new ABMs.

## Natural Experiment Records (NERs)

| NER ID | Intervention | Venue | Date | Source |
|--------|-------------|-------|------|--------|
| `tspp_2016_us_equity` | tick_size_increase ($0.01 -> $0.05) | US small-cap | 2016-10-03 | SEC DERA Reports |
| `french_ftt_2012_eu` | transaction_tax (0 -> 0.2%) | France | 2012-08-01 | Colliard & Hoffmann (2017) |
| `mifid2_2018_eu_tick` | tick_size_increase (EUR 0.005 -> 0.01) | EU | 2018-01-03 | Aquilina et al. (2022) |
| `jpx_2014_jp_tick` | tick_size_decrease (JPY 1.0 -> 0.1) | Japan large-cap | 2014-01-14 | Comerton-Forde et al. (2022) |

NERs are stored as YAML files in `data/ner/`. Each records the intervention parameters, ground truth deltas with 95% confidence intervals, causal identification method, and literature references.

## Stylized Facts

| ID | Description | Estimator |
|----|-------------|-----------|
| `volatility_clustering` | GARCH(1,1) persistence (alpha + beta) | Quasi-MLE |
| `leverage_effect` | Correlation between returns and future volatility | Pearson correlation |
| `gain_loss_asymmetry` | Skewness of return distribution | scipy.stats.skew |
| `fat_tails` | Excess kurtosis | scipy.stats.kurtosis |
| `abs_autocorrelation` | Autocorrelation of absolute returns | numpy.corrcoef at lag 1 |
| `squared_return_acf` | Autocorrelation of squared returns | numpy.corrcoef at lag 1 |

## Scoring Methodology

Each cell in the phase-diagram tensor is scored through:

1. **Sign consistency**: Does the model's delta have the same sign as the empirical delta?
2. **Magnitude check**: Does the model's delta fall within the empirical 95% CI?
3. **MDL weighting**: Models with fewer free parameters receive higher weight: `w_mdl = 1 / (1 + log2(k))`
4. **Causal method weighting**: RCT (1.0) > DiD with FE (0.9) > ... > OLS (0.5)
5. **Static eligibility gate**: Baseline facts must fall within empirical ranges before intervention scoring

## CLI Reference

| Command | Description |
|---------|-------------|
| `prism run` | Run one cell of the tensor |
| `prism tensor` | Run the full adapter x NER x fact tensor |
| `prism compare` | Compare causal method weightings for one cell |
| `prism heatmap` | Generate a phase-diagram heatmap (PNG) |
| `prism latex-heatmap` | Generate publication-quality heatmap (PDF/PGF) |
| `prism latex-table` | Export results as LaTeX tabular |

### Common Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--seed` | 42 | RNG seed for bit-exact reproducibility |
| `--n-paths` | 10 | Number of simulation paths to average |
| `--per-path-facts` | false | Compute facts per path (preserves kurtosis/skewness) |
| `--real-data` | false | Use real market data via yfinance for calibration |
| `--output` | stdout | Output file path (JSON, PNG, PDF, or TEX) |

### Fact Aliases

Short aliases are supported for convenience:

| Alias | Full ID |
|-------|---------|
| `volclust` | `volatility_clustering` |
| `leverage` | `leverage_effect` |
| `gainloss` | `gain_loss_asymmetry` |
| `fattails` | `fat_tails` |
| `absacf` | `abs_autocorrelation` |
| `sqacf` | `squared_return_acf` |

## Python API

```python
from prism import run_cell, run_tensor

# Single cell
result = run_cell(
    adapter_name="sg",
    ner_path="data/ner/tspp_2016_us_equity.yaml",
    fact_ids=["volatility_clustering", "leverage_effect"],
    seed=42, n_paths=20,
)
print(result.summary())

# Full tensor
tensor = run_tensor(
    adapter_names=["sg", "ci", "zi", "lm", "fw"],
    ner_paths=[
        "data/ner/tspp_2016_us_equity.yaml",
        "data/ner/french_ftt_2012_eu.yaml",
    ],
    fact_ids=["volatility_clustering", "leverage_effect", "fat_tails"],
    seed=42, n_paths=20,
)
print(tensor.summary())
```

## Adding a New Adapter

Implement the `ModelAdapter` protocol:

```python
from prism.types import (
    CalibrationArtifact, CanonicalIntervention, ComplexitySpec,
    MarketData, ModelAdapter, SimulatedMarketData,
)

class MyAdapter:
    def calibrate_baseline(self, pre_data: MarketData, ais_context: dict) -> CalibrationArtifact:
        ...

    def apply_intervention(self, calib: CalibrationArtifact, intervention: CanonicalIntervention) -> "MyAdapter":
        ...

    def simulate(self, seed: int, n_paths: int) -> SimulatedMarketData:
        ...

    def describe_complexity(self) -> ComplexitySpec:
        ...
```

Then register it in `src/prism/pipeline.py`:

```python
ADAPTER_REGISTRY["my"] = MyAdapter
```

## Adding a New NER

Create a YAML file in `data/ner/`:

```yaml
ner_id: "my_experiment_2020"

intervention:
  class: "transaction_tax"
  canonical_params:
    rate_from: 0.0
    rate_to: 0.001

venue: "US_equity"
date_effective: "2020-01-15"
assignment: "quasi_experimental"

ground_truth_delta:
  - fact_id: "volatility_clustering"
    delta_hat: 0.05
    ci95: [0.01, 0.09]
    causal_method: "did_firm_fe"
    unit: "relative"
    references:
      - "Author et al. (2021)"
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=prism --cov-report=term-missing

# Lint + format check
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/prism/

# Generate paper figures (output/)
python scripts/generate_paper_figures.py
```

## Project Structure

```
src/prism/
  types.py              Core data types and ModelAdapter protocol
  pipeline.py           Evaluation pipeline (run_cell, run_tensor)
  cli/main.py           CLI entry point
  adapters/             ABM implementations (sg, ci, zi, lm, fw)
  data/ner_loader.py    NER YAML loader
  data/market_data.py   Real market data fetcher (yfinance)
  facts/estimators.py   Stylized fact estimators
  scoring/scorer.py     Sign + magnitude matching
  scoring/mdl.py        MDL complexity weighting
  scoring/causal.py     Causal method weighting
  scoring/eligibility.py  Static eligibility gate
  provenance/tracker.py   W3C PROV-O provenance sealing
  viz/heatmap.py        Matplotlib heatmap
  viz/latex.py          LaTeX figure and table export
data/ner/               Natural Experiment Records (YAML)
tests/                  Unit and integration tests
scripts/                Paper figure generation
```

## License

MIT
