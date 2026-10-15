# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-10T10:18:05Z

## rationale

このスイープは、特にボラティリティが高い領域を狙っています。alpha_fundを0.4に設定することで、ファンダメンタルズに基づく取引の影響を強め、価格変動を促進します。また、chart_strengthを0.8にすることで、チャーチストの影響が増し、価格の短期的な動きが強化されると考えられます。

## params

```json
{
  "alpha_chart": 0.3,
  "alpha_fund": 0.4,
  "alpha_noise": 0.2,
  "chart_strength": 0.8,
  "fund_speed": 0.05,
  "n_steps": 2500,
  "noise_scale": 0.015
}
```

## predicted_fingerprint

```json
{
  "volatility": 35.0,
  "kurtosis": 6.0,
  "hill_tail_index": 16.0,
  "acf_ret_l1": 0.015,
  "acf_absret_mean": 0.1,
  "leverage": 0.025,
  "acf_absret_long": 0.008,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.9
}
```

- predicted_novelty_distance: `4.8`
