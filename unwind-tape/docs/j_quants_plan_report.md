# J-Quants プラン選定レポート — unwind-tape task C

## 0. 一行結論

**Light プラン (¥1,650/月・税込) が最小十分。** バックフィル研究のみのため、**1 か月契約 → 全期間 DL → 解約** の運用で総費用 ¥1,650 に抑えられる（日割り返金なし、年払いオプションなし）。

---

## 1. 前提要件 (task C)

| 項目 | 要件 |
|---|---|
| 頻度 | 日次 OHLCV + 出来高 (調整後推奨) |
| 期間 | 2023-01-01 以降、可能なら 2022-07-01 まで遡って estimation window [-140,-21] 確保 |
| 銘柄 | 11 issuer (6902/6201/7259/7267/8154/3950/4246/7974/4063/4062/2871) |
| 市場プロキシ | TOPIX (market-model) |
| Size 変数 | 発行済株式数 または 時価総額 |
| 調整 | 株式分割等の corporate action 対応 |
| カレンダー | JST 営業日 |
| 遅延 | T+1 or 翌営業日 OK |
| I/F | REST (Python requests) |
| 基準日 | 2026-07-07 |

---

## 2. プラン比較 (JPX 公式 jpx-jquants.com の i18n dict から検証済み)

| プラン | 月額(税込) | 遅延 | 履歴 | Rate limit | TOPIX | task C 判定 |
|---|---:|---|---|---|:---:|---|
| Free | ¥0 | 12週間遅延 | 直近12週間を除く2年間 (2024-04-14 〜 2026-04-14) | 5件/分 | 不可 | 不可 (2023-01-01 に届かず、TOPIX 無し) |
| **Light** | **¥1,650** | 当日17:30頃/翌8:00頃 | **過去5年分 (≈2021-07〜)** | 60件/分 | **可** | **最小十分** |
| Standard | ¥3,300 | 当日17:30頃 | 過去10年分 | 120件/分 | 可 | 過剰 |
| Premium | ¥16,500 | 当日17:30頃 (前場は場中) | 過去20年分（最長）(〜2008-05-07) | 500件/分 | 可 | 過剰 |
| Add-on 分足・ティック | ¥5,500 | — | 2年 | — | — | 不要 (日次分析) |
| Add-on TDnet/適時開示 | ¥11,000 | — | 5年 | — | — | 不要 |

- 年払い / 年額割引は公式ページに一切記載なし。月額のみ、クレジットカードのみ、日割り返金なし。
- 2025-12-22 以降の新規登録は V2 API のみ。認証は API キー方式で Python requests から Bearer で叩ける。

---

## 3. 要件別 最小プラン

| 要件 | 最小プラン | 根拠 |
|---|---|---|
| /prices/daily_quotes (OHLCV + Volume) | Free 以上 | 全プラン提供。ただし Free は 12週遅延 + 2年窓で 2023-01-01 に届かず |
| 調整後価格 (AdjustmentFactor + Adjustment{Open,High,Low,Close,Volume}) | Free 以上 | 全プランで daily_quotes に埋め込み。Honda 7267 (1:3, 2023-10-01) / Nintendo 7974 (1:10, 2022-10-01) の分割はこれで自動処理 |
| 2022-07-01 以降の履歴 | **Light** | 5年窓 (≈2021-07〜) で余裕。Free は 2024-04〜、届かず |
| TOPIX (/indices/topix, V2: /indices/bars/daily/topix) | **Light** | Free は非対応。Light 以上で 5年 (Standard 10年, Premium 20年) |
| 11 銘柄程度の日次バルク取得 | Light の 60件/分で十分 | code×date パラメータで数コールで完了 |
| JST 営業日カレンダー (/markets/trading_calendar) | Free 以上 | 全プラン提供 |
| 発行済株式数 (size 変数の分母) | **Light** (/fins/statements の Number...Shares...FiscalYear 系フィールド) | /listed/info には無い。/fins/statements は Free 以上だが Free は 12週遅延、Light 以上で T+1。※要検証項目あり (下記リスク参照) |

---

## 4. 推奨とその根拠

### 推奨: **Light プラン ¥1,650/月**

**根拠 (すべて 2026-07-07 時点で公式サイトの verbatim 文言と一致):**

1. **履歴 5 年** で 2022-07-01 の estimation window backstop まで約 1 年の余裕あり (2021-07 まで遡れる)。
2. **TOPIX 四本値 (/indices/topix) を含む** — market-model の market proxy が確保できる。Free では取得不可なので Light が下限。
3. **daily_quotes に AdjustmentFactor + Adjustment{Open,High,Low,Close,Volume} が含まれる** — 株式分割の調整は endpoint 側で完結。Honda 1:3 (2023-10) と Nintendo 1:10 (2022-10) の 2 件の分割は AdjustmentClose を使えば透過的に処理可能。
4. **T+1 要件を満たす** — 当日 17:30頃 / 翌営業日 8:00頃 配信。バックフィル研究なので余裕。
5. **11 銘柄・数年分は 60 件/分で完了** — pagination_key で追いかけても数十コール、レート制限に触れない。
6. **Standard/Premium の追加機能 (Nikkei225/信用/空売り/前場/財務詳細/配当) は task C に不要**。¥3,300 や ¥16,500 を払う正当化がない。

### コスト最小化オペレーション

バックフィル研究で常時運用が不要なら:
- Light 1 か月契約 → 過去 5 年分を一括 DL → キャンセル、で **総費用 ¥1,650**。
- 日割り返金なしなので月中いつ解約しても同額。
- ただし 2026-04 の TSE 分類改定などがあった場合の再取得考慮で、契約中に上場銘柄一覧のスナップも同時に取っておく。

---

## 5. 代替策 (安いほうから)

- **Free + 外部補完:** 却下。2023-01-01 に窓が届かず、TOPIX も取れない。
- **Standard ¥3,300:** 10 年履歴と 120件/分の余裕。将来 event window を 2015 年頃まで拡張する予定があるなら、初回契約時に Standard で 1 か月だけ引き切っておく手も。
- **Premium ¥16,500:** BS/PL/CF, 前場, 配当情報が必要になる別タスクが並行するなら合算合理化される。task C 単独ではオーバースペック。
- **外部データ源との併用:** shares outstanding だけ EDINET XBRL や TSE listed_info XLSX から取り、価格は J-Quants Light、というハイブリッドは可能だが実装コスト増。まず Light /fins/statements で足りるか確認するのが先。

---

## 6. リスク・要検証項目

| # | リスク | 影響 | 対処 |
|---|---|---|---|
| R1 | **Light の履歴長 5 年は最新の公式 i18n dict と一致するが、古い GitBook スペックには「2年+12週」との記載が残っている**。もし実際に Light が 2y+12w なら 2024-04 までしか遡れず 2022-07-01 に届かず、Standard (¥3,300) にせざるを得ない。 | 高 (プラン選択が変わる) | 契約前にダッシュボードのプラン比較画面を人間の目で確認する。もしくは Light を 1 か月試して 2022-07-01 の daily_quotes が返るか実測 |
| R2 | **/fins/statements の shares 系フィールドは Number...FiscalYearIncludingTreasuryStock という名前で FY 末しか埋まらない可能性**。四半期 interim 開示で populate されるかどうかは未検証 (全ソースが SPA 経由の snippet で確定できず)。 | 中 (size 変数の粒度が四半期になる可能性) | Light 契約後に 7267 Honda 等の生 JSON を pull し、interim 期の shares が入っているか確認。入っていなければ FY 末値を forward-fill + 分割時は cumulative AdjustmentFactor で補正する近似で運用 (PREREG に明記) |
| R3 | **CA 調整の対象範囲**: 公式は「株式分割・株式併合・ライツイシュー」を明記。合併 (株式交換) と配当は AdjustmentClose に反映されない。 | 低 (task C は price return で AR/CAR、event 日程が ex-div 回避なら実害なし) | AdjustmentClose を total return と混同しないこと、を PREREG に注記 |
| R4 | **Adjustment 系は小数第 2 位で丸められる**。生 Close ÷ AdjustmentClose で AdjustmentFactor を逆算すると sub-yen 誤差が乗る。 | 低 | AdjustmentClose を直接 return 計算に使う (再構成しない) |
| R5 | **年払い / 年額割引は公式ページに存在しない (verbatim で「年払い」「年額」検索ヒット 0)**。バンドルされた情報の一部にあった「年額」は月額×12 の推測値と判明。 | 低 (計算に混ぜないこと) | 費用は月額ベースで見積もる |
| R6 | **Rate limit テーブルに 200件/分 という未マッピングの値が公式サイト i18n dict に存在**。Standard 昇格や新規中間ティア追加の可能性あり。 | 低 (Light 60件/分は task C には十分) | 実装は HTTP 429 に対する adaptive backoff にしておく (公称値ハードコード禁止) |
| R7 | **Light と Premium の月額は Next.js SPA で Stripe から動的読み込みされ、静的 HTML 再取得では未検証**。Standard ¥3,300 と両アドオンは verbatim 検証済み。6 ソース全てが Light=¥1,650, Premium=¥16,500 で一致し矛盾なし。 | 低 | 契約直前にブラウザで pricing 画面を目視確認 |
| R8 | **TSE 銘柄コード**: 上場銘柄一覧を各時点でスナップし、対象 11 銘柄の再編/上場廃止/合併がないことを確認 (2022-07 以降で該当は現時点で未確認)。 | 低 | listed/info を Date 指定でチェック |

---

## 7. 情報源 URL

- https://jpx-jquants.com/ (公式・料金と機能比較)
- https://jpx-jquants.com/pricing/ (SPA・要ブラウザで目視)
- https://jpx-jquants.com/ja/help/plan (i18n dict、Standard/アドオン価格 verbatim 確認)
- https://jpx-jquants.com/ja/spec/data-spec (V2 データ仕様)
- https://jpx-jquants.com/ja/spec/idx-bars-daily-topix (TOPIX V2 endpoint)
- https://jpx.gitbook.io/j-quants-ja (V1 全体スペック・SPA)
- https://jpx.gitbook.io/j-quants-ja/api-reference/daily_quotes (daily_quotes V1)
- https://jpx.gitbook.io/j-quants-ja/api-reference/topix (TOPIX V1)
- https://jpx.gitbook.io/j-quants-ja/api-reference/listed_info (listed_info V1)
- https://api.jquants.com/v2/... (実 API エンドポイント。認証は API キー Bearer)
