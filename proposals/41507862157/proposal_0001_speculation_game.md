# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-02T19:15:23Z

## rationale

この提案は、ボラティリティと尖度の高い領域をターゲットとしています。選択したパラメータにより、エージェントの戦略の多様性が増し、結果として大きな価格変動が促進されると考えられます。これにより、特にボラティリティクラスタリングの特徴が強調されるでしょう。

## params

```json
{
  "B": 10,
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
  "kurtosis": 8.5,
  "hill_tail_index": 5.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.15,
  "leverage": 0.02,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.0`
