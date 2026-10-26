# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-26T15:54:24Z

## rationale

この提案は、gcmgモデルのフィンガープリント空間において、特にヘビーテールとクルトシスの特性を狙っています。Nを100に設定してエージェント数を減少させることで、エージェント間の相互作用を強化し、またr_min_staticを0.03に設定することで、参加しないエージェントが生まれることで市場の複雑性が増すと考えられます。

## params

```json
{
  "M": 4,
  "N": 100,
  "S": 3,
  "T_total": 3000,
  "T_win": 50,
  "r_min_static": 0.03
}
```

## predicted_fingerprint

```json
{
  "volatility": 45.0,
  "kurtosis": 12.0,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.02,
  "leverage": -0.01,
  "acf_absret_long": 0.03,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `3.8`
