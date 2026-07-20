# proposal #3 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-20T11:47:02Z

## rationale

この提案は、minority_game のフィンガープリント空間の中で、特にヘビーテールが観察される領域を狙っています。Nを100に設定し、Mを5に増やすことで、エージェントの戦略の多様性を向上させ、より複雑な相互作用を生成することを目指します。この組み合わせは、特に市場の急激な変動を捉える能力の向上に寄与するでしょう。

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
  "volatility": 50.0,
  "kurtosis": 20.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.2,
  "acf_absret_mean": 0.1,
  "leverage": 0.03,
  "acf_absret_long": 0.03,
  "acf_absret_decay": 0.05,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `5.0`
