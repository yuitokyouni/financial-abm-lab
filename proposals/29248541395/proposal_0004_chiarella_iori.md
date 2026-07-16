# proposal #4 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-13T12:07:47Z

## rationale

chiarella_iori でチャート係数 alpha_chart とノイズ係数 alpha_noise をそれぞれ 0.45, 0.35 に高め、価格変動の自己強化効果を強調します。これによりリターンの一次自己相関が正に偏り、acf_ret_l1 が顕著に上昇すると考えられます。指紋は現在の中心から正のacf方向へ拡がります。

## params

```json
{
  "alpha_chart": 0.45,
  "alpha_fund": 0.55,
  "alpha_noise": 0.35,
  "chart_strength": 1.0,
  "fund_speed": 0.09,
  "n_steps": 2500,
  "noise_scale": 0.015
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.009,
  "kurtosis": 0.5,
  "hill_tail_index": 5.0,
  "acf_ret_l1": 0.12,
  "acf_absret_mean": 0.2,
  "leverage": -0.02,
  "acf_absret_long": 0.15,
  "acf_absret_decay": -0.05,
  "agg_kurt_decay": 0.7
}
```

- predicted_novelty_distance: `2.6`
