# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-12T18:40:29Z

## rationale

このパラメータスイープは、スペキュレーションゲームのフィンガープリント空間において、ボラティリティと尖度を高めることを目指しています。特に、N と M の値を調整することで、エージェント間の相互作用を強化し、より極端なリターンを生成することが期待されます。これにより、ヘビーテールの特性を持つ新しいパターンを探索することができます。

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
  "kurtosis": 8.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.1,
  "leverage": 0.02,
  "acf_absret_long": 0.1,
  "acf_absret_decay": 0.02,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.5`
