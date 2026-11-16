# proposal #4 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-16T19:19:31Z

## rationale

この提案は、特にエージェント間のインタラクションの強化を目指しています。α_wの増加により、富の分配が変化し、群集行動が促進されることで、ボラティリティが増加することが期待されます。過去の文献での富に基づく行動の重要性に根ざしています。

## params

```json
{
  "alpha_w": 1.5,
  "chi": 1.0,
  "n_steps": 2200,
  "noise_scale": 0.012,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 22.0,
  "kurtosis": 9.0,
  "hill_tail_index": 11.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.2,
  "leverage": -0.02,
  "acf_absret_long": 0.08,
  "acf_absret_decay": 0.02,
  "agg_kurt_decay": 1.6
}
```

- predicted_novelty_distance: `4.0`
