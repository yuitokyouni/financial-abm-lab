# CLAUDE.md — unwind-tape / 標準事実のみ
<!-- 「動かない事実」だけ。手順・スニペットは書かない。 -->

## What this is
**研究 ID = YH009**(YH シリーズの新規ライン。YH001-008 は ABM シミュレーションだが、
YH009 は実データの経験的イベントスタディで別系譜。マスター台帳:
`imported/speculation-game-info/docs/findings.md`)。

日本株の「一定期間内解消(unwind)」イベントを組成する tape 研究プロジェクト。groups.csv(イベント群) と legs.csv(各 leg = 個別公表) を突合し、AR/CAR を出す。データ基盤 3 タスクの構成:

- **A. JPX 立会外取引情報の日次キャプチャ** (実装済・cron 化予定)
- **B. xlsx → CSV 正規化 + PDF アーカイバ + build round-trip** (v0.3 で完了)
- **C. J-Quants で日次四本値 + AR/CAR エンジン** (B 完了、着手指示待ち)
- **D. EDINET 母集団拡張** (売出し系書類を網羅発見 → Nゲート ≥30 へ。step1=候補抽出 実装済、step2=本文分類 未)

進捗と受け入れ条件の一次情報は `HANDOFF.md`。新規性と設計不変条件は `docs/CONTRIBUTION.md`。

## 設計判断の3問(`docs/CONTRIBUTION.md` §5 の短縮形。設計を変えるたびに問う)
1. この変更は差分表(研究対象/実測値/検証のしかた)のどの行を毀損するか?
2. 退化経路 D1(単一方式化)/D2(SF回帰)/D3(違いの検証を後回し)のどれかに近づくか?
3. 凍結spec(s1/s2/s3・IS_adj・Nゲート・s3の方式間比較禁止)と矛盾しないか?
→ いずれか YES なら「一時簡略化」と明示するか設計を戻す。恒久化は不可。
用語: 「売却方式」= 売出し/立会外分売/ToSTNeT-3 等(spec の `sale_route`。旧「ルート/ベニュー」)。

## Stack / entrypoints
- 言語/環境: Python 3.11+。依存: `requests`, `openpyxl`, `PyYAML`, stdlib。
  Task C で `pandas`, `pyarrow`, J-Quants HTTP client を追加予定。他リポパッケージへ import しない。
- Task A entrypoint: `unwind-tape/scripts/fetch_jpx_offauction.py` (単体で完結)
- Task A config: `unwind-tape/configs/jpx_offauction.yaml`
- Task A cron 例: `unwind-tape/cron/jpx_offauction.crontab`
- Task B pipeline: `migrate_xlsx_to_csv.py` → `archive_pdfs.py` → `validate_tape.py` → `build_tape.py`
- Task B canonical CSVs: `unwind-tape/data/parsed/tape/{groups,legs,sources}.csv, lists.yaml`
- Task C: `jquants_fetch.py` → `car_engine.py`(系統A CAR) / `shortfall_engine.py`(系統B shortfall, spec `MEASUREMENT_SPEC.md`, config `configs/car.yaml` の `shortfall:` 節)
- TCA残差: `residual_engine.py`(実測 vs √則, spec `docs/TCA_BASELINE_SPEC.md`, config `configs/tca.yaml`)。√則の非線形テストは **`implied_Y_s2 = s2/(σ√(Q/V))`** を主に見る(s3=発行ディスカウント層は別掲)。N<30 は記述のみ。
- Task D: `edinet_fetch.py`(EDINET売出し系書類の網羅発見=候補抽出, config `configs/edinet.yaml`, 設計 `docs/TASK_D_DESIGN.md`)。key=env `EDINET_API_KEY`。step2(本文分類/政策保有判定)は未実装。`data/raw/edinet` は git外。
- BENCHMARK: `benchmark_engine.py`(無条件 exec_gap 参照分布, spec `BENCHMARK_SPEC.md`, config `configs/benchmark.yaml`)。**tape 非混入**の対照分布。生バーは `data/raw/prices/`(git外)。
- 転記: `transcription/disclosure_transcription.csv`(埋めるだけ)+ `scripts/apply_transcription.py`(検証→legs.csv 反映)。disclosure_time/pricing/offer/OA を一次資料から。**推定禁止・空欄は fail-loud 維持**。ガイド `transcription/README.md`。

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

## Task B Fixed Invariants
- **CSV が一次データ**: v0.3 以降、xlsx は `build_tape.py` の生成物。CSV を直接編集して build する運用。
- **group 昇格の原則**: 全 leg で不変な identity 系のみ groups.csv に置く。leg 間で異なり得る解釈 (mechanism_hypothesis / activist_pressure) は legs.csv に残す。昇格判定は `migrate_xlsx_to_csv.py` の `GROUP_COLUMNS` にハードコード。
- **URL 保全**: xlsx の URL が truncated (末尾 `...`) でも、source_id は prefix match で解決するが URL 文字列自体は truncated のまま legs.csv に残す (**データ創作禁止**)。
- **数値埋まり + source_id 必須** (Tier1_confirmed のみ): URL のみで source_id 未解決なら validator が WARN → Source_Log への追加を促す。
- **basis 整合性**: `quantity_basis/value_basis=resolution_max` のとき `sold_shares × previous_close_JPY ≤ sold_value_JPY × 1.01` を検証 (価格が揃わないケースは skip)。
- **PDF アーカイブ**: 供給 PDF は `inputs/pdfs_supplied/` に pin。archiver は seed 優先 → HTTP fallback。sha256 は `data/raw/pdfs/manifest.jsonl` に (Reuters 401 等の失敗は gaps_report.md へ)。
- **build_tape 前 validate**: `build_tape.py` は先に `validate_tape.py` を呼び、ERROR ありなら xlsx 生成を abort。WARN のみなら生成する。

## Runtime layout
```
unwind-tape/
  CLAUDE.md, HANDOFF.md, README.md, .gitignore
  configs/jpx_offauction.yaml
  scripts/
    fetch_jpx_offauction.py       # Task A
    migrate_xlsx_to_csv.py        # Task B: 一次移行 (xlsx→CSV)
    archive_pdfs.py               # Task B: sources.csv URL → data/raw/pdfs/
    validate_tape.py              # Task B: enum/FK/date order/basis/source_id
    build_tape.py                 # Task B: CSV→xlsx round-trip
  cron/jpx_offauction.crontab
  inputs/                         # git-tracked (ユーザ供給の source of truth)
    tape_versions/v0.3/policy_holding_sale_event_tape_v0_3.xlsx
    pdfs_supplied/{S0XX}__*.pdf   # 供給PDF + 初回DL pin (10件)
    */manifest.jsonl              # sha256 込み
  data/                           # 一部 gitignore
    raw/
      jpx_offauction/{page}/…    # gitignored (Task A の生成物、成長する)
      pdfs/{S0XX}__*.{pdf,html}  # git-tracked (Task B アーカイブ、10件+manifest)
    parsed/
      jpx_offauction/*.csv        # gitignored
      tape/                       # git-tracked (Task B canonical CSV)
        groups.csv, legs.csv, sources.csv, lists.yaml,
        field_dictionary.csv, sampling_frame.csv, baseline_spec.csv,
        changelog.csv, readme.yaml,
        migration_report.md, validate_report.md,
        policy_holding_sale_event_tape_regenerated.xlsx  # gitignored
    logs/                         # gitignored
    gaps_report.md                # git-tracked (欠損履歴)
```
