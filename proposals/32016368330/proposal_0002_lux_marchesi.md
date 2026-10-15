# proposal #2 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-17T09:42:25Z

## rationale

このスイープは、特に市場のボラティリティのクラスタリングに焦点を当てています。n_integer_stepsを2500に増やすことで、モデルの安定性を高め、ボラティリティの変動をより明確に捉えることが可能となります。また、n_c_initを150に設定することで、エージェント間の相互作用を強化し、価格の変動性を増加させます。

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
  "volatility": 12.0,
  "kurtosis": 6.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.08,
  "leverage": 0.01,
  "acf_absret_long": 0.06,
  "acf_absret_decay": -0.015,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `3.0`
