# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-02T19:15:23Z

## rationale

この提案は、エージェントの行動が市場に与える影響を強化することを目指しています。特に、ファンダメンタルとチャーチストの影響を増すことで、価格の変動が顕著になり、ボラティリティが増加することが期待されます。

## params

```json
{
  "alpha_chart": 0.3,
  "alpha_fund": 0.4,
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
  "volatility": 20.0,
  "kurtosis": 7.5,
  "hill_tail_index": 4.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.08,
  "leverage": -0.01,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.008,
  "agg_kurt_decay": 0.6
}
```

- predicted_novelty_distance: `4.2`
