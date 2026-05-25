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

## Phase 3: MDL 重み + 静的適格ゲート — COMPLETE

### Phase 3 成果物
1. **MDL weighting** (`src/prism/scoring/mdl.py`): w_mdl = 1/(1+log2(k))
2. **Static eligibility gate** (`src/prism/scoring/eligibility.py`): baseline facts の empirical range チェック
3. **Causal method weighting** (`src/prism/scoring/causal.py`): RCT=1.0 > DiD_FE=0.9 > ... > OLS=0.5
4. **Phase-diagram heatmap** (`src/prism/viz/heatmap.py`): matplotlib 可視化

## Phase 4: 拡張性と実用性 — COMPLETE

### 今回のセッションで達成したこと

#### Phase 4a: ZI-C null adapter + fat tails fact — commit 6990734
1. **ZI-C Adapter** (`src/prism/adapters/zi.py`): Gode & Sunder (1993) Zero-Intelligence Constrained model
   - 4 free parameters (最小) → MDL weight 0.333 (最高)
   - 学習・戦略切替なし — 構造的偽陽性ベンチマーク
   - ZI は eligibility gate で 3/4 facts FAIL → 正しく null model を検出
   - ZI は sign consistency 0/4 on both NERs → 介入応答を再現不能
2. **Fat tails (excess kurtosis)** (`estimators.py`): 4th stylized fact
   - scipy.stats.kurtosis (Fisher=True) + bootstrap CI
   - Eligibility range: [1.0, 50.0] — 全 adapter が FAIL (path 平均化による尖度低下)

#### Phase 4b: Autocorrelation of absolute returns — commit b9e1e96
3. **abs_autocorrelation** (`estimators.py`): 5th stylized fact
   - Lag-1 ACF of |r_t| — volatility long memory の直接測定
   - Eligibility range: [0.05, 0.5] (Cont 2001)

#### Phase 4c: Causal method comparison — commit dc0683d
4. **`compare_causal_methods()`** (`pipeline.py`): 同一 cell を異なる因果推定法で再重み付け
   - `prism compare` CLI コマンド追加
   - RCT (w=1.0) vs OLS (w=0.5) で 2x の confidence 差を実証
   - 6 methods × N facts のテーブル出力

#### Phase 4d: CI/CD + lint cleanup — commit 89b31f8
5. **GitHub Actions** (`.github/workflows/ci.yml`): Python 3.11/3.12 matrix
   - ruff lint → pytest --cov → mypy type check
6. **Ruff lint cleanup**: 16 issues fixed (unused imports/variables)

### Phase 4 テンソル状態
- **Tensor サイズ**: 3 adapters × 2 NERs × 5 facts = 30 cells
- **Adapters**: SG (k=7, w_mdl=0.263), CI (k=9, w_mdl=0.240), ZI (k=4, w_mdl=0.333)
- **NERs**: tspp_2016_us_equity (tick_size_increase), french_ftt_2012_eu (transaction_tax)
- **Facts**: volatility_clustering, leverage_effect, gain_loss_asymmetry, fat_tails, abs_autocorrelation
- **テスト**: 174 tests, all passing, ruff clean

### ZI ベンチマーク結果 (structural falsification)
```
ZI × tspp: eligibility FAIL (leverage+/volclust>0.999/fat_tails<1.0), sign 0/4
ZI × ftt:  eligibility FAIL (leverage+/volclust>0.999/fat_tails<1.0), sign 0/4
```
→ PRISM は null model を正しく棄却。SG/CI は leverage_effect で ZI を上回る。

### 既知の課題・改善余地
- 全 adapter が fat_tails eligibility FAIL — path 平均化が尖度を減衰。single-path モードの検討
- volatility_clustering の delta が全 adapter で INCONCLUSIVE (0.0) — GARCH fit が安定しすぎ
- NER の ground truth delta は external_claim タグ済み — 生データからの再算出は未実施
- mypy strict mode は continue-on-error (型注釈の完全化は未完)
- 実市場データ接続 (Yahoo Finance / WRDS) は Phase 5 に持越し

## 次の目標 (Phase 5 準備)

### Phase 5: データ接続と精緻化
1. 実市場データの接続 (Yahoo Finance yfinance, WRDS) — pre_data を synthetic → real に
2. Single-path simulation mode — fat tails の eligibility 改善
3. GARCH fit の安定性改善 (volatility_clustering delta が常に 0.0 の問題)
4. mypy strict 完全対応
5. NER ground truth の生データからの再算出 (external_claim → derived)
