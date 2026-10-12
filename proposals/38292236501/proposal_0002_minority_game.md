# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-12T18:40:29Z

## rationale

このスイープは、マイノリティゲームのフィンガープリント空間において、エージェントの戦略の複雑さを増加させることを目指しています。Mの値を上げることにより、エージェント間の競争が激化し、ボラティリティや尖度を高める効果が期待されます。この調整により、リターンの特性がより多様化されるでしょう。

## params

```json
{
  "M": 5,
  "N": 100,
  "S": 3,
  "T": 2500
}
```

## predicted_fingerprint

```json
{
  "volatility": 50.0,
  "kurtosis": 15.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.1,
  "acf_absret_mean": 0.15,
  "leverage": 0.04,
  "acf_absret_long": 0.09,
  "acf_absret_decay": 0.03,
  "agg_kurt_decay": 2.5
}
```

- predicted_novelty_distance: `4.3`
