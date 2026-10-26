# proposal #5 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-26T15:54:24Z

## rationale

この提案は、franke_westerhoffモデルのフィンガープリント空間において、ボラティリティとレバレッジの領域をターゲットとしています。phiを0.15に設定することで、群集行動の影響を強化し、より高いボラティリティが期待されます。また、alpha_wを1.8にすることで、富の影響が強化され、より複雑な市場行動を観察することが可能になります。

## params

```json
{
  "alpha_w": 1.8,
  "chi": 1.5,
  "n_steps": 2700,
  "noise_scale": 0.015,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 20.0,
  "kurtosis": 9.0,
  "hill_tail_index": 14.0,
  "acf_ret_l1": 0.03,
  "acf_absret_mean": 0.05,
  "leverage": 0.02,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.7
}
```

- predicted_novelty_distance: `4.1`
