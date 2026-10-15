# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-20T11:47:02Z

## rationale

この提案は、speculation_game のフィンガープリント空間の中で、特にボラティリティと尖度の高い領域を狙っています。Nを300に増加させ、Mを4に設定することで、エージェントの戦略の多様性が増し、より複雑な相互作用を生成することが期待されます。この組み合わせは、特に市場の異常な動きを捉える能力を向上させる可能性があります。

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
  "volatility": 25.0,
  "kurtosis": 12.0,
  "hill_tail_index": 5.0,
  "acf_ret_l1": 0.1,
  "acf_absret_mean": 0.1,
  "leverage": 0.02,
  "acf_absret_long": 0.02,
  "acf_absret_decay": 0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
