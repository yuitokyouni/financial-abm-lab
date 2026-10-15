# proposal #1 — speculation_game

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-10T10:18:05Z

## rationale

このスイープは、ボラティリティの高い領域を狙っています。特に、Nを350に設定することで、エージェントの数が増加し、より多様な戦略が形成されることでボラティリティが高まると考えられます。また、Cを3.2に設定することで、より強い戦略が選択され、価格の変動を引き起こす可能性があります。

## params

```json
{
  "B": 8,
  "C": 3.2,
  "M": 4,
  "N": 350,
  "S": 3,
  "T": 2250
}
```

## predicted_fingerprint

```json
{
  "volatility": 25.0,
  "kurtosis": 5.0,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.01,
  "acf_absret_mean": 0.1,
  "leverage": 0.02,
  "acf_absret_long": 0.005,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 0.5
}
```

- predicted_novelty_distance: `4.5`
