# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-09T19:32:31Z

## rationale

このスイープは、特にボラティリティと尖度の高い領域を目指しています。パラメータの設定により、取引の活発化とともに市場の反応が強まると期待され、その結果、ボラティリティと尖度が増加します。これにより、既存のモデルとは異なる新しいフィンガープリントが得られるでしょう。

## params

```json
{
  "B": 10,
  "C": 3.0,
  "M": 4,
  "N": 400,
  "S": 3,
  "T": 2400
}
```

## predicted_fingerprint

```json
{
  "volatility": 35.0,
  "kurtosis": 12.0,
  "hill_tail_index": 18.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.2,
  "leverage": 0.02,
  "acf_absret_long": 0.12,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `5.0`
