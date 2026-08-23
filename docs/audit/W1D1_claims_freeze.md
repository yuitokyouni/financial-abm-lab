# 12週間 claim / 非claim / 成果物 凍結 — v1.0

**確定日:** 2026-08-16 **対象期間:** 2026-08-16 〜 2026-11-07

**権限:** 本文書は主張(estimand)の唯一の典拠。日程はカレンダー、タスクは BACKLOG.md を正とし、相互に重複記載しない。

**改訂規則:** 変更は version を上げ、理由・日付を deviation として記録する。confirmatory 開始(Week 4)以降は claim 欄を変更しない。

## 1. 主張する(claim)

### A|科学仮説

宣言されたエンジン・執行条件・パラメータ範囲において、runtime-sealed な matched 実験により、外生予測信号の時間依存が集約注文フローおよび価格へ伝達される応答面を推定できる。**主張の対象は絶対値ではなく、事前登録した線形解析オラクルからの乖離面である。**

- 判定: Week 4 confirmatory grid、事前登録 3〜5 contrast(G2)。帰無なら等価性区間を主張(TOST / 事前指定 ROPE)

### A2a|構造的移植性

contract v0.1 と conformance test だけを参照して実装した第二エンジン(Tier 1、最小 ZI + 連続ダブルオークション)において、事前指定した符号・順位・応答形状・原尺度差が再現する。

- 判定: G4a(10/17)。限定: 自作2エンジン間の移植性

### A2b|外部移植性(条件付き)

外部エンジン(ABIDES 等)で最小 run が通り、代表条件が再現する。

- 判定: G4b(10/24)。最大6時間の spike で未到達なら compatibility report に縮小し、外部移植性は「未検証」と明記

### B|実務仮説

現行のモデル検証実務には、採用率と市場構造の組合せに起因するシステム水準の検査を実行する workflow が不足している。

- 判定: 文書調査+問題保有者インタビュー3〜5件。YH007 事例研究は B の証拠ではなく存在可能性の例示。12週内に確立せず示唆の水準に留める

## 2. 主張しない(非claim)

### 実験・統計

- 180セル × 30 seeds の全面実行を約束しない
- pilot 結果を見て SESOI を効果へ寄せない
- realized liquidity を主効果から回帰で除去しない(媒介変数として記録のみ)
- 効果量の推定から「必要十分」等の論理的主張を導かない
- ρ(M−1)≈1 を相転移と呼ばない(variance crossover と限定)
- 交互作用が n.s. であることを「加法的」と述べない
- 効果に関する強い言明(識別成立/解消/頑健/決定的 等)は、対応差＋SE が同一段落にある場合に限る
- 差が有意でない場合、比・パーセントの形で報告しない

### 妥当性・外部妥当性

- **R_sim ≈ R_theory から R_sim ≈ R_real を推論しない**
- 蓄積するものは validity atlas ではなく **falsification atlas**。「妥当」ではなく「この reference class・この領域では反証されていない」と述べ、最小検出可能効果量を必ず添える
- 証拠クラス4種(analytic limit / synthetic ground truth / empirical regularity / intervention response)を対等に並べない。現実に係留しているのは empirical regularity のみ
- stylized facts の一致を realism の根拠にしない

### 範囲

- closed-loop(price→signal→order→price)・policy feedback を WP1 に入れない。共振条件・臨界人数を扱わない
- LLM エージェント、制度変更、認証制度を扱わない
- 中間の相関 0 < ρ < 1 を扱わない(ρ=1 / ρ=0 の両端のみ)
- YH007 一件から、業界一般への欠陥の存在も需要も主張しない
- Tier 1 の適合・再現を外部移植性 A2b の証拠にしない
- ground truth 不要評価の一般化構想(property-based evaluation infrastructure)は12週間の非claim。backlog 参照のみ

### 証拠運用

- YH007 の条件不明 finding を推測で復元しない(【復元不能】として恒久クローズ済み)
- canary をコード全体の正しさの証明として扱わない
- confirmatory data へは seal 済みスクリプトを一度だけ実行する。都合の悪い部分だけ再実行しない
- 未検証の外部引用(判例日付、FDA 引用等)を本文書・prompt・code へ持ち込まない

### 事業

- WP1 の図と監査可能な bundle がない状態で VC へ接触しない。12週間、VC 追加調査・接触を停止
- 事業形態・製品化の判断を 11/7 まで行わない。decision memo で扱う

## 3. 成果物(参照)

- 必須 1〜6・条件付き 7〜8: カレンダー §1 を正とする
- 期限・Gate・11/7 決定表: カレンダー §4 を正とし、本文書へ複製しない
