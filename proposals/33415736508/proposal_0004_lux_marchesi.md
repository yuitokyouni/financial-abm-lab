# proposal #4 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-31T16:46:27Z

## rationale

この提案では、楽観的なチャーチストと悲観的なチャーチスト間の相互作用を強調します。n_c_initを高く設定することで、エージェントの意見の多様性を高め、価格変動が大きくなることが期待されます。また、steps_per_unitを適切に調整することで、価格遷移の頻度を増し、ボラティリティを促進します。

## params

```json
{
  "n_c_init": 150,
  "n_integer_steps": 2800,
  "steps_per_unit": 75
}
```

## predicted_fingerprint

```json
{
  "volatility": 32.0,
  "kurtosis": 16.0,
  "hill_tail_index": 5.9,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.11,
  "leverage": -0.02,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.3
}
```

- predicted_novelty_distance: `4.2`
