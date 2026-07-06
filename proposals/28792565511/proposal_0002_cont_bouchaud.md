# proposal #2 — cont_bouchaud

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-07-06T12:48:58Z

## rationale

c を臨界付近 (0.98) に設定し、クラスタサイズのパワーロー分布を強化することでヒルテイル指数を極大化し、テイルの厚さを増大させます。a を低く保つことで買い・売りの不均衡が顕著になり、リターンの歪みと高いクルトシスが生まれます。Cont‑Bouchaud のパーコレーション概念に基づくパラメータチューニングです。

## params

```json
{
  "N": 4500,
  "T": 2800,
  "a": 0.006,
  "c": 0.98,
  "lam": 1.5
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.012,
  "kurtosis": 0.7,
  "hill_tail_index": 15.0,
  "acf_ret_l1": -0.05,
  "acf_absret_mean": 0.1,
  "leverage": -0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.03,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `2.5`
