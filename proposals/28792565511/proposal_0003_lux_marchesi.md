# proposal #3 — lux_marchesi

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-06T12:48:58Z

## rationale

steps_per_unit を高く設定し、価格変動の時間分解能を上げることで楽観的・悲観的チャーティスト間の切り替えが頻繁になり、負のレバレッジ効果が強まります。また n_c_init を増やすことでチャーティストの基礎人数を拡大し、ボラティリティとクルトシスの上昇を期待します。Lux‑Marchesi の群集転換メカニズムに対する感度実験です。

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
  "volatility": 0.018,
  "kurtosis": 0.6,
  "hill_tail_index": 6.0,
  "acf_ret_l1": -0.02,
  "acf_absret_mean": 0.05,
  "leverage": -0.04,
  "acf_absret_long": 0.08,
  "acf_absret_decay": -0.04,
  "agg_kurt_decay": 0.8
}
```

- predicted_novelty_distance: `2.3`
