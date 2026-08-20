**正本: 本ファイル。claude.ai プロジェクト添付はミラー。**

**§2 の規範的典拠は 2026-08-22 の v0.1 凍結以降 `sieve/docs/contract/` 側。本ファイル §2 は歴史的出所。**

**claim・非claim に関する記述はすべて `docs/audit/W1D1_claims_freeze.md` (v1.0) を正とする。本ファイルの該当記述(§7 ほか)は歴史的出所として読む。日程・gate・11/7 決定表は引き続き本ファイル §4 を正とする。**

> 変更注記(2026-08-20): 外部のみの正本を repo へ収容。上記ヘッダ3行の追加のみで、日程・内容は改訂 v1.1(2026-08-13)から一切変更していない。3行目は同日追記 — §7 と claims v1.0 §2 の重複、および Week 7 等に散在する非claim 記述を、行の列挙ではなくクラス単位の優先順位宣言で閉じるため。

# Sieve / YH007 12週間実行計画

- **期間**: 2026-08-16(日)〜2026-11-07(土)
- **改訂**: v1.1(2026-08-13)
- **目的**: 監査可能な証拠 contract の上で、shared predictor の時間依存が注文フローと価格へ転写されるかを検証し、結果が正でも帰無でもワーキングペーパーと再利用可能な検査インターフェースを残す。

## 0. 計画上の前提

- 8月16〜18日は七大戦観戦のため、Sieve作業は各日3時間を上限とする。
- 8月22日は5時間、8月23日は2時間、8月24日は5時間を作業上限として割り当てる。
- 10月1日の修士課程開始後は、研究室・授業を侵食しないよう、最初の2週を各8時間、その後も週10〜14時間に抑える。
- 8〜9月の実装・実験を前倒しし、10月以降は移植性確認、解析、執筆、限定的な問題インタビューを中心にする。
- Claude Code / Cursor が実装とリポジトリ監査を担当する。Yuito は仕様凍結、結果確認、科学的判断、文章化を担当する。
- VCマップの追加調査とVC接触は12週間停止する。
- 下記の時間は人間の集中作業時間であり、無人の計算時間は含まない。

**総作業上限: 約250時間。合計時間を維持するために10月へ作業を押し込まない。**

| 期間 | 週あたり上限 | 主な作業 |
|---|---|---|
| 8/16〜9/26 | 30時間 | 証拠仕様、実装、pilot、本実験 |
| 9/27〜10/3 | 20時間 | 結果凍結、図、修士移行 |
| 10/4〜10/17 | 8時間 | Tier 1エンジン、接触開始、修士課程への移行 |
| 10/18〜11/7 | 10〜14時間 | Tier 2、執筆、インタビュー、凍結 |

## 1. 12週終了時の成果物

### 必須成果物

1. **YH007 provenance incident report**
   - spec と実行コードの乖離
   - 影響を受けた finding と下流引用先
   - 隔離判断と復旧不能な範囲
   - effective config と canary による再発防止
2. **Evidence Contract v0.1**
   - エンジン非依存の入出力 schema
   - runtime-resolved effective config
   - 導出値、式の版、依存環境、RNG情報
   - event log、metric output、artifact hash の関係
   - exact canary と semantic canary の規約
3. **事前登録文書**
   - 主要仮説、方向予測、主要 contrast
   - pilot / confirmatory seed の分離
   - 多重比較、hold-out、停止規則
   - 原尺度 SESOI と等価性判定
   - pilot データで端から端まで動作確認済みの実行可能な解析スクリプト
4. **Engine 1 の confirmatory evidence bundle**
   - q を固定人数内の置換率として実装
   - 分散一致した phi=0 対照と permutation 対照
   - 実現流動性の診断量
   - runtime、RAM、同時実行可能数
5. **WP1 草稿と主要図**
   - 結果が正なら転写応答面と境界
   - 帰無なら等価性範囲と打ち切り判断
   - 科学仮説 A と実務仮説 B を分離
6. **Tier 1 第二エンジンの最小再現**
   - contract 凍結後に仕様書だけを参照して作る最小 ZI ＋ 連続ダブルオークション
   - PAMS adapter や参照実装を見ずに実装
   - 事前作成した conformance test と canary protocol へ適合
   - 代表6〜12条件の再現

### 条件付き成果物

7. **Tier 2 外部エンジンの compatibility report / 最小再現**
   - ABIDES 等との意味論対応表
   - 接続できた場合のみ代表条件を再現
   - 接続不能も結果として記録し、全面改修はしない
8. **問題保有者の検証**
   - 候補15人
   - 図と bundle が完成し、Yuito が承認した場合のみ最大8人へ依頼
   - 12週間内の完了目標は3〜5件。外部返信に依存するため15件完了は約束しない

## 2. 証拠 contract の確定仕様

本番グリッドより前に、以下を v0.1 として凍結する。

### 2.1 エンジン共通の run record

- `engine_id`, `engine_version`, `git_commit`, source digest
- container / dependency-lock digest、Python・NumPy・BLAS情報
- RNG algorithm / version、master seed、seed-addressing規約
- 入力 artifact の digest
- CLI、設定ファイル、環境変数、既定値を解決した `effective_config`
- 導出パラメータの実効値、式ID、式version
- event-log schema version
- metric-suite version と出力 digest
- canary fixture version と結果

PAMS 固有のエージェント名や板内部クラスは必須 field にしない。共通部分は、時刻、event type、actor role、side、price、quantity、order/trade ID、cause ID とし、エンジン固有情報は extension へ隔離する。

### 2.2 canary を二層に分ける

- **Exact replay canary**: 固定 container、固定 seed、極小構成について、canonicalized output と主要統計 vector の hash を一致させる。コードの意味変更と環境変更をまとめて検出する。
- **Semantic canary**: 異なる環境・他エンジンでは、保存則、event count、符号、許容差付き統計を検査する。同一 hash を要求しない。

exact hash だけでは差の原因を特定できないため、hash と同時に比較可能な統計 vector を保存する。canary は通った経路の意味変更を検出するものであり、コード全体の正しさを証明するものとは扱わない。

## 3. 実験の固定構造

### 3.1 降ろさない条件

- 実行時実効値と bundle の結合
- exact canary
- q を固定戦略コホート内の置換率として実装
- 主対照: 定常分散を一致させた phi=0
- 副対照: 実現信号のランダム置換
- pilot seed と confirmatory seed の完全分離
- confirmatory 開始後の指標・閾値・セル変更禁止
- confirmatory data を読む前に、解析スクリプト、依存 lock、主要図の生成処理まで seal

### 3.2 計算量超過時に削る順序

1. 180セルの全面展開をやめ、基準 L/E の core grid へ限定
2. L/E は境界候補周辺の代表セルだけに限定
3. N_S 二水準は同じ q・異なる qN_S と、同じ qN_S・異なる q の部分 factorial だけにする
4. Tier 2 の ABIDES 全面再現を compatibility report へ縮小
5. 環境横断の bitwise 一致をやめ、semantic canary に限定

control、hold-out、実効設定の封印、Tier 1 の最小エンジンは計算量を理由に削らない。

### 3.3 主解析

- 180個のセル別検定を主解析にしない。
- 事前指定 response surface と3〜5個の主要 contrast を主解析とする。
- 主要 contrast は Holm 等で FWER を管理する。
- セル単位の探索結果は FDR 管理の上で exploratory と表示する。
- common random numbers を使う場合は seed block で対応を保った推論を行う。
- response surface、3〜5個の contrast、Holm 補正、TOST、主要図までを一つの解析コマンドにする。
- confirmatory data へは seal 済みスクリプトを一度だけ実行する。bug が見つかった場合は旧結果を残し、version を上げ、deviation を記録した上で全解析を再実行する。都合の悪い部分だけを再実行しない。

### 3.4 原尺度 SESOI

第一候補は、**予測信号の1定常標準偏差 innovation に対する、指定 horizon 内の累積価格応答(bp)** とする。補助量として、信号 power のうち OFI・return へ到達した割合、depth で正規化した impact を出す。

SESOI は標準誤差で割らない。pilot は分散と計算量の推定にだけ使い、pilot で観測した効果へ閾値を寄せない。外部市場尺度、分析上の測定分解能、または明示した実務上の許容幅から本番前に固定する。

実現 best depth、spread、resilience は媒介変数として記録する。q の主効果を推定する際の control には使わず、機構分析でのみ扱う。

## 4. カレンダー

### Week 1｜8/16(日)〜8/22(土)｜30時間

**目的**: scope を凍結し、YH007 隔離と Evidence Contract v0.1 の設計を終える。

| 日付 | 上限 | 作業 |
|---|---|---|
| 8/16 日 | 3h | 12週の claim・非claim・成果物を1ページに固定。Claude/Cursor の監査対象と出力形式を確認 |
| 8/17 月 | 3h | YH007 の finding→spec→atlas→進捗文書の依存グラフ作成 |
| 8/18 火 | 3h | 影響対象を verified / unverifiable / contaminated-by-reference に分類 |
| 8/19 水 | 5.5h | エンジン非依存の run record・event log schema を作成。Level-I OFI に必要な共通 field を固定 |
| 8/20 木 | 5.5h | effective config、導出式ID、環境・RNG 記録を仕様化 |
| 8/21 金 | 5h | exact / semantic canary の fixture と、Cont 型拘束の解析仕様を作成 |
| 8/22 土 | 5h | Evidence Contract v0.1 review。Cont harness の入力・出力を固定し、仕様追加を停止 |

- 期限: 8/22 23:59
- 成果: Contract draft、YH007 隔離表、incident report 骨子。

### Week 2｜8/23(日)〜8/29(土)｜30時間

**目的**: pilot を走らせるための最小実装と性能計測を完了する。

| 日付 | 上限 | 作業 |
|---|---|---|
| 8/23 日 | 2h | agent が作成した PR とテスト結果だけを確認。新機能は足さない |
| 8/24 月 | 5h | effective config→event log→bundle の hash chain と canary CI を統合 |
| 8/25 火 | 5h | q を固定 N_S 内の置換率として実装・unit test |
| 8/26 水 | 5h | 分散一致 phi=0 対照、permutation 対照、seed pairing を実装 |
| 8/27 木 | 5h | Cont 型拘束を実装し、best depth、spread、外生 shock 後の recovery、OFI/return 出力を追加 |
| 8/28 金 | 5h | 20/60 agents × 2,000/5,000 steps × 3反復。wall time、peak RSS を記録 |
| 8/29 土 | 3h | Cont baseline smoke test、同時実行可能数、pilot 上限、n_steps 候補を確定。Gate G0 判定 |

**Gate G0(8/29)**: 実効値結合、canary、q、二つの対照、2×2性能表、Cont harness の smoke test が通ること。

- 8/29 を hard deadline とし、Week 3 を救済枠に使わない。
- Gate に含めた項目が一つでも未達なら、本番マップを中止し、同日中に Fallback Track F へ切り替える。Week 3 での救済実装は行わない。
- README 自動生成、UI、汎用 plugin 化は未達でも pilot へ進める。

### Week 3｜8/30(日)〜9/5(土)｜30時間

**目的**: 小規模 pilot で推定量・SESOI・本番条件を固定する。

- 基準 L/E、N_S 一水準で core grid の pilot を実行する。
- pilot は最大200 paired seed-blocks に制限する。
- Welch segment 長、segment 数、対象周波数帯、coherence 推定分散を決める。
- Week 2 で実装した Cont 型拘束を pilot 出力へ適用し、価格変更 event 除外後の OFI 関係と depth-impact 関数形を確認する。
- YH007 incident report v0.1 を 9/1 までに書く。
- 原尺度 SESOI、主要 contrast、等価性範囲、停止規則を固定する。
- response surface、contrast、Holm 補正、TOST、主要図を生成する解析スクリプトを完成させ、pilot データで端から端まで実行する。

**Gate G1(9/5)**: preregistration v1、解析スクリプト、依存 lock、confirmatory seed 一覧を一体で seal する。G1 に救済日は置かない。

- Cont 拘束を満たさない場合、実装誤りの確認に最大4時間だけ使う。parameter tuning は行わず、未達なら「市場に関する主張」を降ろし、「当該エンジンの応答」に限定する。
- Cont 拘束が未達の場合、Week 5 の L/E 展開を中止し、その30時間を Tier 1 第二エンジンの前倒しへ振り替える。
- RAM または時間超過なら、n_steps とセル数を削る。seed hold-out と control は削らない。
- 9/5 以降、pilot seed は confirmatory 分析へ再利用しない。
- 9/5 時点で解析スクリプトが端から端まで通らなければ Week 4 へ進まない。Fallback Track F へ切り替える。

### Week 4｜9/6(日)〜9/12(土)｜30時間

**目的**: 基準 L/E における core confirmatory map を完成する。

- phi × q × scope の core grid を hold-out seed で実行する。
- treatment/control を同じ seed block で対応させる。
- 実行中にセル、統計量、外れ値除外規則を変更しない。
- 実行失敗は理由とともに bundle へ残し、黙って再 seed しない。
- core confirmatory は最大1,200 engine-runs を上限とする。
- 全 run 完了後、seal 済み解析コマンドを confirmatory dataset に対して一度だけ実行する。

**Gate G2(9/12)**: 主要 contrast と等価性を、事前登録どおりに一度だけ判定する。

- SESOI を超え hold-out で再現 → Week 5 の L/E・N_S 拡張へ進む。
- SESOI 内で等価 → 拡張を中止し、帰無結果の精密化へ進む。
- pilot だけで見え hold-out で消失 → 事前登録済みの追加 replication block を1回だけ実行。再調整はしない。

### Week 5｜9/13(日)〜9/19(土)｜30時間

**目的**: 境界の機構とスケーリングを必要最小限で確認する。

**Cont 拘束を満たし、かつ効果が確認された場合**

- 境界候補周辺だけで3L × 2E を展開する。
- 同じ q で異なる qN_S、同じ qN_S で異なる q となる N_S 部分 factorial を実行する。
- 追加実験は合計800 engine-runs を上限とする。

**Cont 拘束が未達、または効果が等価・不安定だった場合**

- L/E 全面展開と N_S 拡張を行わない。
- 最大6時間だけ、等価性区間を狭めるための事前指定 replication に使う。
- 残り24時間以上を Tier 1 第二エンジンへ振り替える。
- contract v0.1 と事前作成した conformance test だけを実装者へ渡し、PAMS adapter や参照実装を見せない。
- contract を Tier 1 へ都合よく変更しない。変更が不可避なら v0.2 として理由を記録し、PAMS も再適合させる。
- 結論を「当該エンジン内の効果」または「測定可能だが実質効果を確認できない」に切り替える。

### Week 6｜9/20(日)〜9/26(土)｜30時間

**目的**: Engine 1 の結果を凍結し、監査可能な bundle にする。

- 9/20〜9/21 に Founder Audit を行う。Yuito が spec から主要図、contrast、SESOI、除外 run、bundle まで説明できるか確認する。
- 説明できない図は公開対象から外す。計算の誤りが疑われる場合は、事前登録で許可された diagnostic だけを実行し、confirmatory claim を事後変更しない。
- 9/24 までに説明不能が解消しなければ、その claim と図を落とす。主要図を落とす場合は 10/4 の接触を止め、methods ＋ case study へ縮小する。
- 未実行セルの理由、失敗 run、除外 run を含めて run registry を固定する。
- realized liquidity を媒介変数として機構分析する。
- Cont 型外部拘束の合否を別表にする。
- 全 bundle で effective config、canary、code・environment digest を検査する。
- 主要表、主要図、補助図を生成する。

**Gate G3(9/26)**: Engine 1 evidence freeze。

- Founder Audit に合格していることを freeze 条件にする。
- 9/26 以降は結果を見た上での追加セルを禁止する。
- 不完全でも完了セルを固定し、欠落を明示する。10月へ計算負債を持ち越さない。

### Week 7｜9/27(日)〜10/3(土)｜20時間

**目的**: 修士課程開始前に、Engine 1 の研究成果を人に説明できる形へ変える。

- 9/30 までに transfer-map figure v1、1ページ要約、bundle index を完成する。
- YH007 incident report を事例研究として完成する。
- 事例研究では「同様の欠陥が業界一般に存在する」とは主張しない。存在可能性と検出 workflow の価値だけを示す。
- AIC 議事録と FSB コメントから問題保有者候補15人を確定する。
- インタビュー質問へ「参照実装を自社 simulator で実行可能か、障害は何か」を追加する。
- 9/30 に図、bundle、1ページ要約、質問票を一体で承認または却下する。承認された場合は 10/4 送付分を予約する。
- 10/1 以降は修士課程を優先し、最初の2週を各8時間へ切り替える。

### Week 8｜10/4(日)〜10/10(土)｜8時間

**目的**: 接触を開始し、Tier 1 第二エンジンを contract へ接続する。

- 9/30 に承認済みの場合、10/4 に候補15人のうち最大8人へ依頼する。VC には送らない。
- contract v0.1 と conformance test だけを渡し、最小 ZI ＋ 連続ダブルオークションの Tier 1 実装を開始する。
- 実装者には PAMS adapter、PAMS 側の event 変換コード、既存 canary 実装を見せない。
- 修士課程の履修・研究室立ち上げを優先し、8時間を超えない。

### Week 9｜10/11(日)〜10/17(土)｜8時間

**目的**: Tier 1 による構造的な移植性を判定する。

- Tier 1 の effective config、exact canary、semantic canary、共通 event schema 適合を完了する。
- Engine 1 で重要だった6〜12条件のうち、計算可能な最小集合を実行する。
- 絶対値一致ではなく、事前指定した符号、順位、応答形状、原尺度差を比較する。
- engine 差を消すための事後調整はしない。

**Gate G4a(10/17)**: structural portability 判定。

- 適合・再現 → contract が二つの自作エンジンをまたげたと限定して記述する。
- 適合・非再現 → engine dependence を結果にする。
- 不適合 → contract の PAMS 依存箇所を compatibility report にする。無断で contract を書き換えない。

Tier 1 は外部コードへの移植を証明しない。A2 を「構造的移植性 A2a」と「外部移植性 A2b」に分け、A2b は Tier 2 でのみ評価する。

### Week 10｜10/18(日)〜10/24(土)｜10時間

**目的**: WP1 の Methods・Results を進め、Tier 2 の可否を短時間で判断する。

- Methods、preregistration deviation、Results を執筆する。
- 科学仮説 A、構造的移植性 A2a、外部移植性 A2b、実務仮説 B を章で分離する。
- ABIDES 等について最大6時間の compatibility spike を行う。メッセージ順序、個別レイテンシ、order lifecycle の写像を表にする。
- 6時間で最小 run へ届かなければ Tier 2 全面接続を中止し、compatibility report を成果物にする。
- Week 6 の Founder Audit を踏まえ、外部向け資料の表現だけを最終確認する。実験設計の再監査は行わない。

**Gate G4b(10/24)**: 外部エンジンで最小 run が通れば Week 11 の代表条件へ進み、通らなければ compatibility report で停止する。

### Week 11｜10/25(日)〜10/31(土)｜10時間

**目的**: Discussion と実務検証を進める。

- Discussion、limitations、null result 時の打ち切り基準を書く。
- 日程が合った問題インタビューを実施し、3〜5件完了を目標にする。
- 「現在の workflow」「同じ乖離の検出方法」「自社 simulator で参照実装を走らせられるか」を記録する。
- YH007 一件から業界全体へ一般化せず、インタビューを B の別証拠として扱う。
- Tier 2 が最小 run へ到達済みの場合だけ、残り時間で代表条件を実行する。
- 公開名の変更要否を判断する。名称検討は2時間で打ち切り、研究を遅らせない。

### Week 12｜11/1(日)〜11/7(土)｜14時間

**目的**: 研究・コード・事業判断を一度凍結する。

- WP1 v0.1、case note、Evidence Contract v0.1、bundle index を固定する。
- 再現手順を fresh environment で一度だけ実行する。
- deviations、失敗 run、未検証 claim を公開用表にする。
- A2a と A2b を混同せず、Tier 2 未達なら外部移植性を未検証と明記する。
- 12週間の decision memo を書く。

**最終判断(11/7)**

| 観測 | 判断 |
|---|---|
| 転写効果あり・Tier 2 外部エンジンでも再現・実務家が検査を試せる | tool / data 路線の設計パートナー探索へ進む |
| 転写効果あり・Tier 1 のみ再現 | contract の構造的移植性だけを主張し、外部移植性と製品化判断を保留 |
| 転写効果あり・第二エンジンで非再現 | engine dependence を研究主題にし、汎用製品主張を保留 |
| 効果は SESOI 内・contract は有用 | null WP ＋ provenance case study として完結。製品化判断を延期 |
| contract 構築に12週を使い、confirmatory 結果なし | 計画失敗。追加基盤整備を止め、Sieve 研究 program を縮小 |
| 実務家が既存手法で明確に対処できる | その手法を取り込み、実務仮説 B を棄却または限定 |

## 5. Fallback Track F: G0 または G1 で本番マップを中止した場合

本番マップ中止後も基盤機能を増やし続けない。研究成果を provenance failure の事例研究と検出 workflow の評価へ切り替える。

| 期間 | 成果 |
|---|---|
| Week 3(8/30〜9/5) | YH007 incident report v0.1、1 treatment ＋ 1 matched control の micro-pilot、Evidence Contract v0.1 freeze |
| Week 4(9/6〜9/12) | stale manifest、導出式誤り、AR(1)符号反転、環境/RNG変更の fault injection。effective config と canary が何を検出・見逃すかを表にする |
| Week 5(9/13〜9/19) | contract 仕様だけを見て Tier 1 最小エンジンを実装し、conformance test を実行 |
| Week 6(9/20〜9/26) | PAMS と Tier 1 の contract 適合比較、Founder Audit、case-study evidence freeze |
| Week 7(9/27〜10/3) | incident flow 図、canary coverage 表、1ページ要約、問題保有者15人、10/4 接触の承認判断 |
| Week 8〜9(10/4〜10/17) | 承認済みなら依頼を送付。Tier 2 は compatibility spike までに限定 |
| Week 10〜11(10/18〜10/31) | provenance methods paper / case note 執筆、3〜5件の問題インタビュー |
| Week 12(11/1〜11/7) | Evidence Contract、Tier 1 fixture、case note、decision memo を凍結して終了 |

G1 で中止した場合は、完了済みの Week 3 成果を保持し、Week 4 からこの表へ合流する。この track では transfer map、転写境界、外部市場への妥当性を主張しない。

## 6. 毎週の運用規則

- 日曜冒頭30分で、その週の「完了条件」と削る作業を決める。
- 土曜末に gate 判定を1ページで残す。未達項目を翌週へ無条件に繰り越さない。
- 新規論点は backlog へ置き、当週の scope へ入れない。
- confirmatory 開始後のコード変更は、bug fix を含めて新しい bundle version と replication 対象にする。
- agent が生成した PR は、目的・入力・期待出力・test・失敗時挙動を Yuito が説明できなければ merge しない。
- 睡眠を削って遅れを回収しない。10月の週8〜10時間、11月第1週の14時間上限を維持する。

## 7. この計画で意図的に行わないこと

- 180セル×30 seeds の全面実行を最初から約束しない。
- YH007 の条件不明 finding を推測で復元しない。
- canary をコード全体の正しさの証明として扱わない。
- realized liquidity を主効果から回帰で除去しない。
- pilot 結果を見て SESOI を効果へ寄せない。
- 一件の内部事故から金融機関一般の需要を主張しない。
- WP1 の図と監査可能な bundle がない状態で VC へ接触しない。
