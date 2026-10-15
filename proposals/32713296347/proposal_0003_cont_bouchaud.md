# proposal #3 — cont_bouchaud

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-24T09:48:30Z

## rationale

このパラメータスイープは、エージェントの相互作用が価格形成に与える影響を探求することを目指しています。特に、cの値を0.7に設定することで、エージェント間の接続性が強化され、より複雑な取引パターンが生まれると考えています。文献はありませんが、過去のネットワークモデルに基づいています。

## params

```json
{
  "N": 3000,
  "T": 2500,
  "a": 0.015,
  "c": 0.7,
  "lam": 1.0
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 7.0,
  "hill_tail_index": 14.0,
  "acf_ret_l1": 0.0,
  "acf_absret_mean": 0.02,
  "leverage": -0.01,
  "acf_absret_long": 0.0,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `5.2`
