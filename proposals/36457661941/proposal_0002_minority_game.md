# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-28T17:34:10Z

## rationale

このスイープは、minority_game モデルの戦略の多様性を高めることに焦点を当てています。Mを6に増やすことで、エージェント間の戦略の異質性が高まり、ヘビーテールやボラティリティの変化に対する反応が強化されると予想されます。これにより、未探索の領域に到達できる可能性があります。

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
  "volatility": 40.0,
  "kurtosis": 15.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.07,
  "leverage": 0.03,
  "acf_absret_long": 0.04,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.8`
