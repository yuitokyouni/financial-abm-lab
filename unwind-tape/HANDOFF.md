# unwind-tape — HANDOFF

**最終更新**: 2026-07-07 JST (Task A cron待ち / Task B **v0.4 pipeline 完了 (validator errors=0 warnings=0)**)

## Task 状況

| Task | Status | Blocker | 一次成果物 |
|------|--------|---------|------------|
| **A** JPX 立会外取引 日次キャプチャ | ✅ 実装完了、初回バックフィル成功、**cron 未デプロイ** | Lane B cron へ登録 | `scripts/fetch_jpx_offauction.py` |
| **B** xlsx → CSV 正規化 + PDF アーカイバ + build round-trip | ✅ v0.4 pipeline 完了 (**validator errors=0 warnings=0**) | — | `scripts/{migrate_xlsx_to_csv,validate_tape,archive_pdfs,build_tape}.py` |
| **C** J-Quants + AR/CAR エンジン | ⏸ 未着手 | ユーザ着手指示 | 予定: `docs/j_quants_plan_report.md` → `scripts/car_engine.py` |

---

## Task A — 完了エビデンス

### 実装

- **単体スクリプト**: `unwind-tape/scripts/fetch_jpx_offauction.py`
- **設定**: `unwind-tape/configs/jpx_offauction.yaml` (`expected_columns`/`expected_headers` が schema-change 検知の宣言アンカー)

### 対象 3 ページ

| Page key | 形式 | Schema 検証 |
|----------|------|-------------|
| `tostnet_large_lots` | 日次 xlsx | header 完全一致 |
| `offauction_distribution` | HTML rowspan=2 | `<th>` subset (空白除去して比較) |
| `buyback_ownshares` | HTML simple | `<th>` subset |

### バックフィル結果 (2026-07-07)

```
tostnet_large_lots     : ok_files=10  new_rows=78
offauction_distribution: ok_files=1   new_rows=3
buyback_ownshares      : ok_files=1   new_rows=11
```

冪等再実行で全 dup、exit=0。

### cron デプロイ手順 (Lane B オペレータ向け)

このリポは remote container で走らせている都合、cron 常駐ができない。ホスト側 Lane B に登録する。

1. Lane B ホスト上で working copy を用意 (branch: `claude/unwind-tape-data-foundation-0txm6z`)
2. python3.11+ / `requests` / `openpyxl` / `PyYAML` を確保
3. `unwind-tape/cron/jpx_offauction.crontab` を参考に登録 (推奨: 毎日 21:00 JST)
4. exit != 0 のとき通知が届くことを確認

### 障害復旧

- **一時的 5xx**: 翌日の cron 実行で自動リカバリ。log に警告のみ。
- **schema 不整合**: raw は保存済み。`configs/jpx_offauction.yaml` を更新 → 手動再実行。
- **2週間 gap** (掲載消滅後の復旧): raw は保存済みだが、Task A 単体ではリカバリ不可。**Lane B が動いていることが唯一の防波堤。**

---

## Task B — 完了エビデンス

### スクリプト構成 (パイプライン)

```
inputs/tape_versions/v0.3/policy_holding_sale_event_tape_v0_3.xlsx   ← ユーザ供給
inputs/pdfs_supplied/S00X__*.pdf (×10)                               ← ユーザ供給 + 初回DL pin
                          ↓
scripts/migrate_xlsx_to_csv.py    # xlsx → CSV (one-time; v0.4+ 以降は build_tape で逆方向)
                          ↓
data/parsed/tape/{groups,legs,sources}.csv, lists.yaml,
                 field_dictionary.csv, sampling_frame.csv,
                 baseline_spec.csv, changelog.csv, readme.yaml,
                 migration_report.md
                          ↓
scripts/archive_pdfs.py           # sources.csv の URL を data/raw/pdfs/ へ (seed from supplied 優先)
                          ↓
data/raw/pdfs/{S001..S011}__*.{pdf,html}, manifest.jsonl
                          ↓
scripts/validate_tape.py          # enum / bool / FK / date order / basis consistency / source_id required
                          ↓
data/parsed/tape/validate_report.md
                          ↓
scripts/build_tape.py             # CSV → xlsx (regenerate; validator を pre-check)
                          ↓
data/parsed/tape/policy_holding_sale_event_tape_regenerated.xlsx
```

### CSV スキーマ (v0.3 → CSV)

- **groups.csv** (11 行): `event_group_id, issuer_code, issuer_name, issuer_market, event_tier, confidence_policy_holding, ABM_candidate_flag`
- **legs.csv** (12 行, 64 列): `event_group_id` (FK) → その他 v0.3 の 63 列
  + 派生列 `source_id_primary`, `source_id_secondary` (URL 逆引き)
- **sources.csv**: Source_Log 全列 + `local_path, sha256, bytes, fetched_at` (archiver が埋める)
- **lists.yaml**: 12 enum family (`status`, `event_tier`, ..., `bool`)

### v0.4 で v0.3 から解消された指摘

v0.4 Changelog **C026** と **C027** で以下2点が修復された:

1. **C026 URL truncation バグ**: v0.2 生成時に 80 字＋`...` に切り詰められていた 27 セル (URL 6・seller_name 3・route_notes/mechanism/notes 18) が v0.1 原本から復元された → prefix match による auto-resolve は不要になり、URL は完全な文字列で legs.csv に載る。
2. **C027 Source_Log ギャップ**: 未登録 URL 6 件が **S012-S017** として登録された。validator の warnings=2 (v0.3) は **warnings=0** (v0.4) になった。

### 現在の migration 観測結果 (v0.4)

- **CSV rows**: groups=11, legs=12, sources=**17** (v0.3=11 から +6)
- **truncated-URL auto-resolves**: 0 (v0.3=3 から解消)
- **unresolved URLs**: 0 (v0.3=6 から解消)
- **group column promotion 方針は v0.3 と同じ**: identity 3 列 + `event_tier` + `confidence_policy_holding` + `ABM_candidate_flag` の 6 列(+PK)。`mechanism_hypothesis` と `activist_pressure` は leg 単位で異なり得るので legs.csv に残す。

### validator 結果 (errors=0, warnings=0)

**clean.** ハードコード数値セルはすべて Source_Log の source_id に解決済み。

### PDF アーカイブ結果 (14/17 成功)

`inputs/pdfs_supplied/` に 14 件を pin (7 件ユーザ供給 + 7 件初回 DL を保存):

| source_id | 対応 leg | 状態 |
|-----------|----------|------|
| S001 | (legal memo) | seeded from supplied |
| S002 | JPX 自己株式取得想定質問 (df1f5177) | seeded from supplied |
| S003 | G004 Honda | seeded (初回DL pin) |
| S004 | G003 Aisin | seeded from supplied |
| S005 | G002 DENSO/Toyota Industries | seeded from supplied |
| S006 | G005 Kaga Electronics | seeded from supplied |
| S007 | G008 Nintendo secondary | seeded (初回DL pin) |
| S008 | G008 Nintendo buyback | seeded from supplied |
| S009 | G008/L002 DeNA (Yahoo CDN) | seeded from supplied |
| S010 | Nintendo Reuters | **HTTP 401** (paywall) |
| S011 | Nintendo 有報 | seeded (初回DL pin) |
| S012 | G006 The Pack | seeded (v0.4初回DL pin) |
| S013 | G007 Daikyo Nishikawa | seeded (v0.4初回DL pin) |
| S014 | G001 Toyota Industries index.html | seeded (v0.4初回DL pin) |
| S015 | Reuters Aisin | **HTTP 401** (paywall) |
| S016 | Reuters Honda | **HTTP 401** (paywall) |
| S017 | G008/L002 Yahoo CDN secondary | seeded (v0.4初回DL pin) |

**14/17 archived、3 件 (S010/S015/S016 = すべて Reuters) は paywall で 401**。Reuters は gaps_report.md に列挙。

manifest: `data/raw/pdfs/manifest.jsonl` (sha256 + bytes + captured_at)

### 過去バージョン参照 (v0.3)

v0.3 pipeline も同じスクリプトで走る:
```
python3 scripts/migrate_xlsx_to_csv.py \
    --xlsx inputs/tape_versions/v0.3/policy_holding_sale_event_tape_v0_3.xlsx \
    --version-tag v0.3
```
既定は v0.4。

### 完了条件チェック

1. ⏸ Task A cron 未登録 (Lane B)
2. ✅ `build_tape.py` が CSV→xlsx を再現的に生成、**validator errors=0 warnings=0** で通過。value-level diff vs original v0.4: 17 行の差分すべて説明可 (`archived` 列を archiver が TRUE に更新した14箇所 + 時刻フォーマット/bool 大小文字 3箇所)。
3. ⏸ G004 (Honda) と G008 (Nintendo) の CAR — 価格データ未取得のため Task C 完了までペンディング
4. ✅ HANDOFF.md 更新 (このファイル)

---

## Task C — 待機事項

Task B が Ready 状態になった時点で C 着手可能。**着手指示待ち**。

**最初にやること (実装前)**:
- `docs/j_quants_plan_report.md` を作成
- J-Quants プラン別提供範囲 (遅延・期間・料金) を公式ページから確認
- 本件 (2023 年以降の日次四本値・出来高、対象銘柄 = 12 legs の issuer × TOPIX) に必要な最小プランを結論として書く
- 実装はその後

**実装内容 (spec)**:
- `ADV20` / `ADV60` / 時価総額 → `legs_computed.csv`
- **AR/CAR エンジン**: TOPIX 調整と market-model (推定窓 `[-140, -21]` 営業日) の両方実装、config 切替。本採用は `PREREG.md` に記載 (**Claude は空テンプレートのみ作成**)
- **day 0 規則**: `after_close=TRUE` の行は翌営業日を day 0 とする。推定窓・計算にルックアヘッド禁止
- **出力列**: `announcement_CAR_m1_p1`, `announcement_CAR_0_p1`, `drift_ann_to_pricing`, `pricing_CAR_m1_p1`, `settlement_CAR_m1_p1`, `recovery_5d/20d/60d`, `abnormal_volume_0_p3`

**Ready 直前アクション (推奨)**:
- Source_Log に S012 (The Pack) と S013 (Daikyo Nishikawa) を追加 → validator warnings=0 化
- v0.4+ xlsx を作るなら URL truncation バグを修復してから

---

## 運用メモ

### CSV が canonical になった以降のワークフロー

1. **CSV 直接編集** (推奨): `data/parsed/tape/legs.csv` などを手で編集 → `scripts/validate_tape.py` → `scripts/build_tape.py` で xlsx 再生成
2. **xlsx 経由** (別途 GUI 編集したいとき): 新 xlsx を `inputs/tape_versions/v0.X/` に置く → `scripts/migrate_xlsx_to_csv.py --xlsx ... --version-tag v0.X` で再取り込み。**⚠ sources.csv の `archived` 状態が消えるので直後に `scripts/archive_pdfs.py` を再実行すること。**

### 追加 PDF を pin する方法

1. `unwind-tape/inputs/pdfs_supplied/S0XX__{descriptive_name}.pdf` に配置
2. `unwind-tape/inputs/pdfs_supplied/manifest.jsonl` に 1 行追記 (sha256, source_id, kind=`pdf_downloaded_then_pinned` or `pdf_supplied_by_user`)
3. `scripts/archive_pdfs.py` を実行 → sources.csv の該当行が `archived=TRUE` に更新される

### 完了条件 (原文リマインダ)

1. ⏸ Task A がスクリプトとして完成、初回バックフィルのログと manifest が確認可能 (**残: cron へ登録**)
2. ✅ `build_tape.py` が CSV→xlsx を再現的に生成、バリデーション全通過
3. ⏸ G004(ホンダ) と G008(任天堂) の CAR が手計算と一致 (Task C)
4. 🔁 HANDOFF.md 更新 (このファイル)
