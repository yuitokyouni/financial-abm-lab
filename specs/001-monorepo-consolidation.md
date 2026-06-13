# Spec 001 — 金融ABM研究リポ統合 (financial-abm-lab monorepo化)

- Status: Draft (レビュー待ち)
- Author: Yuito
- Created: 2026-06-13
- Decisions: git履歴ごと統合 / 旧リポ archive化 / parity=統計的等価

---

## 1. 動機 (Why)

金融市場ABMの研究が**7リポに発散**し、同じ核(機構弁別・再現性・provenance)を別角度で繰り返し作り直している。
最も load-bearing な問題は **SG/CI/ZI/LM/FW の5モデルが PRISM / PROV-ABM-atlas / speculation-game-info で三重実装**され、protocol非互換で再利用できないこと。
さらに speculation-game-info の 17k LOC は experiments にベタ書きされ、import 可能な形になっていない。

`financial-abm-lab` は元々「古典→最新ABMを単一frameworkで統一」する器として作られたが、10 LOC の空のまま放置された。本 spec はこの空器を**統合の正準的な受け皿**として昇格させる。

> 非ゴール宣言: これは「新しいリポを増やす」プロジェクトではない。**収束**のためのプロジェクトである。本 spec の期間中、金融ABM核に属する新規リポを作ってはならない。

---

## 2. 成果 (Outcomes / Desired End State)

- O1. SG/CI/ZI/LM/FW を含む ABMモデルが `packages/abm_models` に**1実装だけ**存在し、全 experiments がそれを import する。
- O2. 新しいABMモデルを足すとき、market/SF/provenance を再実装せず core を import するだけで済む。
- O3. 既存の検証済み findings (YH001-006_1 等) が統合後も**統計的等価**で再現できる。
- O4. 統合された各リポの **git コミット系譜が保持**される (provenance要件)。
- O5. 実運用リポ (capital-allocation) と応用リポ (MultiAgent-Trader) は研究核から**隔離**されたまま、共有資産 (prov_record) だけを core 経由で参照する。

---

## 3. スコープ

### 3.1 統合する (研究核 → financial-abm-lab に畳む)

| 旧リポ | 移植先 | 主資産 |
|---|---|---|
| speculation-game-info | `experiments/classical/`, `experiments/speculation_game/` + 抽出を `packages/` | YH001-006_1 (17k LOC) |
| PROV-ABM-atlas | `packages/provenance/`(L2 ctx), `experiments/intervention_atlas/`(toy) | provabm, toy T/H |
| PRISM | `packages/provenance/`(PROV-O), `experiments/intervention_atlas/`(NER) | adapters, SF, NER corpus |
| market-dynamics | `packages/regimes/`, `experiments/regimes/` | KM推定, β-VAE, free-energy |
| ABM-Microstructure | `packages/market/`(CLOB), `experiments/microstructure/` | book/engine, qlearn collusion |
| agent-based-modeling | `experiments/llm_abm/` | semantic_schelling, LLM backends |

### 3.2 統合しない (独立維持)

| リポ | 理由 | 例外 |
|---|---|---|
| capital-allocation | IBKRで実資産を運用中。運用リポを研究monorepoに混ぜるのは事故源 | `prov_record.py` を `packages/provenance` に昇格し、capital-allocation 側が逆に参照 |
| MultiAgent-Trader | 日本株×LLMの応用ドメイン。core を import する satellite に留める | LLMエージェント共通基盤を将来 core から供給可 |
| atelier/mycelium | コードでなくマザー知識ベース | `research/` に同期 (idea-provenance.ttl)。コードと混ぜない |

### 3.3 明示的に scope 外 (Out of scope)

- 旧リポの機能を**改良**すること (移植は等価維持が目的。改良は別 spec)。
- PROV-ABM の L3 (AST/taint/strict validator) 実装 (L2 のまま移植)。
- capital-allocation / MultiAgent-Trader のコードを monorepo に取り込むこと。
- 新規ABMモデル・新規 stylized fact の追加。

---

## 4. ターゲット構造

```
financial-abm-lab/
├── pyproject.toml                 # uv workspace root
├── packages/
│   ├── abm_models/                # SG/CI/ZI/LM/FW + 共通 ModelAdapter protocol (一度だけ)
│   ├── stylized_facts/            # SF battery 統一 (PRISM + PROV-ABM の定義を統合)
│   ├── market/                    # aggregate(excess-demand) + CLOB(ABM-Micro) + LOB(YH006)
│   ├── regimes/                   # KM推定 + β-VAE + free-energy landscape
│   └── provenance/                # PROV-O(PRISM) + L2 ctx(PROV-ABM) + prov_record(cap-alloc)
├── experiments/                   # core を import する薄いラッパー
│   ├── classical/                 # YH001-004
│   ├── speculation_game/          # YH005-007
│   ├── microstructure/            # ABM-Micro 実験A/B
│   ├── intervention_atlas/        # PRISM NER + PROV-ABM toy (撤退仮説の検証系譜)
│   ├── regimes/                   # market-dynamics 実験
│   └── llm_abm/                   # semantic schelling, YH008
├── research/                      # atelier/mycelium 同期 (read-mostly)
├── docs/                          # model_catalog, findings統合, integration_map, ontology
└── specs/                         # 本 spec を含む
```

---

## 5. 制約 (Constraints)

- C1. パッケージ管理は **uv workspace** に統一する (PROV-ABM-atlas/ABM-Microstructure が既に uv。market-dynamics の pip 構成は uv に変換)。
- C2. 移植は **git 履歴を保持**する。`git subtree add --prefix=...` もしくは `git-filter-repo` でサブディレクトリに移し替えてから merge する。単純コピーは禁止。
- C3. lint/format gate (ruff) と pytest を root で一括実行できること。
- C4. 移植順は **依存の葉から**: `packages/` のコア → それを使う `experiments/`。experiments を先に動かさない。
- C5. 各移植 PR は「移植のみ・挙動不変」を原則とし、リファクタは最小に留める。

---

## 6. 前提 (Assumptions)

- A1. speculation-game-info の YH005 には parity 契約(RNG消費順)が既に存在し、抽出後の検証基準として使える。
- A2. PRISM と PROV-ABM-atlas の SG/CI/ZI/LM/FW は概念的に同一モデルで、正準実装に統一可能 (測定 anchor の違いは設定で吸収する)。
- A3. 旧リポは GitHub 上にあり、archive フラグを立てられる。
- A4. atelier/mycelium の `research/` 同期は read-mostly で、monorepo 側から書き戻さない。

---

## 7. 受け入れ条件 (EARS 風・検証可能)

### Backbone (最初の一歩)

- AC1. WHEN 3つの重複SG実装から正準SG実装を `packages/abm_models` に抽出したとき、THE SYSTEM SHALL 単一の `ModelAdapter` protocol を通じて SG を生成・実行できる。
- AC2. WHEN YH005 experiment を core import 版に書き換えて同一 seed で実行したとき、THE SYSTEM SHALL 主要 findings (Hill α, excess kurtosis, null/baseline 比, ACF) を**旧実装の許容誤差内**で再現する。
  - 許容誤差の既定値: 相対誤差 |new−old|/|old| ≤ 0.05 (=5%)。値ごとの個別許容は docs/findings に明記。
- AC3. WHEN backbone が通ったとき、THE SYSTEM SHALL 同じ移植パターン (抽出→core import→parity) を残りモデルに適用できる手順を docs に残す。

### 統合全体

- AC4. WHEN 任意の experiment を実行するとき、THE SYSTEM SHALL ABMモデル・SF・market・provenance を `packages/` から import し、experiment 配下に重複実装を持たない。
- AC5. WHEN 新しいABMモデルを追加するとき、THE SYSTEM SHALL `packages/abm_models` に1ファイル追加 + protocol 準拠のみで、market/SF/provenance の再実装を要求しない。
- AC6. WHEN リポを移植したとき、THE SYSTEM SHALL 移植元の git コミット系譜を `git log --follow` で辿れる状態にする。
- AC7. WHEN 統合が完了したリポについて、THE SYSTEM SHALL GitHub 上で archive 化し、README に統合先 (financial-abm-lab の該当パス) を明記する。
- AC8. WHEN root で `uv run pytest` を実行するとき、THE SYSTEM SHALL 全 packages と全 experiments のテストを単一コマンドで走らせ green にする。
- AC9. WHEN capital-allocation が provenance を記録するとき、THE SYSTEM SHALL `packages/provenance` の prov_record を参照し、cap-alloc 側に重複実装を残さない (cap-alloc 自体は独立リポのまま)。

---

## 8. タスク分解 (依存順)

> Phase 0 (backbone) が通るまで Phase 1 以降に進まない。

- **T0. Backbone 検証** ← 最初の一歩 / go-no-go ゲート
  - T0.1 `pyproject.toml` を uv workspace 化し `packages/` `experiments/` スケルトンを作る
  - T0.2 3実装の SG を比較し正準実装を決定 → `packages/abm_models/sg.py` + `ModelAdapter` protocol
  - T0.3 `packages/stylized_facts` に YH005 が依存する最小 SF (Hill, kurtosis, ACF, null比) を抽出
  - T0.4 YH005 を core import 版へ書き換え → AC2 の parity を測定
  - T0.5 結果を `docs/backbone_parity.md` に記録 (go-no-go 判定)
- **T1. provenance パッケージ統合** (PROV-O + L2 ctx + prov_record)
- **T2. 残り ABMモデル統合** (CI/ZI/LM/FW + 古典 YH001-004)
- **T3. market パッケージ統合** (aggregate + CLOB + LOB)
- **T4. speculation_game experiments 移植** (YH005-007, 履歴保持)
- **T5. intervention_atlas 移植** (PRISM NER + PROV-ABM toy)
- **T6. regimes 統合** (market-dynamics, pip→uv 変換)
- **T7. microstructure / llm_abm 移植**
- **T8. research/ に atelier 同期 + 旧リポ archive化 + README統合先明記**
- **T9. cap-alloc を packages/provenance 参照に切替** (cap-alloc は独立のまま)

---

## 9. リスクと留意

- R1. SG正準化で測定 anchor の差が parity を割る → 設定で吸収できる範囲か T0.2 で先に切り分ける。割れたら「等価でない=統合前に別実装だった」事実を docs に残す (provenance)。
- R2. git subtree merge でパス衝突 → prefix を packages/experiments に分けて回避。
- R3. uv workspace で各旧リポの依存が衝突 → root で版を pin、衝突は移植 PR ごとに解消。
- R4. 「移植ついでに改良」して挙動が変わる → C5 で禁止。改良は別 spec に切る。

---

## 10. Checklist (要件の "unit test" — レビュー用)

完全性:
- [ ] 全7リポの行き先 (統合先パス or 独立維持) が §3 で一意に決まっているか
- [ ] backbone の go-no-go 判定基準が数値で書かれているか (AC2)
- [ ] parity 許容誤差の既定値が明記されているか

明確性:
- [ ] 「統計的等価」が測定量と閾値で定義されているか (曖昧語でないか)
- [ ] 「履歴保持」が具体手段 (subtree/filter-repo) に落ちているか
- [ ] 独立維持リポと統合リポの境界が、例外 (prov_record) 含め矛盾なく書かれているか

一貫性:
- [ ] §2 Outcomes と §7 AC が1対1で対応しているか (O1↔AC4/AC5, O3↔AC2, O4↔AC6, O5↔AC9)
- [ ] scope外 §3.3 と タスク §8 に矛盾がないか (scope外をタスク化していないか)
- [ ] 「新リポを作らない」非ゴールが全体で一貫しているか

実行可能性:
- [ ] T0 だけで go-no-go が判定でき、失敗時に統合を止められる設計か
- [ ] 各 Phase が依存順に並び、葉から実行されるか (C4)
```
