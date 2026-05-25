# Current Progress

## Phase 1 MVP — COMPLETE

`prism run` が実行でき、SG × tick_size × 3 facts の 1 result cell を生成する。
同一 seed で bit 再現可能。provenance 情報が result に含まれる。

### Phase 1 成果物
1. **Core types** (`src/prism/types.py`): MarketData, ModelAdapter Protocol, 全データ型 — commit 86bd538
2. **Fact Estimator Library v0.1** (`src/prism/facts/estimators.py`): GARCH(1,1) vol clustering, leverage effect (Corr), gain/loss asymmetry (skewness) + bootstrap CI — commit 86bd538
3. **Scorer v0.1** (`src/prism/scoring/scorer.py`): 符号一致 + magnitude within CI — commit 207fd6d
4. **Provenance v0.1** (`src/prism/provenance/tracker.py`): data hash, git commit, RNG seed, W3C PROV-O type tags — commit 7ab8fc3
5. **NER loader** (`src/prism/data/ner_loader.py`) + **NER #1** (`data/ner/tspp_2016_us_equity.yaml`) — commit 355d329
6. **SG Adapter** (`src/prism/adapters/sg.py`): Katahira (2019) variant, ModelAdapter Protocol 準拠 — commit 355d329
7. **Pipeline + CLI** (`src/prism/pipeline.py`, `src/prism/cli/main.py`) — commit 33c8330

## Phase 2: 診断介入 + 2機構目 — COMPLETE

### 今回のセッションで達成したこと
1. **NER #2** (`data/ner/french_ftt_2012_eu.yaml`): French FTT 2012, transaction_tax 介入クラス — commit a64d6d1
2. **CI Adapter** (`src/prism/adapters/ci.py`): Chiarella-Iori 型 order-book モデル, ModelAdapter Protocol 準拠, tick_size_increase + transaction_tax 両対応 — commit a64d6d1
3. **`run_tensor()`** (`src/prism/pipeline.py`): adapter × NER × fact の完全テンソル実行 + divergence analysis — commit a64d6d1
4. **`prism tensor` CLI** (`src/prism/cli/main.py`): `prism tensor --adapters sg,ci --ners ... --facts ...` が動作 — commit a64d6d1
5. **テスト**: 88 tests (68 unit + 20 integration), all passing

### Phase 2 終了条件の達成状況
- [x] 2 adapter (SG, CI) × 2 intervention (tick_size_increase, transaction_tax) × 3 facts のテンソルが生成される
- [x] `prism tensor` CLI で 2×2 位相図が出力される
- [x] 少なくとも 1 ペアの adapter で「静的 facts 同等 but 介入応答で乖離」を実証
  - leverage_effect: SG=MATCH vs CI=MISMATCH (両介入で一貫)
  - → SG は leverage effect の符号を正しく再現するが、CI は再現しない = 機構の違いが介入応答で表出

### 介入応答ダイバージェンス (実行結果)
```
DIVERGENCE [tspp_2016_us_equity/leverage_effect]: sg=match vs ci=mismatch
DIVERGENCE [french_ftt_2012_eu/leverage_effect]: sg=match vs ci=mismatch
```

### 既知の課題・改善余地
- NER の ground truth delta は外部引用値 (external_claim タグ済み)。生データからの再算出は未実施
- GARCH estimator の bounds が tight — iid データでの boundary warning あり
- CI adapter のキャリブレーションは簡易版 (noise_scale, price_impact のみ)
- 静的適格ゲート (LOB-Bench 式 realism check) は未実装
- volatility_clustering の delta が両 adapter で INCONCLUSIVE (0.0) — GARCH fit が安定しすぎている可能性

## 次の目標 (Phase 3 準備)

### Phase 3: MDL 重み + 静的適格ゲート
1. Minimum Description Length (MDL) ベースのモデル複雑度ペナルティ
2. 静的適格ゲート: baseline facts が empirical range 内かチェック → 不適格モデルを tensor から除外
3. causal_method の差し替え可能性テスト (DiD → SC 等)
4. 位相図のビジュアライゼーション (matplotlib heatmap)
