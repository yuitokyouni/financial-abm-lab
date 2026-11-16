# proposal #2 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-16T19:19:31Z

## rationale

この提案は、より多様な戦略の選択肢を持つことで、エージェント間の競争が激化し、結果としてボラティリティが増加することを目指しています。特に、Mの増加により、エージェントの行動の多様性が高まり、ヘビーテールの生成が期待できます。

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
  "hill_tail_index": 18.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.15,
  "leverage": 0.01,
  "acf_absret_long": 0.07,
  "acf_absret_decay": 0.04,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.8`
