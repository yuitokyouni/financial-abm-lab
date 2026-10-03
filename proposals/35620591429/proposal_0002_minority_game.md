# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-21T15:43:51Z

## rationale

このパラメータスイープは、特に長期記憶とヘビーテールの特徴を狙っています。Nを100、Mを5に設定することで、エージェントの選択肢を広げ、より多様な戦略が生まれることが期待されます。これにより、クルトシスが高まる可能性があります。

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
  "volatility": 30.0,
  "kurtosis": 14.0,
  "hill_tail_index": 7.0,
  "acf_ret_l1": 0.06,
  "acf_absret_mean": 0.11,
  "leverage": 0.01,
  "acf_absret_long": 0.12,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 0.8
}
```

- predicted_novelty_distance: `4.3`
