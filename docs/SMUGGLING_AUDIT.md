# Adapter Smuggling Audit — Phase C

## What is Answer Smuggling?

Answer smuggling occurs when an adapter's `apply_intervention()` modifies behavioral
parameters (beta, herd_strength, etc.) alongside structural constraints (tick_size),
causing the model to produce the "right" answer by parameter tuning rather than
emergent simulation dynamics.

## Permitted Interventions (Structural Only)

- **tick_size**: Price grid quantization width, applied as ratio: `new = baseline * (tick_to / tick_from)`
- **transaction_cost/tax**: Round-trip cost item

## Adapter-by-Adapter Results

### ZI-C (`zi.py`) — CLEAN

Structural-only by design. No behavioral parameters exist.
- tick_size_decrease: `tick_size *= tick_to/tick_from`
- transaction_tax: `tick_size = max(tick_size, tax_rate * fundamental_value)`

### SG (`sg.py`) — CLEAN

Behavioral parameters explicitly preserved:
- tick_size_decrease: `tick_size *= tick_to/tick_from`
- transaction_tax: `tick_size = max(tick_size, tax_rate * fundamental_value)`
- UNCHANGED: beta, memory, fundamentalist_speed, chartist_lag, chartist_strength, noise_scale, price_impact

### FW (`fw.py`) — CLEAN

- tick_size_decrease: `tick_size *= tick_to/tick_from`
- transaction_tax: `transaction_cost = tax_rate`
- UNCHANGED: phi, chi, alpha_w, alpha_o, alpha_p, sigma_f, sigma_c, noise_scale, price_impact

### CI (`ci.py`) — CLEAN

- tick_size_decrease: `tick_size *= tick_to/tick_from`
- transaction_tax: `transaction_cost = tax_rate`
- UNCHANGED: alpha_fund, alpha_chart, alpha_noise, fund_speed, fund_confidence, chart_lag, chart_strength, noise_scale, spread_ticks, order_depth, price_impact

### LM (`lm.py`) — CLEAN (with note)

- tick_size_decrease: `tick_size *= tick_to/tick_from`
- transaction_tax: `transaction_cost = tax_rate`
- UNCHANGED: n_fund, n_chart, fund_speed, herd_strength, opinion_decay, chart_trend_weight, chart_lookback, noise_scale, price_impact

**Note (MODERATE-1):** LM has an indirect tick_size coupling through trend calculation.
`opinion_pressure = herd_strength * opinion + chart_trend_weight * trend * 100` amplifies
tick discretization effects. This is NOT smuggling (it is a legitimate simulation effect),
but the `* 100` multiplier makes this channel disproportionately strong.

## ZI-C Baseline Comparison

ZI-C (structural-only, no behavioral dynamics) vs SG across 5 seeds, 20 paths each:

| Fact | ZI-C delta (mean +/- std) | SG delta (mean +/- std) |
|------|--------------------------|------------------------|
| volatility_clustering | -0.017 +/- 0.070 | -0.022 +/- 0.030 |
| leverage_effect | +0.000 +/- 0.000 | +0.000 +/- 0.000 |
| gain_loss_asymmetry | -0.000 +/- 0.000 | -0.000 +/- 0.000 |
| fat_tails | +0.001 +/- 0.002 | +0.000 +/- 0.001 |
| abs_autocorrelation | -0.000 +/- 0.000 | +0.000 +/- 0.000 |
| squared_return_acf | -0.000 +/- 0.000 | -0.000 +/- 0.000 |

Both models produce near-zero deltas. The tick_size intervention (0.01 to 0.001)
is effectively a no-op for return-distribution facts at these model scales. SG has
no discriminating power over ZI-C.

## Verdict

All 5 adapters are CLEAN — no answer smuggling remains. The lack of discriminating
power is a genuine scientific result: tick discretization does not produce detectable
effects on return-distribution stylized facts in these ABMs at the scales used.
