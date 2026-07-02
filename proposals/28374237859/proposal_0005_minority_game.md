# proposal #5 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-06-29T13:09:13Z

## rationale

M を 6、S を 4 に設定し、戦略空間を広げることで α=2^M/N が臨界付近に近づき、出席過剰のフラクタル構造が顕在化します。これによりボラティリティが約 25、ヒルテイル指数が上限 20 に達し、priceless 系列の未踏領域を埋めることが期待されます。

## params

```json
{
  "M": 6,
  "N": 120,
  "S": 4,
  "T": 2800
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 12.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.0,
  "acf_absret_mean": 0.0,
  "leverage": 0.0,
  "acf_absret_long": 0.0,
  "acf_absret_decay": 0.0,
  "agg_kurt_decay": 0.0
}
```

- predicted_novelty_distance: `4.5`
