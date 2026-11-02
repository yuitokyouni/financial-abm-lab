# proposal #2 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-02T19:15:23Z

## rationale

このパラメータスイープは、群集行動の強化とボラティリティの増加を目指しています。特に、群集行動を促進するα_wの値を増加させることで、エージェント同士の相互作用が強化され、より高いボラティリティが観察されることが期待されます。

## params

```json
{
  "alpha_w": 2.0,
  "chi": 1.5,
  "n_steps": 2500,
  "noise_scale": 0.01,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 9.0,
  "hill_tail_index": 6.0,
  "acf_ret_l1": 0.04,
  "acf_absret_mean": 0.12,
  "leverage": 0.02,
  "acf_absret_long": 0.03,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `3.8`
