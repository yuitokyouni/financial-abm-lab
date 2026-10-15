# proposal #2 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-24T09:48:30Z

## rationale

この提案は、ファンダメンタリストとチャーチスト間の相互作用のダイナミクスを探索することを目指しています。特に、alpha_wを1.5に設定することで、富の不均衡が強化され、価格変動が増加する可能性があります。文献はありませんが、過去のモデルと矛盾しないように設定されています。

## params

```json
{
  "alpha_w": 1.5,
  "chi": 1.5,
  "n_steps": 2800,
  "noise_scale": 0.01,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 12.0,
  "kurtosis": 6.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.02,
  "leverage": -0.02,
  "acf_absret_long": 0.04,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.5
}
```

- predicted_novelty_distance: `4.0`
