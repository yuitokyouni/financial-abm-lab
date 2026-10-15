# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-31T16:46:27Z

## rationale

この提案は、特に高いボラティリティとカートシスを持つ領域をターゲットとしています。Nを増やすことでエージェントの多様性を高め、強い価格変動を促進します。また、Cを高めることにより、エージェント間の相互作用が強まり、ボラティリティの急上昇を引き起こすことが期待されます。

## params

```json
{
  "B": 8,
  "C": 3.0,
  "M": 4,
  "N": 300,
  "S": 3,
  "T": 2200
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 12.0,
  "hill_tail_index": 5.5,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.15,
  "leverage": -0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `4.5`
