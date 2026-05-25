# Current Progress
- プロジェクト初期化完了（ハーネス設定済み）。
- PRISM要件定義書（v0.1）を `docs/PRISM_REQUIREMENTS.md` として配置完了。
- **WP0 完了:**
  - `docs/WP0_RESEARCH_REPORT.md` 作成・コミット済み。
  - 文献レビュー: LOB-Bench, ABM-FTT文献, Collver (2017, SEC DERA) を最も近い先行研究として特定。新規性を確認。
  - データ可用性: 無料 FINRA/SEC パイロットデータで日次頻度MVPファクト（vol clustering, leverage, gain/loss）計算可能。
  - §12 オープン論点5項目に対する仮決定を記録。
  - プロジェクト・スキャフォールディング完了 (`src/prism/`, `tests/`, `data/`, `scripts/`, `pyproject.toml`)。

## 次の目標 (Mission 2: Phase 1 — 単一セル end-to-end)

要件定義書 §8 Phase 1 に従い、SG × Tick Size Pilot × {leverage, vol clustering, gain/loss} の単一セルを end-to-end で実装し、第三者が `prism run` で同一 Δ を再現できる状態にする。

### 具体的なアクションアイテム
1. **データ取得パイプライン**
   - FINRA パイロット証券リスト（treatment/control 割当）をダウンロードするスクリプト作成
   - SEC MIDAS または Yahoo Finance から日次価格データを取得するスクリプト作成
   - `data/ner/tspp_2016_us_equity.yaml` として NER #1 を構築

2. **Fact Estimator Library v0.1** (`src/prism/facts/`)
   - `volatility_clustering`: GARCH(1,1) persistence パラメータ (α+β)
   - `leverage_effect`: EGARCH leverage パラメータ or Corr(r_t, |r_{t+τ}|²)
   - `gain_loss_asymmetry`: return distribution skewness
   - 実データ・模擬データに同一実装を適用する契約を enforced

3. **SG Adapter** (`src/prism/adapters/sg.py`)
   - Katahira et al. (2019) の Speculation Game を ModelAdapter Protocol に準拠して実装
   - `calibrate_baseline`, `apply_intervention` (tick size → cognitive threshold), `simulate`

4. **Scorer v0.1** (`src/prism/scoring/`)
   - 符号一致 (sign consistency) チェック
   - 大きさ (magnitude within ci95) を confidence 付き副指標として報告

5. **Provenance Layer v0.1** (`src/prism/provenance/`)
   - データハッシュ、コードバージョン、RNG seed の記録
   - W3C PROV 最小実装

6. **CLI + End-to-end**
   - `prism run --adapter sg --ner tspp_2016 --facts leverage,volclust,gainloss`
   - 結果を再現可能アーティファクトとして出力

### 終了条件
- `prism run` が実行でき、1つの result cell (SG × tick_size × 3 facts) を生成する。
- 符号一致の可否が出力される。
- provenance 情報が result に含まれ、同一 seed で同一結果が再現される。
- 次の目標を Phase 2 準備に更新した上で `progress.md` を上書き保存。
