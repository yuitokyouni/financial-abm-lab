<!--
  unwind-tape / PREREG.md — 事前登録 (pre-registration)

  ここに書いた仕様が「本採用の CAR 計算ルール」となり、以後の実装は
  このファイルと config を突合して整合を検証する。

  以後の仕様変更は必ずここに追記し、`event_group_id` レベルで有効期間を明記する。
-->

# unwind-tape — pre-registration

> **⚠️ DRAFT — 未確定。** 以下は Claude が作成した草案。各項目は 2026-07-08 時点の
> 実装・議論内容から機械的に埋めたものであり、**確定日/確定者が入るまでは
> 拘束力を持たない**。特に §3(day 0 規則)と §9(統計的検定)は現状のサンプルサイズ
> (N=12 legs, うち after_close 未確定分は R1 修正でさらに解決待ちに後退)を前提に
> 書いてあるため、サンプル拡張(Task D)後は再検討が必要。

**確定日**:
**確定バージョン**:
**確定者**:

---

## 1. 目的と一次仮説

<!--
政策保有株の解消 event に対して、以下を明示する:
- 主仮説 (例: 「size/ADV では説明できない残差が route と support で説明される」)
- 副仮説 (list)
- ABM 候補判定の閾値 (mechanism_hypothesis を Yes に落とす条件)
-->

**主仮説(draft)**: 政策保有株解消イベントの announcement CAR は、size/ADV・size/free float・
売却構造(sale_route)・自己株買い支援の有無(support_buyback)でおおむね説明され、
これらの観測変数で説明できない残差パターンが systematic に集積する場合にのみ ABM 検証の
対象とする(Baseline_Spec.csv Step 1〜5 に準拠)。

**副仮説(draft)**:
- (a) support_buyback=TRUE のイベントは CAR の下落幅が小さい、または正に転じる
  (G008 Nintendo: 支援あり announcement_CAR_m1_p1=+0.011 は示唆的だが N=1 で検証にならない)
- (b) **20% / 100% ADV 境界仮説**: sold_shares / ADV20 が概ね20%未満の売却は市場が平静に吸収し
  価格影響が小さい一方、100%(=1日分の平均出来高相当)を超える規模では価格影響が非線形に
  拡大する可能性がある。この境界(20%近傍・100%近傍)を跨ぐ leg 群を比較することが
  Baseline_Spec Step 3.5 の「route が複数共存する size/ADV 帯」の具体的な検証対象になる。
  **現状のサンプルでは ADV20 自体が9legしか計算できておらず(R1修正後さらに減る見込み)、
  この境界を跨ぐ十分な leg 数が揃うかは Task D(母集団拡張)後に要確認。**
- (c) **業種偏り(要注意・明記必須)**: 現状のシード11 groups のうち DENSO・Toyota Industries・
  Aisin・Honda Motor・Daikyo Nishikawa の**5件(約45%)が自動車サプライチェーン系**。
  残差パターンが見えても「政策保有株解消の一般効果」なのか「自動車業界固有の効果
  (系列再編・国内生産体制見直し等の同時代性)」なのかを区別できない。Baseline_Spec Step 3 の
  industry FE 導入は必須。母集団拡張までは業種別のsubgroup分析を主張の根拠にしない。

**ABM_candidate_flag=Yes の判定閾値**: 残差が size/ADV・route/support FE を制御してもなお
系統的に(ランダムでなく)クラスタ化する場合のみ。単一 leg の外れ値では判定しない。

---

## 2. 主分析サンプル

<!--
- Tier: どの tier を include するか (v0.3 README は Tier1_confirmed + confidence A/B を推奨)
- confidence: どの confidence level まで
- date range: sample の cutoff (announce_datetime ベース)
- exclusion: 除外条件 (例: value_basis=estimate_close_price のみの行は robustness の別票)
-->

**include(draft)**: `event_tier=Tier1_confirmed` かつ `confidence_policy_holding` が
`A_explicit_policy_holding` または `B_strong_inference`。

**exclude(draft)**: `event_tier=Tier2_candidate`(G009-G011)/`Tier3_overhang` は背景変数
としてのみ使用し、CAR 分析本体には含めない。`value_basis=estimate_close_price` のみで
確定値が無い leg(G004 Honda 等、Reuters 推定ベース)は robustness の別票として分離する。

**サンプルサイズの限界(明記必須)**: 2026-07-08 時点で N=12 legs(11 groups)。うち
day 0 が計算できる leg は after_close 明示済みの分のみ(R1 修正時点で最大1〜数件まで
後退する可能性が高い)。Baseline_Spec.csv Step 1(size/ADV 単回帰)すら安定して回せる
規模ではない。**Task D(Sampling_Frame.csv の TDnet クエリ実装による母集団拡張)が
本分析着手の前提条件。**

---

## 3. day 0 規則

<!--
- 基本規則: day 0 = 反応可能な最初の立会
- `after_close` = TRUE のとき: 翌営業日を day 0 とする
- 半日立会 (大納会・大発会) の扱い
- 立会外時間帯 (dawn/night) の扱い
- 祝日カレンダーの source (JPX official / J-Quants)
-->

**基本規則(実装済み・2026-07-08 修正後)**:
- `after_close` = `TRUE`(明示) → 翌営業日を day 0 とする
- `after_close` = `FALSE`(明示) → announce_datetime 当日を day 0 とする
  (非営業日なら翌営業日にシフト)
- `after_close` が上記いずれでもない(**空欄・unknown**) →
  **day 0 を計算しない。当該 leg の CAR は「未解釈」として扱う。**
  日本の売出し開示は大半が引け後(15:00以降)のため、空欄を引け前開示と暗黙に
  仮定すると day 0 が系統的に1営業日早くなるリスクが高い
  (2026-07-08 review で実際に発覚。修正前は12 leg中実質1leg only が明示値で、
  残りが誤って「同日」扱いされていた)。

**未確定事項(要ユーザ判断)**:
- **時刻閾値**: 「引け後」の基準時刻を何時とするか。TSE は 2024-11 に大引けを
  15:00→15:30 に延長している。この境界を跨ぐ leg があれば個別に確認が必要
  (2026-07-08 時点のシードには該当なさそうだが、母集団拡張後は要チェック)。
- **半日立会 (大納会・大発会)**: J-Quants `/markets/calendar` の `HolDiv`(旧
  `HolidayDivision`)値 "2"(車道 half day / 取引あり)を通常営業日として扱ってよいか未検討。
  現状の `BusinessCalendar` 実装は "1" と "2" を両方営業日として扱っている(要確認)。
- **祝日カレンダー source**: J-Quants `/markets/calendar` を正とする(draft)。
  JPX 公式カレンダーとの突合は未実施。

**運用上の注意**: after_close が空欄の leg(2026-07-08 時点で G001-G007・G008/L002 相当)は、
アーカイブ済みの一次資料 PDF(`inputs/pdfs_supplied/`)と TDnet 検索で
`disclosure_time`/`after_close` を legs.csv に転記してから再計算すること。
それまでの CAR 値は本分析に使用しない。

---

## 4. 推定窓と event window

<!--
- estimation window: [-140, -21] (v0.3 spec)
- event window: [-1, +1] / [0, +1] / etc.
- announcement vs pricing vs settlement で別 window
- 最低取引日数 (推定窓に何営業日以上必要か)
-->

**estimation window(実装済み既定)**: `[-140, -21]` 営業日(day 0 相対)。market_model
使用時のみ意味を持つ(topix_adjusted は推定窓不使用)。

**event window(実装済み既定)**:
- announcement: `[-1, +1]` と `[0, +1]` の両方を出力
- pricing: `[-1, +1]`
- settlement: `[-1, +1]`

**minimum estimation days(実装済み既定)**: 100 営業日。市場モデル使用時に満たなければ
`est_reason` に理由を記録し NaN を返す(黙って計算しない)。

---

## 5. 市場モデル選択

<!--
config 切替式 (topix_only / market_model)
- topix_only: AR_i = R_i - R_topix
- market_model: R_i = α + β * R_topix + ε → AR_i = R_i - (α + β * R_topix)
- α/β の推定期間 (estimation window)
- 本採用 (primary):
- 副次採用 (robustness):
-->

**primary(draft, 実装済み既定)**: `topix_adjusted`(差分モデル、AR = r_stock − r_topix)。
推定窓不要で検証しやすく、サンプルが小さい現段階では過剰パラメータ化を避ける狙い。

**robustness(draft)**: `market_model`(回帰モデル、推定窓 `[-140,-21]`、OLS、α free)。
サンプル拡張後、primary との一致度を §7 で確認する。

**β 推定方法**: OLS(単純最小二乗、頑健標準誤差なし)。
**α の扱い**: free(0 固定にしない、config `alpha_free: true`)。

---

## 6. 出力列と符号定義

<!--
- announcement_CAR_m1_p1: 発表日 CAR[-1,+1]
- announcement_CAR_0_p1: 発表日 CAR[0,+1]
- pricing_CAR_m1_p1: 条件決定日 CAR[-1,+1]
- settlement_CAR_m1_p1: 受渡日 CAR[-1,+1]
- drift_ann_to_pricing: announce day 0 から pricing day 0 までの累積 AR
- recovery_5d / 20d / 60d: 発表 day 0 からの回復率
- abnormal_volume_0_p3: 発表後 0〜+3 日の異常出来高比 (log(V/ADV60) 等)
-->

**符号ルール(draft)**: 正 = 株価上昇方向のAR。売却系イベントは需給悪化により
負の反応が事前予想されるため、正の CAR は「support 効果が需給悪化を上回った」
と解釈する仮説的な読み方になる(確定的な解釈ではない)。

**異常出来高の定義(実装済み既定)**: `log(V_avg[0,+3] / ADV60)`。

**recovery の定義(要確認 — 命名と実装の不一致に注意)**: 現状の実装
(`configs/car.yaml` の `recovery.transform: cum_ar`)は day 0 から horizon
までの**累積 AR そのもの**を返しており、「価格が発表前水準にどれだけ戻ったか」
という直感的な「回復率」の定義(例: 1 − |CAR_horizon| / |CAR_announcement|)とは
異なる。名称が実装を正しく表していない可能性があるため、確定時にどちらの定義を
採用するか明記すること。

---

## 7. 頑健性チェック

<!--
- market model 切替との一致度
- estimation window 変更 ([-250,-11] / [-100,-11] 等) との一致度
- outlier (event window 内の急変 leg 除外) との一致度
-->

**primary robustness suite(draft)**:
1. `topix_adjusted` ⇔ `market_model` の切替で符号・大きさが一致するか
2. estimation window `[-140,-21]` ⇔ `[-250,-11]` の切替で market_model の β が安定するか
3. 自動車サプライチェーン系5社(§1 参照)を除外した subgroup で残差パターンが
   維持されるか(業種偏り対策)

**p-hacking guard**: 事前登録後のサンプル追加・除外基準の変更は本ファイル
§10 changelog に記録すること。分析結果を見てから basis や tier の定義を
事後的に変えない。

---

## 8. 除外・打ち切り

<!--
- estimation 期間に取引停止日を含む場合の扱い
- 分割/併合の調整方法 (unadjusted vs adjusted)
- 大災害・システム障害日の除外
-->

**adjustment source(実装済み)**: J-Quants `daily_quotes`(V2: `/equities/bars/daily`)の
調整後終値(`AdjC` フィールド)。株式分割は透過処理される
(Honda 7267: 2023-10 に 1:3 分割、Nintendo 7974: 2022-10 に 1:10 分割、いずれも
`AdjustmentFactor` で吸収済み)。

**excluded event days(draft)**: 現状未確認。取引停止日・システム障害日を含む
leg があるかは母集団拡張後にチェックする。

---

## 9. 統計的検定と閾値

<!--
- 単一 leg の有意性: t / SIGN / bootstrap
- CAR pooled: cross-sectional t / BMP / GRANK
- multiple testing correction (Bonferroni / FDR)
- ABM 候補の判定閾値
-->

**現状の制約**: N=12 legs(実質さらに少ない)では cross-sectional な有意性検定は
検定力不足で意味を持たない。**統計的検定は Task D でサンプルを拡張するまで実施しない。**
現段階では記述統計(符号・大きさの妥当性を一次資料と目視突合)にとどめる。

**test(draft、サンプル拡張後)**: cross-sectional t検定 + BMP(Boehmer-Musumeci-Poulsen)
標準化残差検定を併用候補とする。
**correction(draft)**: multiple testing 補正は複数副仮説を同時検定する段階で FDR
(Benjamini-Hochberg)を軽量な既定とする。
**ABM_candidate_flag=Yes 判定条件**: §1 参照。単一 leg では判定しない。

---

## 10. 事後修正の禁止事項

<!--
- 変更が発生したら changelog に記録して再送
- サンプル追加・除外は必ずここへ記載
- 出力列の追加は許可、削除は禁止 (backward compat)
-->

- 変更が発生したら本ファイルに追記して再送する。
- サンプル追加・除外は必ずここへ記載する。
- 出力列の追加は許可、削除は禁止(backward compat)。

**changelog (以降の修正)**:
- 2026-07-08: Claude が draft を作成(確定ではない)。§1〜§9 を 2026-07-08 review の
  議論内容(day 0 未定義ケースの発覚、業種偏り、20%/100% ADV 境界仮説、recovery の
  命名と実装の不一致)を踏まえて記入。ユーザ確定待ち。
