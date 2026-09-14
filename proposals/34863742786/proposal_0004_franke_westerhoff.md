# proposal #4 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-14T15:43:09Z

## rationale

この提案は、群集行動によるボラティリティクラスタリングの強化を目指しています。phiとchiの設定により、エージェントの行動がより柔軟に変更され、集団のダイナミクスを強調します。これにより、マーケットの非対称性を強化することが期待されます。

## params

```json
{
  "alpha_w": 1.5,
  "chi": 1.0,
  "n_steps": 2500,
  "noise_scale": 0.01,
  "phi": 0.1
}
```

## predicted_fingerprint

```json
{
  "volatility": 18.0,
  "kurtosis": 14.0,
  "hill_tail_index": 9.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.04,
  "leverage": 0.005,
  "acf_absret_long": 0.005,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.6
}
```

- predicted_novelty_distance: `3.8`
