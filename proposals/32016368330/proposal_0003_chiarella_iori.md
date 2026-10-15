# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-17T09:42:25Z

## rationale

この提案では、特に市場の動的な変動に対応することを重視しています。alpha_fundを0.4に設定することで、ファンダメンタリストが市場に与える影響を強化し、ボラティリティを高めます。また、chart_strengthを0.8にすることで、チャーチストが過去のトレンドをより強く反映し、価格変動を促進します。

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
  "volatility": 20.0,
  "kurtosis": 7.5,
  "hill_tail_index": 18.0,
  "acf_ret_l1": 0.04,
  "acf_absret_mean": 0.09,
  "leverage": 0.015,
  "acf_absret_long": 0.07,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.5`
