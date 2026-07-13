# proposal #3 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-13T12:07:47Z

## rationale

lux_marchesi では初期チャーティスト数 n_c_init を 150 に設定し、チャート参加者が支配的になる状況を作ります。これによりボラティリティクラスターが強化され、acf_absret_long が正の大きな値を示すはずです。結果として既存のセンターから上方向へシフトします。

## params

```json
{
  "n_c_init": 150,
  "n_integer_steps": 2800,
  "steps_per_unit": 90
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.012,
  "kurtosis": 0.8,
  "hill_tail_index": 6.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.25,
  "leverage": -0.015,
  "acf_absret_long": 0.2,
  "acf_absret_decay": -0.04,
  "agg_kurt_decay": 0.9
}
```

- predicted_novelty_distance: `2.8`
