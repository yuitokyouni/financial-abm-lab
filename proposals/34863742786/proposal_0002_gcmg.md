# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-09-14T15:43:09Z

## rationale

この提案は、特にヘビーテールを持つ新しい出現を促進します。Nを100に設定することで、エージェント間の相互作用が増加し、より多様な行動パターンが生成されると考えられます。r_min_staticを0.02にすることで、参加基準が引き上げられ、より戦略的な行動を促します。

## params

```json
{
  "M": 4,
  "N": 100,
  "S": 3,
  "T_total": 3000,
  "T_win": 50,
  "r_min_static": 0.02
}
```

## predicted_fingerprint

```json
{
  "volatility": 30.0,
  "kurtosis": 15.0,
  "hill_tail_index": 15.0,
  "acf_ret_l1": 0.0,
  "acf_absret_mean": 0.01,
  "leverage": -0.01,
  "acf_absret_long": -0.005,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 2.0
}
```

- predicted_novelty_distance: `4.5`
