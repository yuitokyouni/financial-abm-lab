# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-24T09:48:30Z

## rationale

このパラメータスイープは、ヘビーテール特性を持つ可能性のある領域に向かっています。特に、Mを4に設定することで、価格の変動がより複雑になり、群集行動が強化されます。文献はありませんが、過去の研究で示された群集行動の影響を考慮しています。

## params

```json
{
  "B": 8,
  "C": 3.0,
  "M": 4,
  "N": 250,
  "S": 2,
  "T": 2200
}
```

## predicted_fingerprint

```json
{
  "volatility": 15.0,
  "kurtosis": 5.2,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.02,
  "leverage": -0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
