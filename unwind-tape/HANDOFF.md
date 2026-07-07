# unwind-tape — HANDOFF

**最終更新**: 2026-07-07 JST (Task A cron待ち / Task B **v0.4 pipeline 完了 (validator errors=0 warnings=0)**)

## Task 状況

| Task | Status | Blocker | 一次成果物 |
|------|--------|---------|------------|
| **A** JPX 立会外取引 日次キャプチャ | ✅ 実装完了、初回バックフィル成功、**cron 未デプロイ** | Lane B cron へ登録 | `scripts/fetch_jpx_offauction.py` |
| **B** xlsx → CSV 正規化 + PDF アーカイバ + build round-trip | ✅ v0.4 pipeline 完了 (**validator errors=0 warnings=0**) | — | `scripts/{migrate_xlsx_to_csv,validate_tape,archive_pdfs,build_tape}.py` |
| **C** J-Quants + AR/CAR エンジン | 🟡 **コード完備、Mac で run 待ち** (G004/G008 手計算突合が完了条件残) | ユーザ Mac 側の J-Quants fetch 実行 | `scripts/{jquants_fetch,car_engine}.py`, `configs/car.yaml`, `docs/j_quants_plan_report.md`, `docs/macos_runbook_task_c.md`, `PREREG.md` |

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

### cron デプロイ手順 (macOS ユーザ向け)

このリポは remote container で走らせている都合、cron 常駐ができない。手元の macOS に登録する。

**推奨: 一発セットアップスクリプトを使う**

```bash
cd path/to/financial-abm-lab

# 1. まず手動で 1 回走らせて成功することを確認
python3 unwind-tape/scripts/fetch_jpx_offauction.py

# 2. crontab に登録 (dry-run で内容を見て、OKなら --install)
bash unwind-tape/cron/setup_macos_cron.sh                # 何が入るか見るだけ
bash unwind-tape/cron/setup_macos_cron.sh --install      # 実際に crontab -e 相当を実行

# 3. 確認
crontab -l
```

**macOS 特有の必須設定**:
1. **Full Disk Access**: System Settings > Privacy & Security > Full Disk Access に `/usr/sbin/cron` を追加。付けないと raw ファイル書き込みで "Operation not permitted"。
2. **スリープ対策** (以下いずれか):
   - Prevent auto-sleep をON、または
   - `sudo pmset repeat wakeorpoweron MTWRFSU 20:55:00` で発火 5 分前に wake、または
   - launchd 版に切り替え (`bash unwind-tape/cron/setup_macos_launchd.sh --install`) — スリープでロスした発火を起床時にキャッチアップする

**launchd 派の人向け** (スリープ耐性◎):
```bash
bash unwind-tape/cron/setup_macos_launchd.sh --install
launchctl list | grep com.unwind-tape.jpx    # 登録確認
```
plist は `~/Library/LaunchAgents/com.unwind-tape.jpx.plist` に置かれる。

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

## Task C — コード完備 (Mac 実行待ち)

### 完了したもの

- `docs/j_quants_plan_report.md` — J-Quants プラン調査 (12 agent workflow + 3 lens verify)、**Light ¥1,650/月推奨**
- `PREREG.md` — 空テンプレート (10 セクション、中身はユーザが書く)
- `configs/car.yaml` — CAR engine 設定 (model 切替、estimation window、event windows、recovery、abnormal volume)
- `scripts/jquants_fetch.py` — Light API 経由の raw data fetcher (daily_quotes / topix / trading_calendar / fins_statements / listed_info)
- `scripts/car_engine.py` — AR/CAR エンジン。day 0 規則・ルックアヘッド禁止・8 出力列 spec 準拠
- `tests/test_car_engine.py` — 23 件全通過 (day 0 / OLS 回復 / no-lookahead invariant / ADV / CAR sum / recovery / abnormal volume)
- `docs/macos_runbook_task_c.md` — Mac 上での実行手順

### Mac 側でやること

`docs/macos_runbook_task_c.md` の通り。要点だけ:

```bash
cd path/to/financial-abm-lab
pip3 install --user numpy pandas pytest
python3 -m pytest unwind-tape/tests/test_car_engine.py -v         # 23 件通ることを確認
export JQUANTS_REFRESH_TOKEN="eyJ..."                              # 認証
python3 unwind-tape/scripts/jquants_fetch.py                       # 15-20 分
python3 unwind-tape/scripts/car_engine.py                          # 秒単位
# → unwind-tape/data/parsed/tape/car_report.md を開いて G004/G008 の値を手計算と突合
```

### 完了条件の残 (C5)

- G004 (Honda) と G008 (Nintendo) の CAR が手計算と一致 — engine 実行後にユーザが検証
- 一致しない場合は `configs/car.yaml` の day 0 規則・estimation window を調整、または `PREREG.md` を先に確定させて config を合わせる

### モデル切替

- `configs/car.yaml` の `model.primary` を `topix_adjusted` ↔ `market_model` で切替
- 既定は `topix_adjusted` (PREREG 確定まで検証しやすい方)

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
