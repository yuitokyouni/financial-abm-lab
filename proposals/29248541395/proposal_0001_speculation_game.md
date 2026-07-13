# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-13T12:07:47Z

## rationale

本スイープでは M=5、C=3.5 と高い記憶長と戦略強度を設定し、投資家の行動の非線形性を強めます。これによりリターンのボラティリティが上昇し、テイル指数が高くなることが期待され、既存のスペキュレーションゲームのファミリー中心から右上方向へ移動します。

## params

```json
{
  "B": 10,
  "C": 3.5,
  "M": 5,
  "N": 350,
  "S": 3,
  "T": 2450
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.015,
  "kurtosis": 1.2,
  "hill_tail_index": 8.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.2,
  "leverage": -0.02,
  "acf_absret_long": 0.1,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `2.5`
