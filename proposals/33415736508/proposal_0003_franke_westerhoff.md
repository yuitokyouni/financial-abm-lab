# proposal #3 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-31T16:46:27Z

## rationale

この提案は、群集行動とボラティリティの相互作用に焦点を当てています。特に、α_wを高めることにより、富の集中が生じやすくなり、ボラティリティの急激な変動を引き起こすことが期待されます。phiとchiの設定により、エージェント間の影響が強まるため、非対称なリターンが観察されるでしょう。

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
  "volatility": 28.0,
  "kurtosis": 13.0,
  "hill_tail_index": 5.2,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.14,
  "leverage": -0.01,
  "acf_absret_long": 0.06,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `4.4`
