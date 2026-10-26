# proposal #3 — chiarella_iori

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-26T15:54:24Z

## rationale

この提案は、chiarella_ioriモデルのフィンガープリント空間の中で、ボラティリティとレバレッジの領域をターゲットとしています。alpha_fundを0.4に設定することで、ファンダメンタルズの影響を強化し、ボラティリティのダイナミクスがより顕著になることが期待されます。また、n_stepsを2500にすることで、シミュレーションの時間的範囲を拡大し、結果として複雑な市場行動が観察できるでしょう。

## params

```json
{
  "alpha_chart": 0.3,
  "alpha_fund": 0.4,
  "alpha_noise": 0.2,
  "chart_strength": 0.8,
  "fund_speed": 0.05,
  "n_steps": 2500,
  "noise_scale": 0.01
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 7.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.1,
  "leverage": 0.03,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 0.8
}
```

- predicted_novelty_distance: `4.0`
