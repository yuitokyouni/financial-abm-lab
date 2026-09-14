# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-14T15:43:09Z

## rationale

このパラメータスイープは、特に高いボラティリティとクルトシスを持つ領域を目指しています。Nを350に設定することでエージェント数を増やし、より複雑な相互作用を生むことが期待されます。また、Cの増加は戦略の多様性を高め、マーケットインパクトを強調します。

## params

```json
{
  "B": 8,
  "C": 2.5,
  "M": 4,
  "N": 350,
  "S": 3,
  "T": 2200
}
```

## predicted_fingerprint

```json
{
  "volatility": 15.0,
  "kurtosis": 12.5,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.1,
  "acf_absret_mean": 0.05,
  "leverage": 0.02,
  "acf_absret_long": 0.02,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `5.0`
