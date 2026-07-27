# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-27T12:25:24Z

## rationale

この提案は、特にボラティリティと尖度が高い領域を目指しています。Nを増加させ、Mを4に設定することで、より多くの戦略の相互作用を促進し、ボラティリティを高めることが期待されます。これにより、リターンの分布においてヘビーテールが生成される可能性が高まります。

## params

```json
{
  "B": 8,
  "C": 2.5,
  "M": 4,
  "N": 300,
  "S": 3,
  "T": 2200
}
```

## predicted_fingerprint

```json
{
  "volatility": 15.0,
  "kurtosis": 10.5,
  "hill_tail_index": 18.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.01,
  "leverage": -0.01,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
