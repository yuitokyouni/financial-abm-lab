# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-27T12:25:24Z

## rationale

この提案は、ファンダメンタリスト、チャーチスト、ノイズトレーダーの相互作用を強化することを目指しています。特にα_fundとα_chartを上昇させることで、価格発見の過程における競争が激化し、ボラティリティが増加することが期待されます。

## params

```json
{
  "alpha_chart": 0.3,
  "alpha_fund": 0.4,
  "alpha_noise": 0.2,
  "chart_strength": 0.8,
  "fund_speed": 0.05,
  "n_steps": 2800,
  "noise_scale": 0.01
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 11.0,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.005,
  "acf_absret_mean": 0.02,
  "leverage": -0.005,
  "acf_absret_long": 0.015,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.6
}
```

- predicted_novelty_distance: `4.1`
