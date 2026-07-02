# proposal #4 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-06-29T13:09:13Z

## rationale

r_min_static を高め、エージェントの参加ハードルを上げることで出席数が減少し、出席過剰 (attendance_excess) の変動が拡大します。その結果、ボラティリティが 30 程度に達し、ヒルテイル指数が上限の 20 に飽和するという、priceless モデル特有の極端な分布を探索します。

## params

```json
{
  "M": 4,
  "N": 130,
  "S": 3,
  "T_total": 3500,
  "T_win": 60,
  "r_min_static": 0.045
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 15.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.0,
  "acf_absret_mean": 0.01,
  "leverage": 0.0,
  "acf_absret_long": 0.0,
  "acf_absret_decay": 0.0,
  "agg_kurt_decay": 0.0
}
```

- predicted_novelty_distance: `5.0`
