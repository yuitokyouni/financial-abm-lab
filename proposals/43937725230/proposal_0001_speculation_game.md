# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-16T19:19:31Z

## rationale

この提案は、特にボラティリティと尖度の分布が高い領域を目指しています。Nを増やし、強度の高い戦略を持つエージェントを増加させることで、相互作用のダイナミクスが複雑化し、価格変動が大きくなると考えられます。これにより、ヘビーテールやボラティリティクラスタリングの現象が強調されるでしょう。

## params

```json
{
  "B": 8,
  "C": 3.2,
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
  "kurtosis": 8.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.2,
  "leverage": 0.02,
  "acf_absret_long": 0.1,
  "acf_absret_decay": 0.03,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `5.0`
