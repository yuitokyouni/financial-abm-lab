# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-03T12:24:34Z

## rationale

この提案は、特に市場のダイナミクスが変化する領域をターゲットにしています。alpha_fundを0.4に設定することで、ファンダメンタリストの影響を強化し、価格が固定された公正価値に近づくことを促進します。また、chart_strengthを0.8にすることで、チャーチストの影響を高め、トレンドの持続を強化し、ボラティリティの変化を生み出すことを期待しています。

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
  "volatility": 22.0,
  "kurtosis": 10.0,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.005,
  "acf_absret_mean": 0.03,
  "leverage": 0.01,
  "acf_absret_long": 0.04,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.2
}
```

- predicted_novelty_distance: `4.8`
