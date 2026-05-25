# Getting Started with PRISM

This tutorial walks through PRISM's core workflow: loading a natural experiment, running a model adapter through it, and interpreting the results.

## Prerequisites

```bash
pip install -e ".[dev]"
```

## Concept: The Phase-Diagram Tensor

PRISM evaluates ABMs by measuring how they respond to known structural interventions. The output is a 3-dimensional tensor:

- **Dimension 1: Mechanism family** — which ABM (SG, CI, ZI, LM, FW)
- **Dimension 2: Intervention class** — what changed in the market (tick size, transaction tax)
- **Dimension 3: Stylized fact** — what property is measured (volatility clustering, leverage effect, etc.)

Each cell contains a match score: does the model's predicted change agree with what happened in the real market?

## Step 1: Run a Single Cell

The simplest PRISM evaluation is a single cell — one adapter, one NER, one or more facts:

```bash
prism run \
  --adapter sg \
  --ner tspp_2016_us_equity \
  --facts volclust,leverage \
  --seed 42 --n-paths 20
```

This runs the Speculation Game (SG) adapter against the SEC Tick Size Pilot Program NER and computes two stylized facts. Output includes:

- **Eligibility check**: Does the model produce realistic baseline behavior?
- **Sign consistency**: Does the model's delta match the empirical delta's direction?
- **Magnitude check**: Does the model's delta fall within the empirical 95% CI?
- **MDL-weighted confidence**: Adjusted for model complexity
- **Provenance ID**: Unique run identifier for reproducibility

## Step 2: Run the Full Tensor

To compare all adapters across all NERs:

```bash
prism tensor \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu,mifid2_2018_eu_tick,jpx_2014_jp_tick \
  --facts volclust,leverage,gainloss,fattails,absacf,sqacf \
  --seed 42 --n-paths 20 \
  --output results.json
```

The tensor output shows a divergence analysis — cases where adapters disagree on the sign of a fact change. These divergences are the "prism effect": the intervention separates models that look identical under static calibration.

## Step 3: Visualize Results

### Heatmap

```bash
prism heatmap \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu \
  --facts volclust,leverage,gainloss \
  --output heatmap.png
```

Green cells = sign match, red = mismatch, gray = inconclusive, hatched = ineligible.

### Publication-quality LaTeX output

```bash
# PDF/PGF heatmap (Computer Modern fonts, math labels)
prism latex-heatmap \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu \
  --facts volclust,leverage,gainloss \
  --output fig1.pdf

# LaTeX table with booktabs style
prism latex-table \
  --adapters sg,ci,zi,lm,fw \
  --ners tspp_2016_us_equity,french_ftt_2012_eu \
  --facts volclust,leverage,gainloss \
  --output table1.tex
```

## Step 4: Using the Python API

For scripting and integration:

```python
from prism.pipeline import run_cell, run_tensor
from prism.viz import render_heatmap

# Run one cell
cell = run_cell(
    adapter_name="ci",
    ner_path="data/ner/french_ftt_2012_eu.yaml",
    fact_ids=["volatility_clustering", "leverage_effect"],
    seed=42,
    n_paths=20,
)

# Inspect results
print(cell.summary())
print(f"Eligibility: {cell.eligibility.verdict.value}")

for match in cell.weighted_matches:
    print(f"  {match.fact_id}: sign={match.sign_match.value}, "
          f"confidence={match.confidence_weighted:.3f}")

# Access provenance
print(f"Run ID: {cell.provenance['run_id']}")
```

### Per-Path Fact Estimation

By default, PRISM averages returns across simulation paths before computing facts. This can destroy higher-order distributional properties (kurtosis, skewness). Use `per_path_facts=True` to compute facts on each path individually and take the median:

```python
cell = run_cell(
    adapter_name="sg",
    ner_path="data/ner/tspp_2016_us_equity.yaml",
    fact_ids=["fat_tails", "gain_loss_asymmetry"],
    seed=42, n_paths=50,
    per_path_facts=True,
)
```

### Real Market Data Calibration

Instead of synthetic calibration data, use real equity returns via yfinance:

```python
cell = run_cell(
    adapter_name="sg",
    ner_path="data/ner/tspp_2016_us_equity.yaml",
    fact_ids=["volatility_clustering"],
    seed=42, n_paths=20,
    use_real_data=True,  # requires yfinance + internet
)
```

## Step 5: Compare Causal Methods

The same empirical delta can be identified by different causal methods (RCT, DiD, IV, OLS, etc.). PRISM weights results by the strength of causal identification:

```bash
prism compare \
  --adapter sg \
  --ner tspp_2016_us_equity \
  --facts volclust,leverage \
  --seed 42
```

This shows how the confidence score changes across causal methods — RCT (weight 1.0) gives the highest confidence, OLS (weight 0.5) the lowest.

## Step 6: Adding Your Own Model

Implement the `ModelAdapter` protocol:

```python
from prism.types import (
    CalibrationArtifact, CanonicalIntervention, ComplexitySpec,
    MarketData, SimulatedMarketData,
)

class MyABM:
    def calibrate_baseline(self, pre_data, ais_context):
        # Fit model parameters to pre-intervention data
        return CalibrationArtifact(
            model_id="my_abm",
            calibrated_params={"param1": 0.5},
            pre_data_hash=pre_data.content_hash(),
            seed=0,
        )

    def apply_intervention(self, calib, intervention):
        # Return a new adapter instance with modified parameters
        modified = MyABM()
        if intervention.intervention_class == "tick_size_increase":
            modified._tick_scale = 5.0
        return modified

    def simulate(self, seed, n_paths):
        import numpy as np
        rng = np.random.default_rng(seed)
        returns = rng.normal(0, 0.02, (500, 1))
        return SimulatedMarketData(
            returns=returns, seed=seed, n_paths=n_paths, model_id="my_abm",
        )

    def describe_complexity(self):
        return ComplexitySpec(
            n_free_params=3,
            structural_description="Simple demonstration model",
        )
```

Register it in `src/prism/pipeline.py` and run:

```python
from prism.pipeline import ADAPTER_REGISTRY, run_cell
ADAPTER_REGISTRY["my"] = MyABM

result = run_cell("my", "data/ner/tspp_2016_us_equity.yaml",
                  ["volatility_clustering"], seed=42)
print(result.summary())
```

## Key Concepts

### Natural Experiment Record (NER)

A YAML file that encodes a real-world market structural change with known ground truth. Each NER contains:
- The intervention type and parameters (what changed)
- Ground truth deltas with 95% CIs (what happened to stylized facts)
- Causal identification method and assumptions
- Literature references

### ModelAdapter Protocol

The contract that any ABM must satisfy to be evaluated by PRISM:
1. `calibrate_baseline()` — fit to pre-intervention data
2. `apply_intervention()` — modify parameters to reflect the structural change
3. `simulate()` — generate market returns
4. `describe_complexity()` — report free parameter count for MDL weighting

### Provenance

Every PRISM run is sealed with W3C PROV-O compatible provenance including:
- RNG seeds for bit-exact reproducibility
- Data content hashes (SHA-256)
- Git commit of the codebase
- Estimator versions
- All parameter settings
