# proposal #1 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-28T17:34:10Z

## rationale

この提案は、gcmg モデルにおける参加者の選好の強さを高めることを目指しています。r_min_staticを0.03に設定することで、エージェントが参加するためのハードルが下がり、より多くのエージェントが市場に参加することが期待されます。これにより、ボラティリティが増加し、ヘビーテールの特性を強化することができると考えています。

## params

```json
{
  "M": 3,
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
  "volatility": 30.0,
  "kurtosis": 12.0,
  "hill_tail_index": 8.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.05,
  "leverage": 0.01,
  "acf_absret_long": 0.03,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `4.5`
