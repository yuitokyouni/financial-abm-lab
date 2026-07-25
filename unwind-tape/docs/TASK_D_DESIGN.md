<!--
  YH009 / Task D 設計 — 母集団拡張(measurable legs を Nゲートまで増やす)の設計。
  Task C と同じ規律: 設計→ユーザ承認→実装。本書は設計(実装前)。創作禁止・一次確認必須。
  凍結spec(MEASUREMENT_SPEC/BENCHMARK_SPEC)の Nゲート・measurable_flag・参照分布非混入を遵守。
-->

# Task D 設計 v0.1 — 母集団拡張(measurable legs ≥ 30)

**目的**: 現状の measurable legs(実質数件)を、`BENCHMARK_SPEC` の N ゲート
= **measurable execution legs ≥ 30、かつ主要方式 2系統以上で各 10 leg 以上** まで増やす。
これが**成果物②(非線形の実証)と ③(ABM 較正)の着手条件**。手作業の転記(①)を機械的な
**発見(discovery)**で先回りし、候補を転記パイプラインに流す。

> 用語(平易): **leg** = 個別の売り1件(売り手×方式×執行)。**group** = 1銘柄の解消イベント。
> **method(売却方式)** = 売出し / 立会外分売 / ToSTNeT-3 / 市場内売却 / 株式先渡 等(spec の `sale_route`)。

---

## 1. 方針 — 一次・機械可読を軸に、多モードで探す(lead は必ず一次で確認)

**創作禁止の徹底**: 探索が出すのは**lead(候補)だけ**。数値(offer/pricing/disclosure_time)は
**一次資料からの転記でのみ**埋まる。未確認の候補は `Tier2_candidate`(空欄)で台帳に置く。

### 主源 — EDINET(売出しの systematic な一次源)
- 売出し(secondary offering)は金商法により **有価証券届出書 / 発行登録追補書類**を EDINET に提出。
  **EDINET API は全文・メタデータを全期間アーカイブ・公開** → offering を**網羅的かつ一次**で拾える主チャネル。
- 取得: 対象期間の売出し系書類を様式で絞り、**売出人・売出株数・条件**を抽出。
- 分類: 本文の「政策保有」「純投資目的以外」「縮減」等 + 売り手属性(銀行/保険/事業提携先)で
  policy-holding 該当を判定し、`confidence_policy_holding`(A_explicit / B_inference)を付与(groups.csv 規約)。

### 補源
- **立会外(ToSTNeT-3 / 分売)**: **Task A の日次キャプチャが既に記録**。ただし**無帰属** ── 発行体/保有者の
  適時開示と**突合できたものだけ** measurable leg 化。突合できない超大口は**参照分布どまり**(BENCHMARK_SPEC 遵守)。
- **株探 / Yahoo 適時開示アーカイブ**: TDnet 生検索は31日制限のため、過去の適時開示はここで(時刻・種別は転記フローと同じ)。
- **大量保有報告書(EDINET)**: 銀行等の保有比率低下(変更報告書)は解消の lead。特定執行に紐づかないことが多く discovery lead 扱い。
- **報道(日経 / Reuters / Bloomberg)**: 「政策保有 売却」等の lead。**必ず一次で確認**してから台帳へ。

---

## 2. 分類・重複排除・台帳への流し込み

- **分類**: 各候補に `issuer_code / announce_date / method / confidence_policy_holding(A/B) / measurable 可否`。
  measurable でない method(open_market_sale / share_forward 等)は `measurable_flag=FALSE`(系統A のみ)。
- **重複排除**: 1イベントが EDINET(届出書+訂正+価格決定)+ TDnet + 報道 に跨る → `(issuer_code, announce_date, method)`
  で dedup。1 offering の複数書類 = **1 leg**(親 day0 は最初の発表)。
- **流し込み(既存パイプライン再利用)**: 確定候補 → 新 group(G0XX)+ legs を **候補(Tier2_candidate・空欄)**で
  groups.csv / legs.csv に追加 → `transcription/disclosure_transcription.csv` に行追加 → 一次から転記 →
  `apply_transcription.py --check/--apply` → `shortfall_engine` / `car_engine`。

---

## 3. N ゲート追跡と正直な但し書き(必須)

- method 別に measurable legs をカウントし、**≥30・主要方式2系統×各≥10** を追跡(Task D report に常時出力)。
  カウントは **A+B 合算(主ベンチマーク、B は検証パス後)/ A_explicit 単独(併記・理想)** の2系列で出す(§確定事項2)。
- **選択バイアスの明記**: EDINET は**閾値超の売出し**を拾うので、measurable 集合は **offering / 大口に偏る**。
  小口の市場内売却・純市場売却は届出書に出ず**観測されない** → **線形域(小 size)サンプルが過小**になり得る。
  これは成果物②の**相転移点推定に直結する限界**なので必ず明記(TCA_BASELINE §3 と接続)。
- **第2方式 ≥10 が最大の難所**: 立会外は無帰属の壁で measurable 化しにくく、offering 一辺倒だと
  「主要方式2系統×各10」を満たせない可能性。→ 早期に method 別カウントを監視。届かない場合は
  **括り直しで第2方式を捏造せず**、1方式で記述提示 + 第2方式は N 明記で**検出力不足を flag**(§確定事項3)。
  N 緩め・下位分類は既定で採らない(後から結果を選ぶ p-hacking を避ける)。
- **希少性の壁(再掲)**: 非線形が宿る大口(≥1 ADV)イベントは元来稀。件数を稼いでも
  **大 size バケットが薄い**リスクは Task D では解けない(現象の希少性)。認識だけしておく。

---

## 4. 実装フェーズ(承認後・Task C と同じ規律: 設計→承認→実装)

1. **EDINET fetcher**: API で売出し系書類を期間取得、raw 保存 + sha256、既存の取得規律(retry / 冪等 / 構造変化検知)準拠。
2. **分類フィルタ**: policy-holding 判定 + method + confidence tier。
3. **dedup + 候補行生成**: groups / legs / worksheet へ Tier2_candidate で。
4. **N ゲート集計レポート**: method 別 measurable カウント + 選択バイアス注記。
- **独立性**: Task A/B/C から独立(`scripts/` 内のみ import)。`data/raw` は gitignore。API キーは env のみ。

---

## ★ 確定事項(2026-07 ユーザ回答 + Claude 既定)

1. **対象期間 = 2023–2026(確定)**。東証「資本コスト・株価を意識した経営」要請(2023-03)が
   政策保有解消の触媒 → 処置に関連する窓としてこの期間。母集団は売出し系書類を EDINET で走査。
2. **confidence tier(2026-07 ユーザ確定)**: **A_explicit / B_inference を両方記録**し
   `confidence_policy_holding` 列で区別。**N ゲートは A+B 合算を主ベンチマークとして許容**するが、
   (i) **B は一度検証パスを通す**(政策保有性を一次で再確認し誤分類を落とす)、
   (ii) **A_explicit 単独の N を常に併記**(理想は A だけでゲート通過)。B を捨てない=可逆。
3. **第2方式 <10 の代替(既定・可逆)**: **事前に代替を決め打たない**。事前登録は主ゲート(2方式×各10)のみ。
   届かなければ**方式を括り直して第2方式を捏造せず**、「1方式で非線形を記述的に提示 + 第2方式は N を明記して
   **検出力不足**と flag」。これは CONTRIBUTION §3 の退化経路 **D1(単一方式化)を "勝利" とせず限界として明示**する
   立場。ABM(成果物③)は 2方式を要件とせず**1方式内の非線形シグネチャで較正可**なので致命傷にならない。
   括り直し / N 緩和は**後から結果を選ぶ p-hacking リスク**があるため既定では採らない。
4. **EDINET API**: v2 は登録制(サブスクリプションキー)。**キーは取得済み(env に格納、`data/raw` は gitignore)**。 [API v2 仕様は実装時に固定]

---

## 参考(実在・ただし詳細は実装前に固定)

- **EDINET**(金融庁「金融商品取引法に基づく有価証券報告書等の開示書類に関する電子開示システム」)。
  有価証券届出書 / 発行登録追補書類 / 大量保有報告書。API による全文・メタデータ取得。 [要確認: API v2 仕様]
- **JPX 立会外取引情報**(Task A が日次取得中)。
- 既存 spec: `MEASUREMENT_SPEC.md`(s1/s2/s3・measurable_flag・route 別定義)、`BENCHMARK_SPEC.md`(N ゲート・参照分布非混入)、
  `TCA_BASELINE_SPEC.md`(相転移点推定・選択バイアスとの接続)。
