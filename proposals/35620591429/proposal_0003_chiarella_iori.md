# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-21T15:43:51Z

## rationale

この提案は、特にボラティリティとレバレッジの強度を調整することを目指しています。ファンダメンタルストレーダーの影響を強化するため、alpha_fundを0.4に設定し、チャーチストの強度を高めることにより、より多様な市場の反応が期待されます。

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
  "volatility": 12.0,
  "kurtosis": 8.0,
  "hill_tail_index": 5.5,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.07,
  "leverage": 0.02,
  "acf_absret_long": 0.09,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.6
}
```

- predicted_novelty_distance: `4.6`
