# proposal #3 — minority_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-14T15:43:09Z

## rationale

このスイープは、アクター間の競争が激化することで生まれる非対称性の増加を狙います。Nを100に設定することでエージェントの数を増やし、よりダイナミックな市場環境をシミュレートします。また、Mを5にすることで戦略の複雑性を高め、利得-損失非対称性を実現します。

## params

```json
{
  "M": 5,
  "N": 100,
  "S": 3,
  "T": 2500
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 18.0,
  "hill_tail_index": 12.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.03,
  "leverage": 0.01,
  "acf_absret_long": 0.01,
  "acf_absret_decay": -0.015,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.0`
