# proposal #1 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-05T18:25:02Z

## rationale

この提案は、意見の異なるエージェントの相互作用による市場ダイナミクスの変化を探求します。n_c_initを適度に増加させることで、群集行動によるボラティリティのクラスタリングを促進し、価格変動の新たなパターンを生み出すことが期待されます。

## params

```json
{
  "n_c_init": 150,
  "n_integer_steps": 2500,
  "steps_per_unit": 75
}
```

## predicted_fingerprint

```json
{
  "volatility": 18.0,
  "kurtosis": 14.0,
  "hill_tail_index": 17.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.04,
  "leverage": 0.03,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.2
}
```

- predicted_novelty_distance: `3.8`
