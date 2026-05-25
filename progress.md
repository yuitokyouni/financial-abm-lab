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

### Phase 5 成果物
1. **Per-path fact estimation** — commit 60a9546
2. **GARCH optimizer improvement + squared_return_acf** — commit 222746e
3. **Real market data via yfinance** — commit 4d1a2ab
4. **mypy strict compliance** — commit 949e7d6

## Phase 6: 高度な分析と文書化 — IN PROGRESS

### 今回のセッションで達成したこと

#### Phase 6a+6b: MiFID II NER + Lux-Marchesi adapter — commit 0936e33
1. **NER #3** (`data/ner/mifid2_2018_eu_tick.yaml`): MiFID II 2018 EU tick size regime
   - tick_size_increase 介入クラス (EUR 0.005 → 0.01)
   - Aquilina, Budish & O'Neill (2022) + Comerton-Forde et al. (2019) からの ground truth
   - 6 facts の delta + CI95 付き
2. **LM Adapter** (`src/prism/adapters/lm.py`): Lux-Marchesi (1999, 2000) herding model
   - fundamentalist/chartist 2群 + 意見動学 (herding)
   - tick_size_increase: 粗いグリッドが herding cascade を抑制
   - transaction_tax: chartist の trend-following を減衰
   - k=8 free params, ModelAdapter Protocol 準拠
   - 14 unit tests (protocol, intervention, reproducibility)
3. **Pipeline 拡張**: ADAPTER_REGISTRY に "lm" 追加、全既存テスト互換
4. **Integration tests**: LM × 3 NER + MiFID II × 全 adapter テスト追加
5. **Tensor**: 4 adapters × 3 NERs × 6 facts = 72 cells

#### Phase 6c: LaTeX 図表生成 — commit 09ae07a
6. **`render_latex_heatmap()`** (`src/prism/viz/latex.py`): 論文品質 PDF/PGF ヒートマップ
   - LaTeX テキスト対応 (Computer Modern, 数式ラベル)
   - LaTeX 未インストール環境では mathtext にフォールバック
7. **`export_latex_table()`**: 完全な `\begin{table}` 環境の LaTeX ソース生成
   - checkmark/times 符号、MDL重み付き信頼度、gray 表示 (ineligible)
   - booktabs スタイル
8. **CLI**: `prism latex-heatmap` + `prism latex-table` サブコマンド

#### Phase 6d: JPX 2014 tick size decrease NER — commit 789b0c0
9. **NER #4** (`data/ner/jpx_2014_jp_tick.yaml`): JPX tick size reduction for TOPIX 100 stocks
   - tick_size_decrease 介入クラス (JPY 1.0 → 0.1)
   - Comerton-Forde, Putniņš & Tang (2022) + Yao & Ye (2018) からの ground truth
   - 6 facts の delta + CI95 付き
10. **tick_size_decrease** 介入クラス: 全 4 adapters に追加
    - SG: finer ticks → β増加 (switching amplification)
    - CI: finer ticks → spread_ticks 増加, price_impact 減少
    - ZI: finer ticks → bid_ask_spread 縮小
    - LM: finer ticks → herd_strength 増加, opinion_decay 抑制
11. **JP_equity_largecap venue**: yfinance 用 EWJ マッピング追加
12. **Unit tests**: 全 adapter に tick_size_decrease テスト追加
13. **Integration tests**: JPX × 全 adapter + 4×4 tensor テスト追加

#### Phase 6e: Franke-Westerhoff adapter — commit b51f360
14. **FW Adapter** (`src/prism/adapters/fw.py`): Franke & Westerhoff (2012) 構造的確率モデル
    - fundamentalist/chartist の sentiment-driven switching via transition probabilities
    - tick_size_increase/decrease + transaction_tax 全 3 介入対応
    - k=6 free params, ModelAdapter Protocol 準拠
    - 16 unit tests (protocol, intervention × 3, reproducibility)
15. **Pipeline 拡張**: ADAPTER_REGISTRY に "fw" 追加
16. **Integration tests**: FW × 3 NER + 5×4 tensor テスト追加

### Phase 6 テンソル状態
- **Tensor サイズ**: 5 adapters × 4 NERs × 6 facts = 120 cells
- **Adapters**: SG (k=7), CI (k=9), ZI (k=4), LM (k=8), FW (k=6)
- **NERs**: tspp_2016_us_equity, french_ftt_2012_eu, mifid2_2018_eu_tick, jpx_2014_jp_tick
- **Intervention classes**: tick_size_increase, tick_size_decrease, transaction_tax
- **Facts**: volatility_clustering, leverage_effect, gain_loss_asymmetry, fat_tails, abs_autocorrelation, squared_return_acf
- **テスト**: ~285 tests, all passing
- **品質**: ruff clean, mypy strict (adapter/pipeline modules)

### 既知の課題・改善余地
- NER の ground truth delta は external_claim タグ済み — 生データからの再算出は未実施
- 実市場データ接続のテストは yfinance + network 依存 (CI では skip される可能性)

## Phase 7: ドキュメントと公開準備 — COMPLETE

### 今回のセッションで達成したこと

#### Phase 7a: README, チュートリアル, 図表生成スクリプト — commit 26ccc13
1. **README.md** 拡充: プロジェクト概要、アーキテクチャ図、インストール、Quick Start、
   CLI リファレンス、adapter/NER/fact テーブル、Python API 例、
   新 adapter/NER 追加ガイド、開発手順
2. **docs/getting_started.md**: ステップバイステップ チュートリアル
   - 単一セル実行、テンソル実行、可視化、Python API
   - per-path fact estimation、実市場データ、因果手法比較
   - カスタム adapter 統合ガイド
3. **scripts/generate_paper_figures.py**: 論文用図表バッチ生成
   - 5×4×6 フルテンソル PDF/PNG ヒートマップ + LaTeX テーブル
   - tick-size サブセット PDF + LaTeX テーブル
   - JSON 生の結果出力 (再現性用)
4. **.gitignore**: output/ ディレクトリ追加

#### Phase 7b: pyproject.toml メタデータ + CONTRIBUTING.md — commit 1680b06
5. **pyproject.toml**: readme, classifiers (Science/Research, Financial), keywords, project URLs
6. **CONTRIBUTING.md**: 開発セットアップ、コード品質チェック、adapter/NER/fact 追加ガイド

#### Phase 7c: CI/CD strict化, コード整備, ドキュメント修正 — commits 3e98f9c..48d7467
7. **mypy strict CI**: `viz/latex.py` の型エラー修正 (list→tuple)、`continue-on-error` 削除
8. **CI/CD 分離**: lint (ruff check + ruff format + mypy) と test を別ジョブに分離
9. **ruff format**: 全 22 ファイルにフォーマッタ適用
10. **PEP 561 `py.typed`** マーカー追加
11. **Public API**: `from prism import run_cell, run_tensor` トップレベルエクスポート
12. **FW adapter ラベル**: `ADAPTER_LATEX_LABELS` に "fw" → "FW" 追加
13. **pyproject.toml**: `[viz]` optional dependency (matplotlib), URL を yuitokyouni に修正
14. **ドキュメント修正**: README, getting_started, CONTRIBUTING のプレースホルダー URL 修正、
    format check 手順追加、top-level import 使用

### テスト状態
- **286 tests**, all passing
- ruff check clean, ruff format clean
- mypy strict: 0 errors (26 files)
- pip install -e ".[dev]" OK

#### Phase 7c 追加: LICENSE ファイル — commit 71ca7ad
15. **LICENSE**: MIT ライセンスファイル追加

### generate_paper_figures.py 動作確認 — OK
- 全 6 ステップ完了 (exit code 0)
- 出力: `fig_heatmap_full.pdf` (308K), `.png` (559K), `fig_heatmap_ticksize.pdf` (303K),
  `tab_full_tensor.tex` (4.9K), `tab_ticksize.tex` (3.8K), `tensor_full.json` (102K)
- cells = adapter×NER ペア (5×4=20)、各 cell 内に 6 fact matches

### テスト状態
- **286 tests**, all passing
- ruff check clean, ruff format clean
- mypy strict: 0 errors (26 files)

## Phase 8: テスト充実とCI強化 — COMPLETE

### 今回のセッションで達成したこと

#### Phase 8a: CLI テスト + カバレッジ閾値 — commit 3ada3c3
1. **CLI テスト** (`tests/unit/test_cli.py`): 28 tests
   - `build_parser()` 全 7 サブコマンドのパース確認
   - `resolve_fact_ids()` エイリアス解決 6 テスト
   - `resolve_ner_path()` ファイル検索 3 テスト (mock 使用)
   - `main()` 全 7 コマンドディスパッチ (pipeline mock)
   - CLI module coverage: 0% → 99%
2. **85% カバレッジ閾値**: CI + pyproject.toml に `--cov-fail-under=85` 追加

#### Phase 8b: market_data テスト改善 — commit d2476f3
3. **market_data モック テスト** 5 tests 追加
   - ImportError (yfinance 未インストール), empty data, insufficient data, multi-ticker
   - network 不要で CI 安定性向上
   - market_data.py coverage: 83% → 94%+

#### Phase 8c: CI 拡張 + コード品質 — commits fa06f38, f5486a2, 49203e2, debb914, 59c964c
4. **Python 3.13** CI テストマトリクスに追加 + pyproject.toml classifier
5. **dead code 除去**: `SimulatedMarketData.to_market_data()` (未使用メソッド)
6. **警告抑制**: pytest / generate_paper_figures.py で scipy/protobuf 警告を非表示
7. **.gitignore**: `.coverage`, `htmlcov/` 追加
8. **CONTRIBUTING.md**: 85% カバレッジ要件の記載追加

### テスト状態
- **314 tests** (unit: 259, integration: 55), all passing
- ruff check clean, ruff format clean
- mypy strict: 0 errors (26 files)
- coverage: ≥86% (unit only), ≥89% (full suite)
- `pip install -e ".[dev,viz]"` OK
- `prism --help`, `from prism import run_cell, run_tensor` OK

## Phase 9: テスト強化 + API ドキュメント + v0.1.0 — COMPLETE

### 今回のセッションで達成したこと

#### Phase 9a: pipeline.py ユニットテスト — commit fc0088a
1. **pipeline ユニットテスト** (`tests/unit/test_pipeline.py`): 32 tests
   - `CellOutput.summary()`: eligibility/weighted/unweighted/magnitude 表示 9 tests
   - `CellOutput.to_dict()`: serialization 各分岐 6 tests
   - `TensorOutput.summary()`: ineligible/divergence 検出 3 tests
   - `TensorOutput.to_dict()`: 構造確認 1 test
   - `MethodComparisonOutput.summary()` + `to_dict()`: 2 tests
   - `run_cell()`: mock adapter, per_path, pre_data, error 4 tests
   - `_compute_per_path_facts()`: basic + NaN 2 tests
   - `run_tensor()` + `compare_causal_methods()`: mock 3 tests
   - `ADAPTER_REGISTRY`: 全 adapter 存在 + instantiate 2 tests
   - **coverage**: pipeline.py 25% → 99%, 全体 86% → 97%

#### Phase 9b: v0.1.0 + pdoc API ドキュメント — commit 27b4005
2. **Version bump**: 0.0.1 → 0.1.0 (pyproject.toml + `__init__.py`)
3. **pdoc API docs**: `scripts/generate_api_docs.py` (HTML生成 + ライブサーバ)
4. **`[docs]` optional dependency**: pdoc>=14.0
5. **CONTRIBUTING.md**: ドキュメント生成手順追加
6. **.gitignore**: `docs/api/` 追加

#### Phase 8 handoff 確認
- `generate_paper_figures.py` 出力で "FW" ラベル確認済み (LaTeX テーブル 4行)
- Phase 8 → COMPLETE

### テスト状態
- **351 tests** (unit: 291, integration: 55+), all passing
- ruff check clean, ruff format clean
- mypy strict: 0 errors (26 files)
- coverage: ≥97% (unit only), ≥97% (full suite)
- `pip install -e ".[dev,viz]"` OK
- `prism --help`, `from prism import run_cell, run_tensor` OK
- `python scripts/generate_api_docs.py` OK

### ブロッカー
- なし

### 次回セッションで最初に実行すべきこと
1. フルテストスイート実行確認 (`pytest --cov=prism --cov-fail-under=85`)

### 次の目標 (Phase 10 候補)
1. GitHub Release v0.1.0 作成 (タグ + リリースノート)
2. CI に API ドキュメント生成ステップ追加
3. GitHub Pages でのドキュメント公開
4. PyPI テスト公開 (test.pypi.org)
