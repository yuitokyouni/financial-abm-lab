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

### Phase 4 成果物
1. **ZI-C Adapter** (`src/prism/adapters/zi.py`): null model ベンチマーク — commit 6990734
2. **Fat tails (excess kurtosis)** + **abs_autocorrelation** — commits 6990734, b9e1e96
3. **Causal method comparison** (`compare_causal_methods()`, `prism compare`) — commit dc0683d
4. **GitHub Actions CI** (`.github/workflows/ci.yml`) — commit 89b31f8

## Phase 5: データ接続と精緻化 — COMPLETE

### 今回のセッションで達成したこと

#### Phase 5a: Per-path fact estimation — commit 60a9546
1. **`per_path_facts` モード** (`pipeline.py`): 個別パスで fact を計算し median で集約
   - path 平均化による尖度・歪度の消失を回避 (CLT 効果の排除)
   - `run_cell()`, `run_tensor()`, `compare_causal_methods()` に `per_path_facts` パラメータ追加
   - `--per-path-facts` CLI フラグを全サブコマンドに追加
   - 6 integration tests 追加

#### Phase 5b: GARCH optimizer + squared_return_acf — commit 222746e
2. **GARCH(1,1) 最適化改善**: beta 下限 0.3→0.01, alpha 上限 0.5→0.7, 6 starting points (低持続性含む)
3. **`squared_return_acf`** (`estimators.py`): 6th stylized fact — r² の lag-1 ACF
   - 最適化不要、GARCH persistence より感度の高いボラティリティクラスタリング指標
   - 両 NER に ground truth delta 追加、eligibility range [0.05, 0.5]
4. **Estimator version** 0.1.0 → 0.2.0

#### Phase 5c: Real market data via yfinance — commit 4d1a2ab
5. **`fetch_returns()`** (`data/market_data.py`): Yahoo Finance からの日次対数リターン取得
6. **`fetch_pre_intervention_data()`**: NER の venue/date に基づく自動データ取得
   - US_equity_smallcap → IWM, EU_equity_largecap → EZU
7. **`use_real_data`** パラメータ + `--real-data` CLI フラグ
   - synthetic N(0,0.02) → 実データでのキャリブレーション
8. **Optional dependency**: `pip install prism-abm[real-data]`

#### Phase 5d: mypy strict compliance — commit 949e7d6
9. **mypy --strict 完全パス** (0 errors, 23 source files)
   - ModelAdapter protocol 型注釈、FactResult metadata dict 型修正
   - CLI 変数名分離 (型衝突解消)、`_write_json` ヘルパー抽出
   - types-PyYAML stubs 導入

### Phase 5 テンソル状態
- **Tensor サイズ**: 3 adapters × 2 NERs × 6 facts = 36 cells
- **Adapters**: SG (k=7, w_mdl=0.263), CI (k=9, w_mdl=0.240), ZI (k=4, w_mdl=0.333)
- **NERs**: tspp_2016_us_equity, french_ftt_2012_eu
- **Facts**: volatility_clustering, leverage_effect, gain_loss_asymmetry, fat_tails, abs_autocorrelation, squared_return_acf
- **テスト**: 192 tests, all passing
- **品質**: ruff clean, mypy strict clean

### 既知の課題・改善余地
- NER の ground truth delta は external_claim タグ済み — 生データからの再算出は未実施
- 実市場データ接続のテストは yfinance + network 依存 (CI では skip される可能性)
- GARCH delta が引き続き小さい可能性 — squared_return_acf が補完的指標として機能

## 次の目標 (Phase 6 準備)

### Phase 6: 高度な分析と文書化
1. NER ground truth の生データからの再算出 (external_claim → derived)
2. 追加 NER (例: MiFID II 2018, Japanese tick size 2014)
3. 追加 adapter (例: LLSm, Farmer-Joshi)
4. 論文用の図表生成 (LaTeX 対応)
5. ドキュメント整備 (API docs, チュートリアル)
