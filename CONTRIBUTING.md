# Contributing to PRISM

## Development Setup

```bash
git clone https://github.com/your-org/PRISM.git
cd PRISM
pip install -e ".[dev]"
```

## Code Quality

All contributions must pass:

```bash
# Tests
pytest

# Linting
ruff check src/ tests/

# Type checking
mypy src/prism/
```

## Adding a New Model Adapter

1. Create `src/prism/adapters/xx.py` implementing the `ModelAdapter` protocol from `src/prism/types.py`
2. The adapter must implement: `calibrate_baseline()`, `apply_intervention()`, `simulate()`, `describe_complexity()`
3. Support all three intervention classes: `tick_size_increase`, `tick_size_decrease`, `transaction_tax`
4. Register in `ADAPTER_REGISTRY` in `src/prism/pipeline.py`
5. Export from `src/prism/adapters/__init__.py`
6. Add unit tests in `tests/unit/test_xx_adapter.py` covering:
   - Protocol conformance (`isinstance(adapter, ModelAdapter)`)
   - Each intervention class
   - Seed reproducibility
7. Add integration tests in `tests/integration/test_pipeline.py`

## Adding a New NER

1. Create `data/ner/your_ner_id.yaml` following the schema in existing NER files
2. Include: `ner_id`, `intervention` (class + canonical_params), `venue`, `date_effective`, `assignment`, `ground_truth_delta` with `ci95`, `causal_method`, and `references`
3. Tag unverified deltas with `"external_claim"` in references
4. Add integration tests exercising the new NER against existing adapters

## Adding a New Stylized Fact

1. Add the estimator function in `src/prism/facts/estimators.py`
2. Register in the `FACT_REGISTRY` dict
3. Optionally add a short alias in `src/prism/cli/main.py` `FACT_ALIASES`
4. Add unit tests in `tests/unit/test_facts.py`

## Commit Messages

Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.

## Style

- Line length: 100 characters
- Target: Python 3.11+
- Type hints required (mypy strict)
- No comments unless the "why" is non-obvious
