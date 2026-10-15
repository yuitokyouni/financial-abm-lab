# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-07-20T11:47:02Z

## rationale

このパラメータスイープは、gcmgモデルのフィンガープリント空間の中で、特にボラティリティと尖度の高い領域を目指しています。参加者数を100に増やし、T_totalを3500に設定することで、エージェントの相互作用が増加し、より大規模な市場の動きがシミュレーションされます。これにより、フィンガープリントが新しい特性を持つことが期待されます。

## params

```json
{
  "M": 4,
  "N": 100,
  "S": 3,
  "T_total": 3500,
  "T_win": 60,
  "r_min_static": 0.03
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 15.0,
  "hill_tail_index": 6.0,
  "acf_ret_l1": 0.05,
  "acf_absret_mean": 0.05,
  "leverage": 0.01,
  "acf_absret_long": 0.01,
  "acf_absret_decay": 0.02,
  "agg_kurt_decay": 1.2
}
```

- predicted_novelty_distance: `4.2`
