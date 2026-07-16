# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-06T12:48:58Z

## rationale

このスイープは、量子化されたリターン履歴と高い戦略予算 B が長期自己相関 (acf_absret_long) を強め、ボラティリティとテイル指数を上昇させることを狙います。B と C を大きくすることでエージェントの戦略切り替えが頻繁になり、リターンのクラスタリングが顕在化します。Speculation Game の内部メカニズムに基づく拡張で、実証的に長期記憶領域を探索します。

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
  "volatility": 0.015,
  "kurtosis": 0.5,
  "hill_tail_index": 8.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.2,
  "leverage": -0.02,
  "acf_absret_long": 0.12,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.2
}
```

- predicted_novelty_distance: `2.8`
