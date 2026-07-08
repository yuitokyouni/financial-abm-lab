# 開示転記シート — disclosure_time / pricing / offer / OA(埋めるだけ)

系統A(CAR)と系統B(shortfall)を実 leg で動かすための**一次資料転記**シート。
`disclosure_transcription.csv` を埋めて `scripts/apply_transcription.py` を回すと、
検証を通ってから `legs.csv` の該当セルだけが更新される。**創作は厳禁。取れないセルは空欄のまま**
= その leg は day0 未確定の fail-loud を維持する(埋めた分だけ計算が伸びる)。

## なぜ転記が律速か
`legs.csv` の `after_close` が空欄の leg は day0=None(R1 の fail-loud)。CAR も shortfall も NA。
現状 day0 が解決しているのは G008 のみ。**disclosure_time の転記が全計算の最上流**。次に
offering の `pricing_date` / `offer_price_JPY` が s3(ディスカウント)を立てる。

## 埋める列と入れ方
| 列 | 形式 | 入れ方 |
|---|---|---|
| `disclosure_time` | `HH:MM`(JST) | 適時開示の**開示時刻**。取れなければ空欄(推定禁止) |
| `after_close` | `TRUE`/`FALSE` | 開示時刻 ≥15:00 なら TRUE。disclosure_time から機械的に決まる(推定ではない) |
| `time_source` | enum(下記) | 時刻の出所。**必須**(disclosure_time を入れたら必ず) |
| `pricing_date` | `YYYY-MM-DD` | 条件決定日(offering) |
| `offer_price_JPY` | 数値 | 売出価格(条件決定PDF) |
| `OA_exercised_shares` | 数値 | OA(グリーンシュー)の**行使結果**株数。0 なら 0 |

### time_source enum(この6つだけ)
`pdf_header` / `tdnet` / `yahoo_archive` / `kabutan` / `media` / `nikkei_nkd`
- `nikkei_nkd` = 日経の開示ミラー(`nikkei.com/nkd/disclosure/tdnr/...`)。発表時刻を載せることが多い
  (実例: デンソー16:55・アイシン16:40・ザ・パック17:00)。TDnet 31日制限を跨げる二次だが時刻の質は高い。
- **`inferred`(推定)は不可**。apply が ERROR で弾く。
- 空欄のまま = day0 未確定を維持(fail-loud)。埋めない自由はあるが、埋めるなら出所必須。

## タイムスタンプの所在ガイド(発表PDF本体に時刻が無いことが多い)
1. **発表PDFのヘッダ/フッタ**に時刻があればそれ(`time_source=pdf_header`)。
2. **TDnet 公開検索は過去31日しか遡れない**。今日(2026-07-08)基準で 2026-06-07 以前の開示は
   TDnet では出ない → 本シートの全 leg が対象外。
3. **過去分は次で取得**(2023年分も残存):
   - **株探(kabutan)** の銘柄別「開示一覧」に開示日時 → `time_source=kabutan`
   - **Yahoo!ファイナンスの適時開示アーカイブ** → `time_source=yahoo_archive`
   - どうしても一次で取れず報道で時刻が分かる場合のみ `media`(最後の手段)

## 取得すべきPDF(inputs/pdfs_supplied/ へ、S018 以降で Source_Log 登録)
各 offering leg について:
- **条件決定(発行価格等の決定)PDF** … `pricing_date` / `offer_price_JPY` の一次根拠
- **シンジケートカバー取引終了 の開示PDF** … 安定操作・OA まわりの確定
- 置き場所: `unwind-tape/inputs/pdfs_supplied/S0XX__<issuer>_<kind>.pdf`
- 登録: `data/parsed/tape/sources.csv`(Source_Log)に `S018` 以降で追記 → `scripts/archive_pdfs.py`
  で sha256 込みアーカイブ。`note` 欄は各行の `source_docs_to_obtain` を参照。

## 回し方
```bash
# 1) disclosure_transcription.csv を埋める(埋めた分だけでよい)
# 2) 検証だけ(legs.csv は触らない)
python3 unwind-tape/scripts/apply_transcription.py --check
# 3) 検証OK(ERROR無し)なら legs.csv に反映
python3 unwind-tape/scripts/apply_transcription.py --apply
# 4) 下流を再計算
python3 unwind-tape/scripts/car_engine.py
python3 unwind-tape/scripts/shortfall_engine.py
```

## 組み込みサニティ(**拒否ではなく確認フラグ**、ただし推定は ERROR)
- **ERROR(書き込まない)**: `time_source=inferred`、または disclosure_time があるのに
  time_source が enum 外/空欄。after_close が開示時刻と矛盾。
- **WARN(確認フラグ、書き込みは行う)**:
  - offering の **discount が 2〜5% 帯の外**(`(pricing終値−offer)/pricing終値`。pricing終値は
    J-Quants 生終値)。慣行外なので転記ミス or 特殊条件の確認。
  - **pricing_date が announce day0 の 5〜15営業日後の外**。ブックビルディング期間の常識帯。
- WARN は正しいこともある(市況急変・特殊スキーム)。潰さず「確認した」で通す。

## 反映される legs.csv の列(それ以外は一切触らない)
`disclosure_time, after_close, pricing_date, offer_price_JPY, OA_exercised_shares`。
`time_source` は legs.csv には載せず、本シートを**出所台帳**として保持する(provenance)。
apply は非空セルのみ上書き(部分転記OK・冪等)。
