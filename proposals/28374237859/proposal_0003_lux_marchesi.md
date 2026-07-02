# proposal #3 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-06-29T13:09:13Z

## rationale

チャート派エージェントの初期数を増やし、時間刻みを細かくすることで、楽観・悲観チャート間のスイッチング頻度が上がり、ボラティリティ (volatility ≈ 0.02) とレバレッジ効果 (leverage ≈ -0.005) が強化されます。Lux‑Marchesi の意見伝搬メカニズムを高密度化した実験的拡張です。

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
  "volatility": 0.02,
  "kurtosis": 0.5,
  "hill_tail_index": 6.0,
  "acf_ret_l1": -0.005,
  "acf_absret_mean": 0.05,
  "leverage": -0.005,
  "acf_absret_long": 0.02,
  "acf_absret_decay": -0.015,
  "agg_kurt_decay": 0.3
}
```

- predicted_novelty_distance: `2.5`
