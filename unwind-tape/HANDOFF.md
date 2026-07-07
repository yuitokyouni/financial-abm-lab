# unwind-tape — HANDOFF

**最終更新**: 2026-07-07 JST (Task A 実装 + 初回バックフィル完了、cron 未デプロイ)

## Task 状況

| Task | Status | Blocker | 一次成果物 |
|------|--------|---------|------------|
| **A** JPX 立会外取引 日次キャプチャ | ✅ 実装完了、初回バックフィル成功、**cron 未デプロイ** | Lane B cron へ登録 | `scripts/fetch_jpx_offauction.py` |
| **B** xlsx → CSV 正規化 + PDF アーカイバ | ⏸ 未着手 | v0.2 xlsx の供給待ち | 予定: `scripts/build_tape.py`, `scripts/archive_pdfs.py` |
| **C** J-Quants + AR/CAR エンジン | ⏸ 未着手 | Task B 完了待ち | 予定: `scripts/car_engine.py`, `PREREG.md` |

---

## Task A — 完了エビデンス

### 実装

- **単体スクリプト**: `unwind-tape/scripts/fetch_jpx_offauction.py`
  - 依存: `requests`, `openpyxl`, `PyYAML`, stdlib のみ
  - 他リポパッケージへの import なし (単体で完結)
- **設定**: `unwind-tape/configs/jpx_offauction.yaml`
  - 想定カラムは `expected_columns`/`expected_headers` に宣言。変更検知の一次アンカー。

### 対象 3 ページ

| Page key | URL | 形式 | Schema 検証 | 日付キー |
|----------|-----|------|-------------|----------|
| `tostnet_large_lots` | https://www.jpx.co.jp/markets/equities/tostnet/index.html | 日次 xlsx (index に列挙) | header 完全一致 | publication_date (ファイル名 YYYYMMDD) |
| `offauction_distribution` | https://www.jpx.co.jp/markets/equities/off-auction-distro/index.html | HTML 表 (rowspan=2, 2trで1record) | `<th>` subset (空白除去して比較) | capture_date (JST) |
| `buyback_ownshares` | https://www.jpx.co.jp/markets/equities/off-auction-ownshares/index.html | HTML 表 (1trで1record) | `<th>` subset | capture_date (JST) |

### 初回バックフィル (2026-07-07 15:28 JST)

```
tostnet_large_lots     : ok_files=10  new_rows=78  dup=0   schema_mismatches=0  fetch_errors=0
offauction_distribution: ok_files=1   new_rows=3   dup=0   schema_mismatches=0  fetch_errors=0
buyback_ownshares      : ok_files=1   new_rows=11  dup=0   schema_mismatches=0  fetch_errors=0
exit=0
```

即再実行での冪等性も確認: `new_rows=0`, `dup=10` (tostnet)、`new_rows=0` (HTML 2ページ)。exit=0。

### manifest / raw / parsed の実在確認

```
$ find unwind-tape/data -maxdepth 4 -type d | sort
data
data/logs
data/parsed/jpx_offauction
data/raw/jpx_offauction/buyback_ownshares/2026-07-07
data/raw/jpx_offauction/offauction_distribution/2026-07-07
data/raw/jpx_offauction/tostnet_large_lots/2026-06-22
...(2週間分の日付ごと)
data/raw/jpx_offauction/tostnet_large_lots/2026-07-03
```

- manifest.jsonl は各 page 直下 (`data/raw/jpx_offauction/{page}/manifest.jsonl`)
  - 各行に `captured_at, page, date_key, source_url, local_path, sha256, bytes, rows_parsed, status, detail`
  - status: `ok` / `skipped_duplicate` / `schema_mismatch` / `fetch_error`
- parsed CSV: `data/parsed/jpx_offauction/{page}.csv` (追記 + natural_key dedupe)
- ログ: `data/logs/jpx_fetch_YYYY-MM-DD.log`

**raw / parsed / logs はコミット対象外** (`.gitignore`)。manifest は仮に共有したい場合コミット可(現状 `data/` 一括除外の副次で除外中)。

### 不変条件 (CLAUDE.md 参照)

- データ創作は厳禁。欠損はそのまま、`data/gaps_report.md` に列挙。
- schema-change 検知は raw のみ保存し **非0終了**。cron 経由なら stderr → mail 通知される (`data/logs/cron.stderr.log` にも残す)。
- 冪等: 同一 sha256 が manifest に `ok` で残っていれば parsed への再書込みを行わない。
- リトライ: 指数バックオフ (base=2s, factor=2, retries=4)。

---

## Task A — cron デプロイ手順 (Lane B オペレータ向け)

**このリポは remote container で走らせている都合、cron 常駐ができない。ホスト側 Lane B に登録する。**

### 手順

1. Lane B のホスト上でこのリポの working copy を用意 (branch: `claude/unwind-tape-data-foundation-0txm6z`)
2. python3.11+ と `requests`, `openpyxl`, `PyYAML` がインストール済みであることを確認
   - もしくは `uv sync` (repo root の workspace 経由)
3. `unwind-tape/cron/jpx_offauction.crontab` を参考に crontab または systemd-timer を登録
   - 推奨実行時刻: **毎日 21:00 JST** (JPX 公表は翌営業日朝、朝側で走らせるより evening capture が retention margin を最大化する)
   - flock による二重起動防止を必ず入れる
   - 週末も走らせる (idempotent スキップで無害)
4. 初回 cron 実行時、log が `unwind-tape/data/logs/jpx_fetch_YYYY-MM-DD.log` に出ることを確認
5. exit != 0 のときに通知が届くことを確認 (stderr → mail、または Lane B の webhook)

### 検証チェックリスト

- [ ] cron 実行 → `unwind-tape/data/logs/cron.stdout.log` に開始・終了ログが1エントリずつ追加された
- [ ] `unwind-tape/data/raw/jpx_offauction/tostnet_large_lots/manifest.jsonl` に本日行が追加された
- [ ] `unwind-tape/data/parsed/jpx_offauction/tostnet_large_lots.csv` の末尾が最新公表日で更新された
- [ ] schema_mismatch / fetch_error が発生した場合、`unwind-tape/data/gaps_report.md` に記録され通知が飛ぶ

### 障害復旧

- **一時的な JPX 側の 5xx/タイムアウト**: 翌日の cron 実行で自動リカバリ。`data/logs/jpx_fetch_*.log` に警告のみ、exit=4。
- **schema 不整合**: `data/raw/jpx_offauction/{page}/{YYYY-MM-DD}/` に raw が保存されているので、`configs/jpx_offauction.yaml` の `expected_columns`/`expected_headers` を更新して手動で再実行。
- **2週間 gap** (掲載が消えた後で復旧しようとした場合): raw は保存済みなので `data/raw/` を人力で web archive などから補完し、再パースするフローが必要。**Task A 単体ではリカバリ不可** — Lane B が動いていることが唯一の防波堤。

---

## Task B — 待機事項

ユーザ供給の **v0.2 xlsx** を受領次第着手。以下は spec 化済み:

- xlsx → `groups.csv` / `legs.csv` / `sources.csv` に正規化
- 以後 CSV が一次データ、xlsx は `build_tape.py` の生成物とする
- **バリデーション**: enum は `lists.yaml` と突合 / leg-group 整合 / 日付順序 `announce <= pricing <= settlement` / `quantity_basis`・`value_basis` の整合(例: `resolution_max` 行は `shares × prev_close <= value 上限`) / ハードコード数値セルは `source_id` 必須
- **PDF アーカイバ**: `sources.csv` の全 URL を DL、`data/raw/pdfs/` に保存、sha256 記録、失敗一覧レポート

**着手時に確認する事項**:
- `groups.csv` / `legs.csv` / `sources.csv` の列定義 (現時点で unknown、xlsx から抽出)
- `lists.yaml` の enum 定義 (現時点で unknown)
- `quantity_basis` / `value_basis` の spec

---

## Task C — 待機事項

Task B 完了後に着手。以下は spec 化済み:

- **J-Quants プラン別提供範囲を公式ページで確認し、本件(2023 年以降の日次四本値・出来高、対象銘柄 + TOPIX)に必要な最小プランを報告してから実装**
- `ADV20` / `ADV60` / 時価総額 → `legs_computed.csv`
- **AR/CAR エンジン**: TOPIX 調整 と market-model (推定窓 `[-140, -21]` 営業日) の両方実装、config 切替。本採用は `PREREG.md` に記載 (Claude は空テンプレートのみ作成)
- **day 0 規則**: `after_close=TRUE` の行は翌営業日を day 0 とする。推定窓・計算にルックアヘッド禁止
- **出力列**: `announcement_CAR_m1_p1`, `announcement_CAR_0_p1`, `drift_ann_to_pricing`, `pricing_CAR_m1_p1`, `settlement_CAR_m1_p1`, `recovery_5d/20d/60d`, `abnormal_volume_0_p3`

**着手時に最初にやること**: `docs/j_quants_plan_report.md` を作成して J-Quants プラン別提供範囲(遅延・期間・料金)を比較し、必要最小プランを結論として書く。実装はその後。

---

## 完了条件 (原文リマインダ)

1. ✅ Task A がスクリプトとして完成、初回バックフィルのログと manifest が確認可能 (**残: cron へ登録**)
2. ⏸ `build_tape.py` が CSV→xlsx を再現的に生成、バリデーション全通過
3. ⏸ G004(ホンダ) と G008(任天堂) の CAR が手計算と一致
4. 🔁 HANDOFF.md 更新 (このファイル)
