# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-10-19T16:16:02Z

## rationale

この提案は、エージェントの参加者数を調整することで、クラスター間の相互作用を強化することを目指しています。特に、戦略選択の幅を広げることで、ボラティリティとクルトシスの両方を高めることが期待されます。

## params

```json
{
  "M": 3,
  "N": 100,
  "S": 3,
  "T_total": 3000,
  "T_win": 40,
  "r_min_static": 0.02
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 20.0,
  "hill_tail_index": 10.0,
  "acf_ret_l1": 0.005,
  "acf_absret_mean": 0.03,
  "leverage": -0.01,
  "acf_absret_long": 0.05,
  "acf_absret_decay": -0.01,
  "agg_kurt_decay": 3.0
}
```

- predicted_novelty_distance: `4.0`
