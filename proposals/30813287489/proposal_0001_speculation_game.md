# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-03T12:24:34Z

## rationale

この提案は、特にボラティリティと尖度の高い領域を目指しています。Nを300に設定することで、エージェント数を増やし、より多様な戦略を模倣する機会を増加させます。また、Mを5にすることで、より複雑な行動が発生し、これが結果的にボラティリティと尖度を高めると考えられます。

## params

```json
{
  "B": 8,
  "C": 2.5,
  "M": 5,
  "N": 300,
  "S": 3,
  "T": 2200
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 14.0,
  "hill_tail_index": 18.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.03,
  "leverage": 0.02,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
