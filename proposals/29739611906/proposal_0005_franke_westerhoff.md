# proposal #5 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-20T11:47:02Z

## rationale

この提案は、franke_westerhoffモデルにおいて、特にリスク回避とボラティリティの高い領域をターゲットにしています。n_stepsを2500に設定し、alpha_wを2.0に増加させることで、エージェントの行動がより非線形になると考えられ、市場の反応が強化される可能性があります。

## params

```json
{
  "alpha_w": 2.0,
  "chi": 1.0,
  "n_steps": 2500,
  "noise_scale": 0.015,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 22.0,
  "kurtosis": 16.0,
  "hill_tail_index": 8.0,
  "acf_ret_l1": 0.1,
  "acf_absret_mean": 0.08,
  "leverage": 0.025,
  "acf_absret_long": 0.02,
  "acf_absret_decay": 0.02,
  "agg_kurt_decay": 1.6
}
```

- predicted_novelty_distance: `4.4`
