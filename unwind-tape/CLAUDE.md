# CLAUDE.md — unwind-tape / 標準事実のみ
<!-- 「動かない事実」だけ。手順・スニペットは書かない。 -->

## What this is
日本株の「一定期間内解消(unwind)」イベントを組成する tape 研究プロジェクト。groups.csv(イベント群) と legs.csv(各 leg = 個別公表) を突合し、AR/CAR を出す。データ基盤 3 タスクの構成:

- **A. JPX 立会外取引情報の日次キャプチャ** (実装済・cron 化予定)
- **B. xlsx → CSV 正規化 + PDF アーカイバ** (v0.2 xlsx 供給待ち)
- **C. J-Quants で日次四本値 + AR/CAR エンジン** (B 依存)

進捗と受け入れ条件の一次情報は `HANDOFF.md`。

## Stack / entrypoints
- 言語/環境: Python 3.11+。依存: `requests`, `openpyxl`, `PyYAML`, stdlib (Task A のみ現状)。
  以後 B/C で `pandas`, `pyarrow` が追加。他リポパッケージへ import しない。
- Task A entrypoint: `unwind-tape/scripts/fetch_jpx_offauction.py` (単体で完結)
- Task A config: `unwind-tape/configs/jpx_offauction.yaml`
- Task A cron 例: `unwind-tape/cron/jpx_offauction.crontab`

## Conventions
- **データ創作は厳禁**。欠損は空欄のまま、`data/gaps_report.md` に列挙。
- raw は加工前の原本(取得ファイルそのまま)を保存。sha256 を manifest.jsonl に必ず追記。
- パース済み CSV は raw の全列を保持。派生列は `_` プレフィックス(例: `_publication_date_iso`, `_row_hash`)。
- **構造変化検知**: 想定カラムと不一致なら raw のみ保存し、manifest に `schema_mismatch` として記録して非0終了。黙って空を書かない。
- CSV 追記は natural_key での dedupe。tostnet は publication_date 単位で丸ごと入替 (whole-file replace)。
- タイムゾーンは Asia/Tokyo。日付キーは `YYYY-MM-DD` (ISO 8601)。
- **他コードにimport依存させない**: Task A スクリプトは `unwind-tape/scripts/` の内部だけを import する。`packages/`, `src/fabm` からも独立。

## Where the truth lives
- 進捗・受け入れ条件: `HANDOFF.md`
- Task A 設定: `configs/jpx_offauction.yaml` (`expected_columns` / `expected_headers` は schema-change 検知の宣言。ここを変えない限り黙って通ることはない)
- Task A manifest: `data/raw/jpx_offauction/{page}/manifest.jsonl` (append-only ledger、sha256 込み)
- Task A gaps: `data/gaps_report.md` (欠損・schema 不整合・取得失敗の履歴)
- Task B/C の PREREG (推定窓・day 0 規則): C 実装時に `PREREG.md` を追加(空テンプレートのみ Claude 作成、中身はユーザが記述)

## Task A Fixed Invariants
<!-- 実装で絶対に落とすな。 -->
- **raw 保存**: `data/raw/jpx_offauction/{page}/{YYYY-MM-DD}/` 直下。日付キーは tostnet=publication_date, HTML 2ページ=capture_date (JST)。
- **冪等**: 同一 sha256 が manifest に status=ok で存在するなら parsed CSV への再書込を行わない (skipped_duplicate として manifest には残す)。
- **リトライ**: 指数バックオフ (base=2s, factor=2, retries=4)。
- **schema-change 検知**: (i) tostnet xlsx は header 完全一致 (順序含む)、(ii) HTML 2ページは `expected_headers` が対象 table の flatten 済み `<th>` 集合の subset。不一致は raw だけ保存し `schema_mismatch` で非0終了。
- **HTTP UA**: 明示ヘッダ("unwind-tape-fetch/0.x ...")。JPX は素の Python UA を 403 する。
- **stdlib HTML parser のみ**: bs4/lxml 依存を持たない。パーサ差替時は _TableCollector の rowspan 挙動を再検証する。

## Runtime layout
```
unwind-tape/
  CLAUDE.md, HANDOFF.md, README.md
  configs/jpx_offauction.yaml
  scripts/fetch_jpx_offauction.py
  cron/jpx_offauction.crontab
  data/                      # .gitignore 対象(生データ)
    raw/jpx_offauction/{page}/manifest.jsonl
    raw/jpx_offauction/{page}/{YYYY-MM-DD}/*.{xlsx,html}
    parsed/jpx_offauction/{page}.csv
    gaps_report.md            # コミット対象
    logs/jpx_fetch_YYYY-MM-DD.log
```
