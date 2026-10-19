# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-19T16:16:02Z

## rationale

この提案は、特にボラティリティとクルトシスの高い領域を目指しています。選択したパラメータ値は、エージェント間の戦略の多様性を増加させ、意図的に市場の変動を強化することで、価格変動の不安定性を高めると考えられます。

## params

```json
{
  "B": 8,
  "C": 3.0,
  "M": 4,
  "N": 300,
  "S": 3,
  "T": 2250
}
```

## predicted_fingerprint

```json
{
  "volatility": 12.0,
  "kurtosis": 10.5,
  "hill_tail_index": 5.5,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.1,
  "leverage": 0.05,
  "acf_absret_long": 0.15,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `3.2`
