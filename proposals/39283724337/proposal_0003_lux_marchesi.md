# proposal #3 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-19T16:16:02Z

## rationale

この提案は、エージェントの初期設定を調整することで、意見の差異を強調し、価格変動のダイナミクスをより複雑にすることを目指しています。特に、初期のエージェントの数を増やすことで、ボラティリティとクルトシスを高めることが期待されます。

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
  "hill_tail_index": 5.5,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.06,
  "leverage": 0.01,
  "acf_absret_long": 0.1,
  "acf_absret_decay": 0.0,
  "agg_kurt_decay": 2.5
}
```

- predicted_novelty_distance: `4.1`
