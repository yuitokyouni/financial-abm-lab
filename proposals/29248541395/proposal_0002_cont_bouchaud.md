# proposal #2 — cont_bouchaud

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-13T12:07:47Z

## rationale

cont_bouchaud のパラメータ c を 0.95 に近づけ、臨界的なクラスター形成を促すことで、リターンの尖度とヒルテイル指数が大幅に増大すると予想します。高い a と lam により取引インパクトも増し、指紋空間では尖度・テイル側の離散点へ到達します。

## params

```json
{
  "N": 4500,
  "T": 2800,
  "a": 0.015,
  "c": 0.95,
  "lam": 1.5
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.008,
  "kurtosis": 2.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": -0.02,
  "acf_absret_mean": 0.3,
  "leverage": -0.01,
  "acf_absret_long": 0.12,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 1.0
}
```

- predicted_novelty_distance: `2.2`
