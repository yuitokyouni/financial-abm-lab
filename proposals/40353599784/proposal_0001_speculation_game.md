# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-26T15:54:24Z

## rationale

この提案は、speculation_game のフィンガープリント空間で、特にボラティリティとクルトシスの領域をターゲットにしています。Nを300に設定し、Sを3にすることでエージェントの多様性を高め、価格変動のダイナミクスを強化します。また、Bを8にすることで、エージェント間の競争が促進され、結果としてより複雑な市場行動が期待されます。

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
  "kurtosis": 8.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.1,
  "acf_absret_mean": 0.15,
  "leverage": 0.02,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.05,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
