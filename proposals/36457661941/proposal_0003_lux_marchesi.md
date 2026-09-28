# proposal #3 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-28T17:34:10Z

## rationale

この提案は、lux_marchesi モデルの動的な意見形成プロセスを強化することを目指しています。n_c_initを100に設定することで、初期の楽観的および悲観的なチャーチストの数を増やし、価格変動のダイナミクスが複雑化し、ヘビーテールの特性が顕著になると期待されます。

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
  "volatility": 25.0,
  "kurtosis": 11.0,
  "hill_tail_index": 7.0,
  "acf_ret_l1": 0.04,
  "acf_absret_mean": 0.08,
  "leverage": 0.02,
  "acf_absret_long": 0.03,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.6`
