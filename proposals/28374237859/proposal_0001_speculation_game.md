# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-06-29T13:09:13Z

## rationale

このスイープはCパラメータを高め、戦略テーブルの深さを増やすことで、長期的な自己相関 (acf_absret_long > 0.1) を強化し、リターンのテイル指数 (hill_tail_index ≈ 8) を上昇させることを狙います。特に、過去のリターン履歴が長くなるとエージェントの行動が集団的に同期しやすくなるという点は、Chiarella と Iori の取引戦略連鎖に類似しています。

## params

```json
{
  "B": 10,
  "C": 3.5,
  "M": 4,
  "N": 350,
  "S": 3,
  "T": 2400
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.045,
  "kurtosis": 0.8,
  "hill_tail_index": 8.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.2,
  "leverage": -0.02,
  "acf_absret_long": 0.1,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `3.5`
