# proposal #3 — franke_westerhoff

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-12T18:40:29Z

## rationale

この提案は、フランケ・ウェスターホフモデルのパラメータを調整することで、エージェント間の相互作用がより顕著に現れるようにすることを目指しています。特に、α_wを高く設定することで、富の不均質性が強化され、ボラティリティや尖度が高まることが期待されます。

## params

```json
{
  "alpha_w": 2.0,
  "chi": 1.5,
  "n_steps": 2500,
  "noise_scale": 0.015,
  "phi": 0.15
}
```

## predicted_fingerprint

```json
{
  "volatility": 20.0,
  "kurtosis": 10.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.07,
  "acf_absret_mean": 0.1,
  "leverage": 0.03,
  "acf_absret_long": 0.08,
  "acf_absret_decay": 0.02,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.8`
