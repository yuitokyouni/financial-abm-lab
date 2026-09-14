# proposal #5 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-14T15:43:09Z

## rationale

このスイープは、ファンダメンタリストとチャーチストの相互作用を強化し、ボラティリティの非対称性を生むことを目指しています。alpha_fundとalpha_chartを高めることで、価格形成における感応度が向上し、よりダイナミックな市場を再現することが期待されます。

## params

```json
{
  "alpha_chart": 0.4,
  "alpha_fund": 0.5,
  "alpha_noise": 0.2,
  "chart_strength": 0.8,
  "fund_speed": 0.05,
  "n_steps": 2800,
  "noise_scale": 0.015
}
```

## predicted_fingerprint

```json
{
  "volatility": 22.0,
  "kurtosis": 16.0,
  "hill_tail_index": 11.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.02,
  "leverage": 0.015,
  "acf_absret_long": 0.008,
  "acf_absret_decay": -0.005,
  "agg_kurt_decay": 1.9
}
```

- predicted_novelty_distance: `5.2`
