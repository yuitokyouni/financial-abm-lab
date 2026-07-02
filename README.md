# financial-abm-lab

金融市場 Agent-Based Modeling 研究のモノレポ。散在していた研究リポを履歴ごと1つに収束。
設計と受け入れ条件は [`specs/001-monorepo-consolidation.md`](specs/001-monorepo-consolidation.md) が ground truth。

## 統合ステータス

**Stage A — 履歴ごと取り込み(完了)**: 6リポを `imported/` 配下に subtree merge(履歴保持)。

| 取り込み元 | 配置 | 履歴 | 中心アイデア |
|---|---|---|---|
| speculation-game-info | `imported/speculation-game-info` | ✓ 保持 | 古典→最新ABMの再現実装 (YH001-006_1) |
| PROV-ABM-atlas | `imported/PROV-ABM-atlas` | ✓ 保持 (feat/sf-classifier-equivalence) | 介入応答 vs SF の機構弁別 toy + provenance L2 |
| PRISM | `imported/PRISM` | ✓ 保持 | 自然実験による ABM 介入応答スコアリング (撤退済・系譜) |
| market-dynamics | `imported/market-dynamics` | ✓ 保持 | free-energy landscape による市場レジーム検知 |
| ABM-Microstructure | `imported/ABM-Microstructure` | ✓ 保持 | batch vs continuous の algo共謀設計マップ |
| agent-based-modeling | `imported/agent-based-modeling` | ✗ スナップショット (upstream に .git 無し) | LLM-as-agent (semantic Schelling) |

**Stage B — core 抽出と再編(未着手)**: `imported/` の中身を以下へ再配置する。
SG/CI/ZI/LM/FW の三重実装を `packages/abm_models` の単一正準実装に統一するのが最大の目的。

```
packages/
  abm_models/      SG/CI/ZI/LM/FW + 共通 ModelAdapter protocol (一度だけ)
  stylized_facts/  SF battery 統一
  market/          aggregate + CLOB + LOB
  regimes/         KM + β-VAE + free-energy
  provenance/      PROV-O + L2 ctx + prov_record(cap-alloc から昇格)
experiments/       core を import する薄いラッパー (classical / speculation_game /
                   microstructure / intervention_atlas / regimes / llm_abm)
research/          atelier/mycelium 同期 (idea-provenance.ttl)
```

Stage B の最初の一歩 = backbone 検証(T0): 正準 SG を抽出 → YH005 を core import 版に書き換え →
findings が**統計的等価**(相対誤差 ≤ 5%)で再現するか。go なら同型で残りを移行。

## 統合しない(独立維持)

- **capital-allocation** … IBKR 実運用リポ。研究核と混ぜない。`prov_record.py` のみ `packages/provenance` に昇格して逆参照させる。
- **MultiAgent-Trader** … 日本株×LLM 応用。core を import する satellite に留める。
- **atelier/mycelium** … マザー知識ベース。`research/` に同期し、コードと混ぜない。

## 旧リポの扱い

Stage A 完了後、取り込み済みの旧 GitHub リポは **archive 化(read-only)** する。
各旧リポの履歴はこのモノレポ内に保存されている。

---

## Appendix — fabm 当初の設計メモ (Stage B で packages 化する規約)

元 `financial-abm-lab` scaffold が掲げていた規約。Stage B の core 設計時に踏襲する:

- 全 experiment は config 駆動 (`experiment_name`, `seed`, `data.symbol`/`start`/`end`, `simulation.n_agents`/`n_steps`)。
- multi-seed: master_seed から agent/order/news/simulation/validation の子 seed を spawn(`src/fabm/rng.py` の `make_rngs`)。
- 標準 metrics: `mean_return, volatility, kurtosis, tail_index, abs_return_acf`。
- 結果は graph だけでなく **table で保存**: `run_id, timestamp, git_commit, config_path, seed, parameters, metrics, artifact_paths, notes`。
