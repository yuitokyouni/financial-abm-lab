# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-17T09:42:25Z

## rationale

このパラメータスイープは、特にボラティリティを高めることを目指しています。Nを300に設定することで、エージェントの数を増やし、より多様な戦略の相互作用を促進します。また、Cを2.5に増加させることで戦略の選択肢を広げ、より高いボラティリティを期待できます。

## params

```json
{
  "B": 8,
  "C": 2.5,
  "M": 4,
  "N": 300,
  "S": 3,
  "T": 2400
}
```

## predicted_fingerprint

```json
{
  "volatility": 15.0,
  "kurtosis": 5.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.1,
  "leverage": 0.015,
  "acf_absret_long": 0.1,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `3.5`
