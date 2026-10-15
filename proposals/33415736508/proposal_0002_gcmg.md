# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-31T16:46:27Z

## rationale

この提案では、出現するクラスターのサイズが大きくなることで、ヘビーテールのリターンを強調します。特に、Nを100に設定し、T_totalを長くすることで、エージェントの相互作用が増え、エージェントの決定が市場に対する影響を強化します。これにより、独自の価格挙動が生成されることが期待されます。

## params

```json
{
  "M": 4,
  "N": 100,
  "S": 3,
  "T_total": 3500,
  "T_win": 50,
  "r_min_static": 0.03
}
```

## predicted_fingerprint

```json
{
  "volatility": 35.0,
  "kurtosis": 15.0,
  "hill_tail_index": 6.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.1,
  "leverage": -0.02,
  "acf_absret_long": 0.04,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.3`
