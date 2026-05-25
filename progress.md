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

### Phase 2 成果物
1. **NER #2** (`data/ner/french_ftt_2012_eu.yaml`): French FTT 2012, transaction_tax 介入クラス — commit a64d6d1
2. **CI Adapter** (`src/prism/adapters/ci.py`): Chiarella-Iori 型 order-book モデル — commit a64d6d1
3. **`run_tensor()`** (`src/prism/pipeline.py`): adapter × NER × fact の完全テンソル実行 + divergence analysis — commit a64d6d1
4. **`prism tensor` CLI** — commit a64d6d1

### 介入応答ダイバージェンス (実行結果)
```
DIVERGENCE [tspp_2016_us_equity/leverage_effect]: sg=match vs ci=mismatch
DIVERGENCE [french_ftt_2012_eu/leverage_effect]: sg=match vs ci=mismatch
```

## Phase 3: MDL 重み + 静的適格ゲート — COMPLETE

### 今回のセッションで達成したこと
1. **MDL weighting** (`src/prism/scoring/mdl.py`): 自由パラメータ数に基づく複雑度ペナルティ。w_mdl = 1/(1+log2(k)) — commit 70728e2
   - SG (k=7): w=0.263,  CI (k=9): w=0.240 → 単純モデルが有利
2. **Static eligibility gate** (`src/prism/scoring/eligibility.py`): baseline facts の empirical range チェック — commit 70728e2
   - volatility_clustering: [0.5, 0.999], leverage_effect: [-0.5, 0.0], gain_loss_asymmetry: [-3.0, 0.5]
   - 不適格モデルは tensor 出力でハッチング表示
3. **Causal method weighting** (`src/prism/scoring/causal.py`): 因果推定手法の品質階層 — commit a55dc82
   - RCT=1.0 > DiD_FE=0.9 > DiD=0.85 > SC=0.8 > IV=0.7 > OLS=0.5
   - combined confidence = raw × mdl_weight × causal_weight
4. **Phase-diagram heatmap** (`src/prism/viz/heatmap.py`): matplotlib 可視化 — commit 4031c91
   - `prism heatmap` CLI コマンド: 色分け (green=MATCH, red=MISMATCH, gray=INCONCLUSIVE)
   - MDL 重み付き confidence 表示、不適格アダプタのハッチング
5. **テスト**: 139 tests (99 unit + 40 integration), all passing

### Phase 3 終了条件の達成状況
- [x] MDL ベースのモデル複雑度ペナルティが confidence に乗算される
- [x] 静的適格ゲート: baseline facts が empirical range 内かチェック
- [x] causal_method の品質重みが scoring に統合されている
- [x] 位相図のビジュアライゼーション (matplotlib heatmap)

### 既知の課題・改善余地
- NER の ground truth delta は外部引用値 (external_claim タグ済み)。生データからの再算出は未実施
- GARCH estimator の bounds が tight — iid データでの boundary warning あり
- CI adapter のキャリブレーションは簡易版 (noise_scale, price_impact のみ)
- volatility_clustering の delta が両 adapter で INCONCLUSIVE (0.0) — GARCH fit が安定しすぎている可能性
- MDL の description_length は現在 n_free_params と同値 — 構造記述の情報量を反映した計算は未実装

## 次の目標 (Phase 4 準備)

### Phase 4: 拡張性と実用性
1. 新 adapter 追加 (e.g., LUX model, ZI model) で N>2 の位相図
2. 実市場データの接続 (Yahoo Finance / WRDS)
3. causal_method の差し替え可能性テスト (DiD → SC 等) — 同一 NER で複数推定法を比較
4. LOB-Bench 式 realism check の精緻化 (autocorrelation, fat tails)
5. CI/CD パイプラインの構築
