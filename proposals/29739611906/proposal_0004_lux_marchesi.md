# proposal #4 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-20T11:47:02Z

## rationale

この提案は、lux_marchesiモデルのフィンガープリント空間において、特にボラティリティとヘビーテールのある領域をターゲットにしています。n_integer_stepsを2500に増やし、初期のエージェント数を100に設定することで、より多くの市場のダイナミクスがシミュレーションされ、実際の市場挙動に近づくことが期待されます。

## params

```json
{
  "n_c_init": 100,
  "n_integer_steps": 2500,
  "steps_per_unit": 75
}
```

## predicted_fingerprint

```json
{
  "volatility": 20.0,
  "kurtosis": 18.0,
  "hill_tail_index": 7.0,
  "acf_ret_l1": 0.15,
  "acf_absret_mean": 0.12,
  "leverage": 0.02,
  "acf_absret_long": 0.04,
  "acf_absret_decay": 0.03,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.8`
