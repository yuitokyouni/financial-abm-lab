# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-23T20:56:00Z

## rationale

このパラメータスイープは、ウェルス・ダイナミクスの特性として、特に長期記憶とボラティリティクラスタリングに関連する領域をターゲットにしています。Nを増加させ、Mを最適化することで、エージェント間の相互作用が強化され、より複雑な市場ダイナミクスを生成します。これにより、ヘビーテールやボラティリティの変動を強調できると考えています。

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
  "kurtosis": 8.5,
  "hill_tail_index": 5.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.1,
  "leverage": 0.01,
  "acf_absret_long": 0.08,
  "acf_absret_decay": 0.005,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.5`
