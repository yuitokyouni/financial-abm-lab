# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-11-09T19:32:31Z

## rationale

この提案は、群集行動が強く影響するボラティリティの高い状態を探求することに焦点を当てています。パラメータ設定により、エージェントの参加基準をわずかに引き上げることで、より極端な参加状況を促進し、結果としてヘビーテールを持つリターン分布を生成することが期待されます。

## params

```json
{
  "M": 4,
  "N": 100,
  "S": 3,
  "T_total": 3500,
  "T_win": 60,
  "r_min_static": 0.02
}
```

## predicted_fingerprint

```json
{
  "volatility": 45.0,
  "kurtosis": 15.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.15,
  "leverage": 0.03,
  "acf_absret_long": 0.07,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.5`
