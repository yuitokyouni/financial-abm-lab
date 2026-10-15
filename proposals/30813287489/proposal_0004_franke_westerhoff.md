# proposal #4 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-03T12:24:34Z

## rationale

この提案は、特に不均質信念が市場に与える影響を探求します。chiを1.5に設定することで、群集行動を強調し、特にボラティリティのクラスタリングを引き起こすことを目指しています。また、alpha_wを1.5にすることで、富の影響を強調し、エージェントの行動に更なるダイナミクスをもたらします。

## params

```json
{
  "alpha_w": 1.5,
  "chi": 1.5,
  "n_steps": 2200,
  "noise_scale": 0.01,
  "phi": 0.1
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 11.0,
  "hill_tail_index": 19.0,
  "acf_ret_l1": 0.008,
  "acf_absret_mean": 0.02,
  "leverage": 0.02,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.015,
  "agg_kurt_decay": 1.7
}
```

- predicted_novelty_distance: `4.6`
