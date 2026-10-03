# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-21T15:43:51Z

## rationale

このパラメータスイープは、特にボラティリティとクルトシスを高めることを目指しています。Nを300、Bを8に設定することで、参加エージェントの数と資本の影響を強調し、マーケットインパクトを増加させることが期待されます。これにより、ヘビーテールの特徴が強調されると考えられます。

## params

```json
{
  "B": 8,
  "C": 2.5,
  "M": 4,
  "N": 300,
  "S": 3,
  "T": 2250
}
```

## predicted_fingerprint

```json
{
  "volatility": 15.0,
  "kurtosis": 10.5,
  "hill_tail_index": 5.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.1,
  "leverage": 0.02,
  "acf_absret_long": 0.08,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `4.5`
