# proposal #5 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-03T12:24:34Z

## rationale

この提案は、特にボラティリティとヘビーテールの特性を強調することを目指しています。n_integer_stepsを2800に設定することで、シミュレーションの期間を延長し、より多くの価格変動を観察することが可能になります。また、n_c_initを150にすることで、初期条件が市場の動きに与える影響を高めることを期待しています。

## params

```json
{
  "n_c_init": 150,
  "n_integer_steps": 2800,
  "steps_per_unit": 70
}
```

## predicted_fingerprint

```json
{
  "volatility": 40.0,
  "kurtosis": 15.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.005,
  "acf_absret_mean": 0.02,
  "leverage": 0.04,
  "acf_absret_long": 0.06,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.4`
