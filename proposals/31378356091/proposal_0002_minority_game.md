# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-10T10:18:05Z

## rationale

このスイープは、価格の急激な変動を引き起こす可能性のある領域を狙っています。特に、Mを5に増やすことで、エージェントの戦略の複雑さが増し、結果としてより大きな変動が期待されます。また、Nを120に設定することで、エージェントの相互作用が増え、価格形成に影響を与えることが見込まれます。

## params

```json
{
  "M": 5,
  "N": 120,
  "S": 3,
  "T": 2500
}
```

## predicted_fingerprint

```json
{
  "volatility": 40.0,
  "kurtosis": 10.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.15,
  "leverage": 0.015,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 0.7
}
```

- predicted_novelty_distance: `5.0`
