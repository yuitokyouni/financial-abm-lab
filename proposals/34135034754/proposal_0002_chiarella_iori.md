# proposal #2 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-07T14:52:07Z

## rationale

この提案は、ファンダメンタリストとチャーチストの相互作用を強化することを目指しています。特に、ファンダメンタリストの影響力を高めることで、より安定した価格形成が期待でき、ボラティリティが低下することが見込まれます。このような設定は、価格発見のメカニズムをより明確にするための重要なステップです。

## params

```json
{
  "alpha_chart": 0.3,
  "alpha_fund": 0.4,
  "alpha_noise": 0.3,
  "chart_strength": 0.9,
  "fund_speed": 0.05,
  "n_steps": 2500,
  "noise_scale": 0.012
}
```

## predicted_fingerprint

```json
{
  "volatility": 5.0,
  "kurtosis": 4.0,
  "hill_tail_index": 3.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.02,
  "leverage": 0.005,
  "acf_absret_long": 0.02,
  "acf_absret_decay": 0.005,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `4.3`
