# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-16T19:19:31Z

## rationale

このスイープは、特にボラティリティクラスタリングを強調することを目指しています。ファンダメンタリストとチャーチストの影響を高めることで、価格の変動がより顕著になり、群集行動がより強調されるでしょう。この構造は、過去の文献での市場のダイナミクスに関連しています。

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
  "kurtosis": 10.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.04,
  "acf_absret_mean": 0.2,
  "leverage": 0.0,
  "acf_absret_long": 0.06,
  "acf_absret_decay": 0.03,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.2`
