# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-07T14:52:07Z

## rationale

この提案は、ボラティリティの高い領域を目指しています。特に、NとMの値を増やすことで、エージェント間の相互作用が強化され、より複雑な価格変動が生成されると考えられます。このアプローチは、エージェントの選択肢を増やし、ダイナミクスを豊かにすることで、新しい市場の特性を探ることができます。

## params

```json
{
  "B": 8,
  "C": 3.5,
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
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.1,
  "leverage": 0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": 0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
