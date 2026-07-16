# proposal #4 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-06T12:48:58Z

## rationale

ファンダメンタル派とチャーティスト派の影響度をともに高め、特に chart_strength を 1.0 に上げることでトレンド追随が強化され、リターンの自己相関とクルトシスが増大します。alpha_noise を低く抑えることでノイズの拡散を抑制し、ボラティリティが顕著に上がります。Chiarella‑Iori の三層トレーダー構造を強化したパラメータ設定です。

## params

```json
{
  "alpha_chart": 0.45,
  "alpha_fund": 0.55,
  "alpha_noise": 0.12,
  "chart_strength": 1.0,
  "fund_speed": 0.09,
  "n_steps": 2500,
  "noise_scale": 0.015
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.02,
  "kurtosis": 0.8,
  "hill_tail_index": 7.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.15,
  "leverage": -0.015,
  "acf_absret_long": 0.1,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `2.6`
