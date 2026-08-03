# proposal #2 — gcmg

- status: `proposed`
- type: `param_sweep`
- llm_model: `openai/gpt-4o-mini`
- created_at: 2026-08-03T12:24:34Z

## rationale

この提案は、特に参加者の行動に基づくボラティリティのクラスタリングを強調します。T_totalを3500に設定することで、より長い期間のデータを収集し、結果としてボラティリティが高まると考えられます。また、r_min_staticを0.03にすることで、エージェントがより積極的に参加する条件を設定し、これが結果的に市場のダイナミクスに影響を与えることを期待しています。

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
  "volatility": 35.0,
  "kurtosis": 12.0,
  "hill_tail_index": 20.0,
  "acf_ret_l1": 0.02,
  "acf_absret_mean": 0.04,
  "leverage": 0.03,
  "acf_absret_long": 0.06,
  "acf_absret_decay": -0.02,
  "agg_kurt_decay": 1.8
}
```

- predicted_novelty_distance: `4.2`
