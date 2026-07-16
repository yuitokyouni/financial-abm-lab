# proposal #2 — cont_bouchaud

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-oss-120b`
- created_at: 2026-06-29T13:09:13Z

## rationale

c を 0.9 に近づけることでクラスタサイズのパワー律分布が臨界点に接近し、リターンのテイル指数 (hill_tail_index ≈ 12) と尖度 (kurtosis ≈ 1.2) が顕著に増大すると期待されます。これはBouchaud のクラスタモデルで臨界現象が脂肪テイルを生むことを示した研究に基づく拡張です。

## params

```json
{
  "N": 4500,
  "T": 2600,
  "a": 0.015,
  "c": 0.9,
  "lam": 1.2
}
```

## predicted_fingerprint

```json
{
  "volatility": 0.03,
  "kurtosis": 1.2,
  "hill_tail_index": 12.0,
  "acf_ret_l1": -0.01,
  "acf_absret_mean": 0.15,
  "leverage": -0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.8
}
```

- predicted_novelty_distance: `2.8`
