# unwind-tape — HANDOFF

**最終更新**: 2026-07-08 JST (Task A cron登録済み・自動発火は次回21:00待ち / Task B **v0.4 完了** / Task C **G004/G008 手計算突合 MATCH — 完了条件(3)達成**)

## Task 状況

| Task | Status | Blocker | 一次成果物 |
|------|--------|---------|------------|
| **A** JPX 立会外取引 日次キャプチャ | ✅ 実装完了、初回バックフィル成功、**cron 登録済み**(ユーザ Mac, 毎日21:00)。手動実行では成功確認済み、自動発火は次回21:00で確認予定 | — | `scripts/fetch_jpx_offauction.py` |
| **B** xlsx → CSV 正規化 + PDF アーカイバ + build round-trip | ✅ v0.4 pipeline 完了 (**validator errors=0 warnings=0**) | — | `scripts/{migrate_xlsx_to_csv,validate_tape,archive_pdfs,build_tape}.py` |
| **C** J-Quants + AR/CAR エンジン | ✅ **完了** — G004/G008 の CAR が独立実装の手計算と **3/3 MATCH (diff=0.000000)** | — | `scripts/{jquants_fetch,car_engine,hand_check_car}.py`, `configs/car.yaml`, `docs/j_quants_plan_report.md`, `PREREG.md`(空テンプレ) |

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

### ⚠️ cron → launchd への切替を推奨 (2026-07-08 review 指摘)

**現状 `setup_macos_cron.sh --install` で cron 登録済み。** cron はスリープ中に発火時刻を跨ぐとその回を**永久に失う**(次回発火まで何もしない)。launchd の `StartCalendarInterval` はスリープでロスした発火を**起床時に自動キャッチアップ**する。ノートPCで夜間スリープする運用なら launchd 一択。

切替手順:
```bash
crontab -e   # unwind-tape の2行(# unwind-tape ... と 00 21 * * * ...)を削除して保存
bash unwind-tape/cron/setup_macos_launchd.sh --install
launchctl list | grep com.unwind-tape.jpx    # 登録確認
```
plist は `~/Library/LaunchAgents/com.unwind-tape.jpx.plist` に置かれる。

### ✅ 鮮度アラーム実装済み (2026-07-08)

発火漏れ・構造変化を「誰も見ていない」状態を無くすため、`fetch_jpx_offauction.py` の
実行末尾で各ページの `manifest.jsonl` の最新 `status=ok` の `date_key` を確認し、
**営業日換算で5日以上古ければ ERROR ログを出し exit≠0** にする機能を追加した
(`--max-stale-business-days` で閾値変更可、`--skip-freshness-check` で無効化可)。
JPX の掲載保持は過去2週間のみなので、この仕組みが唯一の早期警戒網になる。
単体テスト: `tests/test_fetch_jpx_offauction.py` (8件)。

### 障害復旧

- **一時的 5xx**: 翌日の cron/launchd 実行で自動リカバリ。log に警告のみ。
- **schema 不整合**: raw は保存済み。`configs/jpx_offauction.yaml` を更新 → 手動再実行。
- **2週間 gap** (掲載消滅後の復旧): raw は保存済みだが、Task A 単体ではリカバリ不可。**鮮度アラームで早期検知するのが唯一の防波堤。**

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
- **truncated-URL の prefix-match 自動解決件数**: 0 (v0.3 では 6 セルの truncated URL のうち 3 件を
  prefix match で自動解決していたが、v0.4 で C026 により URL セル自体が全復元されたため不要に)。
  ⚠️ この「3」は **prefix-match で自動解決できた件数**であり、truncated URL の総数ではない。
  truncated セルの総数は **27 セル(URL 6・seller_name 3・route_notes/mechanism/notes 18)**。
  過去のレポート・引き継ぎ資料で「URL truncation: 3件」と書いたものは不正確 (2026-07-08 review 指摘、訂正済み)。
- **unresolved URLs (Source_Log に無い URL)**: 0 (v0.3=6 から解消。C027 で S012-S017 追加)
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
- `scripts/jquants_fetch.py` — J-Quants API fetcher。**V2 既定** (`x-api-key` 認証、
  daily_quotes/topix/trading_calendar/fins_summary/listed_info)。V1 レガシー資格情報
  にも `--base-url` で対応 (V1 は 2026-07 時点で実質廃止、410 Gone を実機確認済み)
- `scripts/car_engine.py` — AR/CAR エンジン。day 0 規則・ルックアヘッド禁止・8 出力列 spec 準拠。
  V1→V2 フィールド名不一致を検知する `FieldMismatchError` guard 付き
- `tests/test_car_engine.py` — 30 件全通過 (day 0 / OLS 回復 / no-lookahead invariant / ADV / CAR sum / recovery / abnormal volume / field-mismatch guard)
- `docs/macos_runbook_task_c.md` — Mac 上での実行手順

### Mac 側でやること

`docs/macos_runbook_task_c.md` の通り。要点だけ:

```bash
cd path/to/financial-abm-lab
pip3 install --user numpy pandas pytest
python3 -m pytest unwind-tape/tests/test_car_engine.py -v         # 30 件通ることを確認
export JQUANTS_API_KEY="ダッシュボードのAPIキー"                    # V2 認証
python3 unwind-tape/scripts/jquants_fetch.py                       # 15-20 分
python3 unwind-tape/scripts/car_engine.py                          # 秒単位
# → unwind-tape/data/parsed/tape/car_report.md を開いて G004/G008 の値を手計算と突合
```

### ✅ 実データでの fetch 検証完了 (2026-07-08)

Mac + Light プラン + V2 API キーで `jquants_fetch.py` を実行、25/25 endpoint fetch 成功 (exit=0):
- trading_calendar: 1469 件 (2022-07-01〜2026-07-08)
- topix: 982 件
- daily_quotes: 11 銘柄 × 955〜982 件
- fins_summary: 11 銘柄 × 20〜23 件
- listed_info: **10/11 件** (1 銘柄が未取得 — CAR 計算には不使用の補助データなので non-blocking。原因は未調査)

これで V2 の認証・endpoint・response envelope の実装が実データで裏付けられた。

### ✅ car_engine.py 実データ実行成功 (2026-07-08) — G004/G008 の CAR が出力された

実データ実行で以下の V1→V2 フィールド名リネームを実機確認・修正済み:

| 概念 | V1 | V2 (実確認) |
|---|---|---|
| 営業日区分 | `HolidayDivision` | `HolDiv` |
| 四本値 | `Close`/`Open`/`High`/`Low` | `C`/`O`/`H`/`L` |
| 出来高 | `Volume` | `Vo` |
| 調整後終値 | `AdjustmentClose` | `AdjC` |
| 調整後出来高 | `AdjustmentVolume` | `AdjVo` |
| 調整係数 | `AdjustmentFactor` | `AdjFactor` (変化なし) |
| 開示日 (fins) | `DisclosedDate` | `DiscDate` |

**未解決 (R2 が的中)**: `/fins/summary` に V1 の「期末発行済株式数」に相当する直接フィールドが無い。最も近い代替は `AvgSh` (期中平均株式数、EPS算出用)。`load_fins_shares` はこれを **近似値として使用**し、`market_cap_JPY` の detail に `(approx: period-average shares, not period-end)` と明記するようにした。正確な期末株式数が必要なら EDINET 等の外部ソース併用を検討 (plan_report.md R2 の代替案参照)。

9/12 leg で CAR 計算成功 (G001-G008)。残り3件 (G009-G011) は Tier2_candidate で `announce_datetime` 空欄のため意図通り未計算。

### ✅ C5 完了 (2026-07-08) — G004/G008 手計算突合 3/3 MATCH

`scripts/hand_check_car.py` (car_engine.py とは独立実装、日付ナビゲーションのみ
`BusinessCalendar` を共用、AR/CAR の算術は素朴な log-return 差分の for-loop) で
実データを再計算し、`car_report.md` の値と突合:

| leg | car_engine.py | hand_check_car.py | diff |
|---|---:|---:|---:|
| G004/L001 (Honda) | -0.010755 | -0.010755 | 0.000000 |
| G008/L001 (Nintendo) | +0.011071 | +0.011071 | 0.000000 |
| G008/L002 (Nintendo) | +0.047487 | +0.047487 | 0.000000 |

**完了条件(3)達成。** 2つの独立した実装経路が寸分違わず一致した。

market_cap は `AvgSh`(期中平均株式数)近似のまま — 正確な期末株式数が必要になったら
EDINET 等の外部ソース併用を検討 (plan_report.md R2)。日次リターン(CARの本体)には
影響しない。

### モデル切替

- `configs/car.yaml` の `model.primary` を `topix_adjusted` ↔ `market_model` で切替
- 既定は `topix_adjusted` (PREREG 確定まで検証しやすい方)

---

## 系統B — shortfall 分解エンジン (MEASUREMENT_SPEC v0.2, 2026-07-08)

`MEASUREMENT_SPEC.md`(ユーザ確定 v0.2)に基づく実装。系統A(CAR)とは独立。

- **spec**: `unwind-tape/MEASUREMENT_SPEC.md`
- **engine**: `unwind-tape/scripts/shortfall_engine.py` → `data/parsed/tape/legs_shortfall.csv`
- **config**: `configs/car.yaml` の `shortfall:` 節 (a=1, price_basis=raw, route分類)
- **tests**: `tests/test_shortfall_engine.py` 9件。恒等分解 `IS_raw=s1+s2+s3` の厳密成立、
  toSTNeT s3≡0/degenerate、TOPIX total調整、生終値回帰(分割銘柄で s3 が壊れないこと)を固定。

**実装上の必須逸脱1点(要ユーザ確認)**: 系統Bは**生終値(C)**で実装した。spec は「調整後」と
書いてあるが、契約上の生価格(売出価格・約定値)と調整後終値を混ぜると**分割銘柄で s3 が
約 ln(分割比) ずれて壊れる**(Honda 2023-10 の 1:3 分割 → s3 が −ln(3)≈−1.10 ずれる)。
単一イベント区間内に分割は入らないので生終値で恒等分解は閉じる。詳細は MEASUREMENT_SPEC.md
末尾の実装ノート。

### Mac での実行
```bash
python3 unwind-tape/scripts/jquants_fetch.py   # 済ならスキップ (Open=O も取得済み)
python3 unwind-tape/scripts/shortfall_engine.py
cat unwind-tape/data/parsed/tape/legs_shortfall.csv
```

### 現データで計算できる leg(正直な現状)
`after_close` が明示済みなのは G008/L001 のみ → **親 day0 が解決するのは G008 だけ**。従って
系統Bで実値が出るのは **G008/L002(DeNA の ToSTNeT-3 応募, degenerate 型)の1件のみ**。
残りは spec の宣言どおりブロック中:
- G001-G007: 親 day0 未解決(`after_close`/`disclosure_time` 未転記)→ skip
- secondary_offering 各行: `pricing_date`/`offer_price_JPY` 未転記 → skip(創作しない)
- G002 share_forward: `measurable_flag=FALSE`(系統B対象外、系統Aのみ)

**→ 系統Bを動かすための最優先作業は spec §依存の通り: G001-G007 の `disclosure_time` 転記、
次に pricing_date / offer_price の一次PDF転記。** これが済めば offering 系の s1/s2/s3 が一気に埋まる。

---

## BENCHMARK — 無条件 exec_gap 参照分布 (BENCHMARK_SPEC v0.1, 2026-07-08)

Task A が日次で貯める立会外プリント(ToSTNeT-1 超大口約定・立会外分売)× その日の J-Quants
生終値から、**平時の執行ギャップの正常水準**(参照分布)を作る。**tape 本体(系統A/B)には
混入させない**。帰属 leg の s3 が異常かどうかを後で判定するための対照であって、統計的 null では
ない。帰属 leg の転記待ちに**ブロックされず今すぐ回せる**唯一の経験的アウトプット。

- **spec**: `unwind-tape/BENCHMARK_SPEC.md`(ユーザ確定 v0.1 + 実装ノート)
- **engine**: `unwind-tape/scripts/benchmark_engine.py`
- **config**: `configs/benchmark.yaml`
- **tests**: `tests/test_benchmark_engine.py`(exec_gap 恒等 `close=prev+day_return`、生終値、
  ±7%バンド/前日終値クロス分類、size/ADV20 バケット、超大口/分売の row、summary facet、健康診断)
- **出力**:
  - `data/parsed/benchmark/benchmark_detail.csv`(px/prev/close/両gap/day_return/size/ADV20/ex-div/分類) — **価格含む→git外**
  - `data/parsed/benchmark/benchmark_summary.csv`(route×参照×size/ADV20 別 N/median/IQR/p90/p95/p99/バンド集積率) — git-track
  - `data/parsed/benchmark/benchmark_report.md`(同上+注記) — git-track

**定義**: 超大口は `exec_gap_prev=ln(prev_close)−ln(px)`、`exec_gap_close=ln(close)−ln(px)`
(参照は両方保存、恒等 `close=prev+day_return`)。分売は `exec_gap=ln(prev_close)−ln(分売価格)`
= 開示ディスカウント(administered price、交渉価格系と別 route)。**生終値基準**(系統Bと同じ)。

**注記(裾の解釈に必須、report にも出力)**: (a) `band_edge_rate` の ±7% は**目安**で、実際の
制限値幅は絶対円ラダー。裾は規則打ち切りされ得るので売出しの裾と直接比較しない。(b) `ex_div_flag`
は `AdjustmentFactor≠1` 判定なので**分割/割当は拾うが現金配当の落ちは検出できない**(既知の盲点、
要 /fins/dividends)。

### Mac での実行
```bash
# 1) プリント出現銘柄の日次バーだけ取得・キャッシュ(要 JQUANTS_API_KEY, レート制御)
python3 unwind-tape/scripts/benchmark_engine.py --fetch
# 2) 参照分布を計算
python3 unwind-tape/scripts/benchmark_engine.py
cat unwind-tape/data/parsed/benchmark/benchmark_report.md
```
現状 N はまだ薄い(Task A の backfill 2週間+日次ぶん)。日々のキャプチャ蓄積で自動的に増える。
`benchmark_engine.py` は Task A の停止も検知する(最新プリントが 5営業日超遅延なら WARN)。

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
