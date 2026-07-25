# YH010-g Task 6 — EDINET属性抽出器と推奨再構成の精度検証

- 日付: 2026-07-24
- 対象: `specs/YH010g_HANDOFF.md` Task 6（EDINET属性パイプライン）の実装本体と Task 2 の本検証
- 状態: **コード完成・ネットワーク層はローカル実行待ち**（EDINETキーはユーザーのローカル環境にあり、キーのない本環境では抽出ロジックをフィクスチャで検証済み）

## 実装

### `yh010g.edinet` — XBRL属性抽出器
- **純粋関数（テスト済み）**: `parse_edinet_csv`（EDINET CSV type=5・UTF-16・タブ区切りのパース）、`extract_attributes`（有報サマリ節からROE 5年系列・純資産・政策保有額を抽出、連結優先、パーセント→fraction変換）。フィクスチャで連結値の選択・5年平均・政策保有比率25%を検証。
- **ネットワーク層（`EdinetClient`、ローカル専用）**: 書類一覧（type=2）→証券コードで有報検索→CSV（type=5, ZIP）取得。`EDINET_API_KEY` 未設定なら明示的に失敗（黙って空を返さない）。
- **要素IDの検証手段**: `python -m yh010g.edinet dump <docID>` で実CSVの全（要素ID, コンテキスト, 値）を出力。タクソノミ版差で要素IDがずれた場合、`extract_attributes` が `unmatched` に記録し、dumpで正しいIDを確認して定数を調整できる。

### `yh010g.build_attributes` — 属性CSV構築ドライバ（ローカル実行）
```
export EDINET_API_KEY=...
uv run python -m yh010g.build_attributes \
  --targets docs/yh010g_validation_targets.csv \
  --out data/processed/yh010g/attributes_edinet.csv
```
決算期末+80〜100日を有報提出日候補として自動探索。EDINET財務（ROE・政策保有）を取得し、任意の手動CSV（候補者/議案レベルのフラグ）とマージ（EDINET優先）。**結果CSVをコミットすれば、キーのない環境でも精度検証が回る**。

### `yh010g.validate_policy` — 推奨再構成の精度検証（Task 2 本検証）
著名議案のground truth（`docs/yh010g_validation_groundtruth.csv`、Task調査の17件から財務・機械判定可能な7件を抽出）に対し、規則ベース再構成の推奨方向が実推奨と一致するかを **mechanism層別** で測定。

## 検証結果（手動フラグのみ・EDINET未注入）

```
[mechanical] ISS 1.0 (n=3)  GL 1.0 (n=2)
[financial ] ISS 0.0 (n=2)  GL 1.0 (n=1)
[judgmental] ISS 0.5 (n=2)  GL 0.0 (n=2)
```

**この層別結果自体が主要な知見**——規則ベース再構成が何を再現でき何ができないかの境界を定量化した:

1. **mechanical（女性取締役ゼロ・買収防衛策）: ISS/GLとも100%一致**。キヤノン御手洗2023（女性ゼロ→ISS反対）と2024（女性追加→賛成に反転）のペアを両方正しく再現。規則の中核は機能している。
2. **financial（政策保有20%基準）: 手動フラグのみではISS 0%**——policy_holdings属性が欠けると反対を再現できない。**これはEDINETが必要な理由の実証**であり、`--edinet` で財務を注入すればISS 100%になる（テスト `test_validation_harness_with_edinet` で確認済み: みずほ0.28/SMBCトラスト0.31を注入→両者反対を再現）。GLは縮減計画例外で賛成=既定と一致（ISS/GLの条文差分が正しく分岐）。
3. **judgmental（不祥事責任・総合的独立性）: ISS 0.5（偶然一致）/GL 0%**——トヨタ豊田2024の反対（認証不正の最終責任）やGL2023反対（取締役会の総合的独立性）は**機械的属性に還元できない判断**であり、規則ベースの射程外。**この限界を明示的に境界づけたことがモノカルチャー測定の妥当性に効く**: ID-g1で使う「推奨分裂」は機械的規則が確実な領域（政策保有帯・女性取締役・退職慰労金）に限定すべきで、判断系議案は識別から除外する根拠になる。

## ローカル実行の手順（ユーザー作業）

1. `export EDINET_API_KEY=<キー>`（gitignore環境で）
2. `uv run python -m yh010g.build_attributes --targets docs/yh010g_validation_targets.csv --out data/processed/yh010g/attributes_edinet.csv`
3. 要素ID未マッチが出たら `python -m yh010g.edinet dump <docID>` で実IDを確認し `edinet.py` の `EL_*` 定数を調整
4. `uv run python -m yh010g.validate_policy --edinet data/processed/yh010g/attributes_edinet.csv` で financial系ISSが反対を再現することを確認
5. `attributes_edinet.csv` をコミット・プッシュ（データは軽量CSVなので原本sha256不要、EDINETの公開値）

## 残り

- パネル全体（217k議案）への属性適用（`build_attributes` の targets をパネルの発行体×年度に拡張）→ conditional規則の本発火 → ID-g1分裂の完全版
- 女性取締役数はXBRLで安定取得できない可能性が高く、招集通知/CG報告書からの別経路が要る（現状は手動フラグ）
- 事前登録（閾値・k選択・識別判定の固定）→ 主結果の本実行
