# Adapter Smuggling Audit — Phase C

## What is Answer Smuggling?

Answer smuggling occurs when an adapter's `apply_intervention()` modifies behavioral
parameters (β, herd_strength, chi, noise_scale, alpha_noise, etc.) in addition to
the structural constraint (tick_size, transaction_cost). This encodes the expected
outcome into the model parameters, making sign-match results meaningless — the model
produces the "right answer" because the code told it to, not because the behavioral
mechanisms generated it emergently.

## Allowed Interventions (Structural Constraints Only)

| Intervention Class | Allowed Structural Change |
|-------------------|---------------------------|
| tick_size_increase/decrease | `tick_size` = new tick value |
| transaction_tax | `transaction_cost` = tax rate |

Everything else (behavioral parameters) must remain unchanged across interventions.

## Pre-Fix Smuggling Inventory

### SG Adapter (sg.py)
- **tick_size_increase**: `beta = beta / √(tick_ratio)` — SMUGGLED
- **tick_size_decrease**: `beta = beta * √(tick_ratio)` — SMUGGLED
- **transaction_tax**: `noise_scale *= 1 - tax_rate * 10` — SMUGGLED

### CI Adapter (ci.py)
- **tick_size_increase**: `spread_ticks = int(spread_ticks / tick_ratio)`, `price_impact *= √(tick_ratio)` — SMUGGLED
- **tick_size_decrease**: `spread_ticks = int(spread_ticks * tick_ratio)`, `price_impact /= √(tick_ratio)` — SMUGGLED
- **transaction_tax**: `noise_scale *= 1 + tax_rate * 5`, `alpha_noise *= 1 - tax_rate * 3` (+ renormalization) — SMUGGLED

### LM Adapter (lm.py)
- **tick_size_increase**: `herd_strength /= √(tick_ratio)`, `opinion_decay *= 1 + 0.1·ln(tick_ratio)` — SMUGGLED
- **tick_size_decrease**: `herd_strength *= √(tick_ratio)`, `opinion_decay *= max(0.01, 1 - 0.1·ln(tick_ratio))` — SMUGGLED
- **transaction_tax**: `chart_trend_weight *= 1 - tax_rate * 8`, `noise_scale *= 1 + tax_rate * 3` — SMUGGLED

### FW Adapter (fw.py)
- **tick_size_increase**: `chi /= √(tick_ratio)`, `alpha_w /= 1 + 0.1·ln(tick_ratio)` — SMUGGLED
- **tick_size_decrease**: `chi *= √(tick_ratio)`, `alpha_w *= 1 + 0.1·ln(tick_ratio)` — SMUGGLED
- **transaction_tax**: `chi *= 1 - tax_rate * 8`, `sigma_c *= 1 + tax_rate * 5` — SMUGGLED

### ZI-C Adapter (zi.py)
- **tick interventions**: `tick_size` only — CLEAN
- **transaction_tax**: `tick_size = max(tick, tax·fundamental_value)` — CLEAN (structural)

## Post-Fix Results (JPX 2014, structural-only intervention)

| Adapter | Sign Matches (6 facts) | vs ZI-C Baseline (3/6) | Discriminating Power |
|---------|----------------------|------------------------|---------------------|
| ZI-C | 3/6 | — | Baseline (null model) |
| SG | **5/6** | **+2** | YES — behavioral mechanisms add value |
| FW | **5/6** | **+2** | YES — behavioral mechanisms add value |
| LM | 3/6 | 0 | NO — ties the null model |
| CI | 2/6 | -1 | NO — worse than null model |

## Detailed Sign Comparison

| Fact | DiD | ZI-C | SG | CI | LM | FW |
|------|-----|------|----|----|----|----|
| volatility_clustering | - | + ✗ | - ✓ | + ✗ | + ✗ | - ✓ |
| leverage_effect | - | - ✓ | + ✗ | - ✓ | - ✓ | - ✓ |
| gain_loss_asymmetry | + | - ✗ | + ✓ | + ✓ | + ✓ | - ✗ |
| fat_tails | + | - ✗ | + ✓ | - ✗ | + ✓ | + ✓ |
| abs_autocorrelation | + | + ✓ | + ✓ | - ✗ | - ✗ | + ✓ |
| squared_return_acf | + | + ✓ | + ✓ | - ✗ | - ✗ | + ✓ |

## Interpretation

After removing smuggling, **SG and FW retain genuine discriminating power** — their
behavioral mechanisms (strategy switching in SG, sentiment-driven switching in FW)
produce emergent responses to structural tick_size changes that match empirical
direction better than random noise.

**CI and LM show no discriminating power** — CI (order book with heterogeneous agents)
performs worse than the null, and LM (herding dynamics) merely ties it. This doesn't
mean these models are useless, but their behavioral mechanisms don't generate
meaningful responses to tick_size interventions when no parameter guidance is provided.

**Important caveat:** This is tested on only one NER (JPX 2014 tick_size_decrease).
Different intervention types (tick_size_increase, transaction_tax) or different market
conditions may yield different results. The current conclusion applies narrowly to
this specific empirically-grounded comparison.
