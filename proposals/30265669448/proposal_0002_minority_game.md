# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-27T12:25:24Z

## rationale

この提案は、エージェント数を増やし、戦略の数を6に増加させることで、より複雑な相互作用を実現し、特にリターンの非対称性を強化することを目指しています。これにより、損失回避や群集行動の影響が顕著になると考えられます。

## params

```json
{
  "M": 6,
  "N": 100,
  "S": 3,
  "T": 2500
}
```

## predicted_fingerprint

```json
{
  "volatility": 35.0,
  "kurtosis": 12.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.02,
  "leverage": -0.02,
  "acf_absret_long": 0.0,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.8`
