<!--
  unwind-tape / PREREG.md — 事前登録 (pre-registration)

  Claude はこのテンプレートの構造だけ用意した。中身はユーザが書く。
  ここに書いた仕様が「本採用の CAR 計算ルール」となり、以後の実装は
  このファイルと config を突合して整合を検証する。

  書く順序の目安:
    1. 目的 → 2. 主分析サンプル → 3. day0規則 → 4. 推定窓 → 5. 市場モデル選択 →
    6. 出力列と符号定義 → 7. 頑健性チェック → 8. 除外・打ち切りルール →
    9. 統計的検定と閾値 → 10. 事後修正の禁止事項

  記入日は空欄のままにし、確定した時点で埋める。
  以後の仕様変更は必ずここに追記し、`event_group_id` レベルで有効期間を明記する。
-->

# unwind-tape — pre-registration

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

主仮説:
副仮説:

---

## 2. 主分析サンプル

<!--
- Tier: どの tier を include するか (v0.3 README は Tier1_confirmed + confidence A/B を推奨)
- confidence: どの confidence level まで
- date range: sample の cutoff (announce_datetime ベース)
- exclusion: 除外条件 (例: value_basis=estimate_close_price のみの行は robustness の別票)
-->

include:
exclude:

---

## 3. day 0 規則

<!--
- 基本規則: day 0 = 反応可能な最初の立会
- `after_close` = TRUE のとき: 翌営業日を day 0 とする
- 半日立会 (大納会・大発会) の扱い
- 立会外時間帯 (dawn/night) の扱い
- 祝日カレンダーの source (JPX official / J-Quants)
-->

営業日カレンダー source:
after_close=TRUE の扱い:
特殊立会日の扱い:
時刻閾値 (disclosure_time がない leg):

---

## 4. 推定窓と event window

<!--
- estimation window: [-140, -21] (v0.3 spec)
- event window: [-1, +1] / [0, +1] / etc.
- announcement vs pricing vs settlement で別 window
- 最低取引日数 (推定窓に何営業日以上必要か)
-->

estimation window:
event window (announcement):
event window (pricing):
event window (settlement):
minimum estimation days:

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

primary model:
robustness model:
β 推定方法 (OLS/rolling/GLS):
α の扱い (0固定 vs free):

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

符号ルール (positive/negative の意味):
異常出来高の定義:
recovery の分母:

---

## 7. 頑健性チェック

<!--
- market model 切替との一致度
- estimation window 変更 ([-250,-11] / [-100,-11] 等) との一致度
- outlier (event window 内の急変 leg 除外) との一致度
-->

primary robustness suite:
p-hacking guard:

---

## 8. 除外・打ち切り

<!--
- estimation 期間に取引停止日を含む場合の扱い
- 分割/併合の調整方法 (unadjusted vs adjusted)
- 大災害・システム障害日の除外
-->

adjustment source:
excluded event days:

---

## 9. 統計的検定と閾値

<!--
- 単一 leg の有意性: t / SIGN / bootstrap
- CAR pooled: cross-sectional t / BMP / GRANK
- multiple testing correction (Bonferroni / FDR)
- ABM 候補の判定閾値
-->

test:
correction:
ABM_candidate_flag = Yes 判定条件:

---

## 10. 事後修正の禁止事項

<!--
- 変更が発生したら changelog に記録して再送
- サンプル追加・除外は必ずここへ記載
- 出力列の追加は許可、削除は禁止 (backward compat)
-->

changelog (以降の修正):
- YYYY-MM-DD: <変更内容> / <理由>
