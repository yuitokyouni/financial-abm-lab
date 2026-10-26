# proposal #4 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-26T15:54:24Z

## rationale

この提案は、lux_marchesiモデルのフィンガープリント空間で、特にヘビーテールとクルトシスの特性をターゲットにしています。n_integer_stepsを2800に設定することで、エージェントの意思決定がより長期的な視点で行われることが期待され、市場の動的な特性が強化されます。また、n_c_initを180にすることで、初期のエージェントの多様性を増やし、複雑な市場行動が観察されることを目指します。

## params

```json
{
  "n_c_init": 180,
  "n_integer_steps": 2800,
  "steps_per_unit": 75
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 10.0,
  "hill_tail_index": 16.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.08,
  "leverage": 0.01,
  "acf_absret_long": 0.02,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 1.2
}
```

- predicted_novelty_distance: `4.3`
