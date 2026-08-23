# 監査 backlog(当週 scope 外の是正・確認項目)

## 権威の分担(並行権威を作らないための宣言)

- **作業項目(コードに触るもの)の正は本ファイル。** カレンダー側は本ファイルを
  参照するだけで、内容を複製しない。
- **日程と gate の正はカレンダー文書。** 本ファイルは日程を複製しない
  (下記の日付言及は転記先の識別のためのポインタであり、正ではない)。
- 理由: 並行権威は本プロジェクトで再現している失敗様式である(下記
  incident 材料 3 件)。P4 の research_status.yaml(単一状態源)と同じ原則を
  backlog にも適用する。
- **claim・非claim の正は `W1D1_claims_freeze.md` (v1.0)。** 日程・gate・11/7
  決定表の正は `sieve_12_week_calendar_2026-08-16.md` §4。
- **commit 規則(2026-08-20 Yuito 承認)**: commit は Yuito の明示指示がある場合のみ
  CC が実行可。自発 commit は禁止。指示文言がセッションログに残ることをもって
  委任記録とする。**本行を規則文の正本とし、プロンプトでは再掲せず参照のみとする**
  (規則文自体を書き写すと、規則の並行典拠という同型の穴を開けることになるため)。
- **統合規則(2026-08-23 追加)**: セッション branch は**当日中に main へ統合する**
  (統合自体は委任可)。**統合前の内容を「repo 収容済み」と呼ばない。**
  根拠は事故 1 件: 8/20 の成果(claims 凍結 v1.0・12 週カレンダー v1.1)が
  branch 上に 2 日留まった結果、8/21 セッションからは「両 repo のどこにも無い」と
  観測され、読めば済んだ §2.1 を推定で埋めて 8 項目中 2 項目を誤った。
  branch にあることと repo にあることは別である。
- **委任適用記録**: `9c9fc07`(claims 収容) / `78419d5`(カレンダー収容) /
  `c51cf59`(カレンダーヘッダへ claim 記述の優先順位宣言を追記) / 本起票コミット自身
  (自己参照のため hash は本文に持てない — `git log` 上で本行を追加したコミットが
  4 件目にあたる)。

## P0〜P5 進捗表(claims 草稿 §4 から移設)

| P | 内容 | 状態 |
|---|---|---|
| P0 | read-only 棚卸し | 完了・main マージ済み |
| P1 | effective_config | 未着手 |
| P2 | canary | 未着手 |
| P3 | q 置換＋対照群 | 未着手 |
| P4 | repo 状態源一元化 | 保留 — 解除前提は下記§「P4 解除の前提(YH007-8)」を正とする |
| P5 | 2×2 ベンチマーク | 未着手 |

- 日程・週割当は入れない(カレンダー権限)。
- **番号衝突の注意**: 本表の P 番号は financial-abm-lab の監査系列である。sieve の
  コミット `6cce339`「external audit P1/P2」は**別系列**で、そちらは sieve main へ
  マージ済み。本表の P1/P2 は未着手であり、両者を同一視しないこと
  (「宣言された状態」と「実際の状態」の乖離は下記 incident 材料の再発型)。
- 状態列は 2026-08-16 に repo 現況と照合済み(P0 は `746b854` 以降マージ条件 1-5・
  Week 0 クローズまで origin/main、P1 の effective_config は言及のみで実装なし、
  P2 の canary は 3 repo に不在、P4 の research_status.yaml は不在)。

## P4 解除の前提(YH007-8)

1. **P3-F を修正較正値(φ=0.615/σ=3.81e-3)で再走し、agg parity 参照値を
   確定する(P4 解除の前提)。** 現状の正確な位置づけ:
   **P3-F は旧キャリブレーション下での条件付き合格であり、修正較正下での
   合格は未確認**。合格判定 (i)(kronos recenter の |ret_acf[1]| < 0.1)は
   φ/σ 非関与だが、判定 (ii) の agg parity は旧較正参照値 0.102
   (= 旧較正 zi_matched の agg と確定、`P0_yh007_recalibration_rerun.md` §3)に
   対して行われた。修正較正の参照は 0.072。Kronos 実機(KRONOS_PATH)が必要。
2. **P4 解除は、依存鎖(round6 → §3.8 recenter → P3-F)の全リンクが一次
   artifact を持つまで保留。** 2026-08-13 時点: round6 の符号構造(二重乖離)は
   両較正の一次 artifact で再確定済み。**P3-F リンクはそもそも修正較正で
   未検証**(1 リンクが弱くなったのではなく、未検証だったことが確定した)。

## P3(q 置換設計)pilot への診断項目追加

- **「q=1、修正キャリブレーション、N_L 固定の条件で、約定率と出来高が
  許容帯に入るか」を pilot 診断に含める。** 根拠: 修正 φ/σ では全 agent が
  matched_ar1 の 1-group 構成で agg_rate が 0.0015(目標帯下限 0.05)に崩壊する
  (`P0_yh007_recalibration_rerun.md` §2)。q=1 は戦略群全員が採用者になる条件で
  あり、縮退すればヒートマップ最上段が「高採用率」でなく「市場が動かない領域」に
  なって転写量の測定が出来高ゼロと交絡する。N_L 固定の置換設計では転移しない
  可能性が高いが、グリッド確定前(Week 3 pilot)に確認し、縮退なら q 上端を
  0.9 に切るか N_L を厚くするかを事前判断する。

## Evidence Contract v0.1 / run record schema への要件(週内仕様作業へ転記)

1. **キャリブレーション定数は、コード既定値ではなく外部由来の入力アーティファクト
   として扱う。** source reference と digest を持ち、run record に「どの
   キャリブレーション artifact を使ったか」を記録する。理由:
   - φ=0.615/σ=3.81e-3 自体の provenance は判定根拠 (c)(Kronos 実機による
     外部測定で、現状再実行不能)。この性質は artifact メタデータとして明示
     されるべきで、コード定数では表現できない。
   - 現状は値の変更 = コード 9 箇所の変更で、git blame でしか追えない。
     入力アーティファクト化すれば config hash が動き、P1 の hash chain が
     そのまま変更を検出する。
2. **不確実性の表記規約**: ±・区間の定義(SD か SE か、ddof、n)を出力・文書の
   両方で必須にする。実例: p3d の集計表の ± が SD(ddof=1) であることは
   スクリプトを読まないと分からず、レビューで識別可否の判断を誤らせかけた。
3. **CLI override 経路の実効値検査**: `--phi-ar1`/`--sigma-ar1-abs` 型の
   override は「spec と違う値で回せるが実効値の検査が無い」状態を作る。
   P1 仕様に「**CLI override 経路が effective config に解決済みで反映され、
   spec 期待値との照合対象になる**」ことを明示的に含める。
   **P1 完了までの運用**: この経路を通った run の args 入り出力 JSON は必ず保存。
4. **主張・findings には流動性・約定診断量(agg 等)を添える**: 対照 run で
   ret_acf は較正を識別せず agg のみが決定的(paired t=−65)だったのに、元の
   主張が agg を記録していなかったため遡及識別が不能だった実例
   (P3 の「流動性診断量を全 run の出力に含める」要件の先取り根拠)。
5. **atlas 各セルの「反証されていない」に最小検出可能効果量を必須添付。**
   表示仕様は Contract v0.2 候補。
6. **contract v0.1 に外部の書き手を 1 名以上入れる。** Week 7 接触の目的として明記。

## 事業形態・governance(11/7 decision memo で判断)

1. **commercial simulator と neutral benchmark governance の利益相反。**
   11/7 decision memo で組織分離を含め判断する。
2. **初期 data moat は customer realized data ではなく falsification atlas。**
3. **Week 7 インタビューに運営主体の条件を開かせる設問を追加**(5 択は後段)。
4. **ground truth 不要評価の一般化構想(property-based evaluation
   infrastructure)。**「rejector ＋ ground truth 割当最適化」への再定式化を含む。
   検討は 11/7 以降(claims v1.0 §2「範囲」の非 claim 行と対)。

## 恒久クローズ(再探索しない)

- **claims 草稿 §5 項目 9 以降**: 原本未コミットのため両側で復元不能を確認
  (2026-08-16)。再探索しない。確認範囲: 3 repo の作業ツリー、全ブランチ・
  全コミットの履歴検索(追加/削除/改名を含む)、Google Drive のタイトル・全文検索。
  いずれも 0 件。**追記(2026-08-20)**: 凍結本文 v1.0 は
  `docs/audit/W1D1_claims_freeze.md` として本 repo にコミットされ、外部のみの
  正本ではなくなった。ただし v1.0 は草稿 §5 を削除した後の版であり、項目 9 以降は
  v1.0 にも含まれない。本クローズは維持する。

## Week 3 pilot への引き継ぎ(P0 是正の副産物 — 数値と方針)

1. **power 計算の事前値: σ_d ≈ 0.075**(ret_acf[1] の paired diff SD =
   0.0266 × √8。2,000 step・legacy 2-group 構成、seeds 0..7、
   `P0_rerun_yh007_8_p3d.json` vs `P0_control_oldvalues_yh007_8_p3d.json`)。
   対応のある t 検定(両側 α=0.05、検出力 0.8)での必要 seed 数:

   | 検出したい差 Δ | 必要 seed 数 |
   |---|---|
   | 0.04 | 約 28 |
   | 0.02 | 約 111 |
   | 0.01 | 約 444 |

   元計画の「seeds 30 以上」は Δ=0.04 をぎりぎり検出できる水準であり、
   それより小さい効果の主張には足りない。**注意**: この σ_d は 2,000 step の
   もの。ACF 推定の分散はおよそ step 数に反比例するため、20,000 step なら
   σ_d は約 1/3、必要 seed 数は約 1/10 になる — **seed 数と step 数は独立に
   決められない。Week 3 の power 計算は両方を同時に扱うこと**。

   **セル対比(層別)の σ_d — Week 3 のセル単位 power にはこちらを使う**:
   2×2 の層別対応差の σ_d は **0.062〜0.099**(ret_acf[1]、2,000 step。
   修正較正: S3 層別 0.088/0.071、S2 層別 0.068/0.065。旧較正: 0.083/0.073、
   0.099/0.062)。較正対比の 0.075 と同水準で、上の必要 seed 数表はセル対比にも
   そのまま適用できる。**プール推定量の SE(修正較正で 0.011、seed 内負相関
   r=−0.57 による相殺の産物)から seed 数を出してはならない — セル単位の
   検出力を過大評価し、必要 seed 数を過少に見積もる。**
2. **主推定量を local projection(既知の外生 ε_t への応答)に置く方針を
   Week 3 の事前登録要件に記録する。** 根拠: 同一 run・同一 seed・同一介入で
   agg(注文フロー段階)t=−65 に対し ret_acf[1](価格段階)t=−1.5 — 測ろうと
   している転写経路そのものに沿って測定 S/N が大きく劣化している。ACF ベースの
   推定量は主推定量にせず記述統計に降ろす。ε_t は自前で生成しているので、
   二次モーメントの要約でなく既知の外生入力を条件にでき、S/N は原理的に
   大きく改善する。**power 計算は local projection の推定量に対して行う**
   (ret_acf の σ_d で seed 数を決めると大幅に過剰になる見込み)。

## incident report 材料(事例メモ)

- **一次 artifact(判定根拠 a)は対象 findings 11 件中 0 件**。出力は既定で
  /tmp、一切未コミット。対の数字: 2026-08-13 の再走・対照 run により
  `P0_rerun_yh007_8_p3d.json` が YH007-8 系で最初の一次 artifact になった
  (0 件 → 2 件)。
- **単一の再発型:「宣言された基準・状態」と「実際に強制・実行される基準・状態」の
  乖離**(3 例 + 未遂 1 例。個別の事故ではなく同じ型の再発として記述できる):
  1. φ/σ: spec の宣言(修正値を使うこと)と実行コードの強制(旧値ハードコード)
     が 2026-07-21〜08-13 の間乖離(更新漏れとして顕在化)
  2. Stage B: README の宣言(未着手)と parity 文書の実状(GREEN)が乖離
  3. agg 帯: docstring・spec の宣言([0.05, 0.20])と assert の強制(0.02..0.40)
     が**初版 aa6d299 から**乖離(numeric literal 差分監査で時系列を確定、
     マージ条件 3 で解消)
  4. (未遂)backlog: カレンダーとリポジトリの並行権威になりかけ、分担宣言で遮断
- **監査手順が監査者自身の誤りを訂正した事例**: numeric literal 差分(条件 5)は
  「6 コミット中に他の緩和がないか」を探すために提案されたが、結果は逆に
  「6 コミット中の閾値変更ゼロ + 緩和は初版からの持ち越し」を確定し、
  「修理の途中で検査が弱くなった」という当初のレビュー所見(diff を取らずに
  時系列を断定したもの)を覆した。手順が仮説の向きに関わらず機能した実例として、
  証拠 bundle の説得材料になる。
- 存在しない文書パス `specs/004-yh007-strategy-feedback-loop.md` が、計画文書 →
  監査プロンプト → 監査対象の指定へと無検証で伝播した(P0 §0 で訂正)。
- **統計が支える範囲を超えた結論が 2 回続いた**(「実質解消」→「識別成立」、
  いずれも点推定の一致・不一致からの結論で、対応差の検定で棄却)。監査プロンプト
  共通ヘッダに規約 8(対応のある差 + SE 必須、± の定義明示)と 8b(比・
  パーセントは差より危険 — 差が n.s. なら比は報告しない、比の CI 必須)が
  追加された経緯。
- **記録されていた量は、利用可能なチャネルの中で最も情報量が少ないものだった。**
  元の頑健性再走の記録は ret_acf[1](較正への感応が t≈−1.5 で n.s.)のみで、
  同じ run が必ず出力していた agg(t=−65、実質重なりなしで較正を識別)は
  記録されなかった。その結果 provenance は復元不能で恒久クローズとなった。
  **何を保存するかの選択自体が provenance の一部である**。

## W1D6(2026-08-21)起票 — Evidence Contract v0.1 の実装から出た項目

成果物は `yuitokyouni/sieve` の branch `claude/schema-v2-fixture-7c82kx` に
ある(`schemas/` の 3 件、`docs/contract/` の 6 文書、`fixtures/canary/`、
`tools/cont_harness_reference.py`)。**内容は複製しない。本節は作業項目のみ。**

### A. 契約 gap(2026-08-22 review の議題)

`sieve:docs/contract/contract_gaps.md` に選択肢・推奨・根拠を記載済み。
本節は「決めること」の一覧であり、判断内容は転記しない。

1. **G1 Level-I 状態の取得経路を決める。** 2026-08-19 の「Level-I OFI に必要な
   共通 field」の判断が **両 repo のどこにも無い**(下記 D-1)。schema 側は
   header の `l1_availability` で経路を宣言できるようにしてあるので schema は
   ブロックしていないが、決定自体は未了。**Cont harness は inline を要求するので、
   Week 3 の主推定量がこの決定に依存する。**
2. **G2 `actor_role` に `exogenous_harness` を採るか決める。** 無いと shock 注入
   order が識別不能。BACKLOG 既存項目「主推定量を local projection(既知の外生
   ε_t への応答)に置く」も、外生入力が log 上で識別できることに依存する。
3. **G4 同時刻 event の順序と `cause_event_id` の整合を決める。**
4. **G5 終端状態記録と `order_id` の共通 surface 昇格を決める。** 現状、数量保存則
   が共通 8 field だけでは閉じない。canary は終端 `book_level` event で回避して
   いる(新 field も ext.* も使わない)が、per-order 版は order_id 無しでは不可能。
5. **G6 binary observation file(parquet 等)の canonical form を決める。** 現在は
   file byte のみ hash。writer 設定違いで意味的に同一の parquet が別 digest になる。
6. **G7 共通 surface 比較表が観測 domain まで digest で固定している件の是非。**
7. **G8 conformance profile の FAIL 項目リストを作る。** Q1 で schema は permissive、
   severity は profile 層と確定済み。profile 自体が未作成。D-1 に依存。

### B. 既存 schema への変更要求(承認範囲外につき本日は起票のみ)

Cont harness 出力が `MetricSpec` で表現できるかを確認した結果、3 箇所で不可。

8. **G9 `MetricSpec` に `parameters` が無い。** `BaselineSpec` にはある。
   interval / window / depth / shock protocol という「何を計算したかを変える
   knob」が spec に載らない。**これは本 backlog の incident 材料と同型**
   (宣言された基準と実際に実行される基準の乖離)。推奨は `BaselineSpec` と
   同形の `parameters` 追加。
9. **G10 `TestResult` に `standard_error` が無い。** `ci_low`/`ci_high` はあるが、
   本 backlog の不確実性表記規約(SD か SE か・ddof・n を必須)を CI は担えない。
   加えて `TestResult` 1 件 = scalar 1 件なので、window 別の
   (β̂_i, SE_i, R²_i) ベクトルの置き場が無い。
10. **G11 `MetricRequirements` が event log 入力を表現できない。** column /
    geometry 指向であり、「`ordering.tie_break` が undefined でない log」「
    `l1_availability` が inline の log」という要求が書けない。

    8〜10 は「event stream 推定量を metric registry の中に置くか横に置くか」という
    1 つの問いなので、**まとめて決める**こと。別々に答えると半端に非互換な
    答えが 3 つできる。

### C. 実装(freeze 後)

11. **RunManifest v2 / EventLog / CanaryResult を `sieve.core.models` の pydantic
    model にし、`sieve schemas export` の対象に入れる。** 現状は hand-authored の
    JSON Schema として並置(既存 schema を触らないため)。移行時に
    `tests/unit/test_cli.py::test_schemas_export` の期待も更新が要る。
12. **canary を CI に統合する(8/24)。** `fixtures/canary/run_canary.py` は exit code
    が verdict(0 MATCH / 1 MISMATCH / 2 UNVERIFIABLE / 3 PENDING_GENERATION)なので
    パース不要。標準ライブラリのみ・1 秒未満で走る。
13. **Cont estimator 用の非退化 fixture を用意する。** canary fixture は 40 step の
    toy で価格がほとんど動かず(328 pair 中 price-changing 5)、β̂ はほぼ 0、
    λ は not estimable。**canary fixture は Cont estimator の妥当な入力ではない。**
    I/O 形状の確認には使えるが、推定量の数値的な確認には別の入力が要る。

### D. 所在確認が必要な文書(本日ブロックされた項目)

14. **§2.1 必須 10 項目を定義しているカレンダー原本の所在。** 両 repo に無く
    (`§2.1` の全文検索は `imported/` 配下の無関係文書のみ)、**「§2.1 全項目 →
    具体 field」解決表(8/22 凍結条件)が埋められなかった。** field 側は完成して
    いる(`sieve:docs/contract/evidence_contract_v0.1.md` §7 Table A)ので、項目
    一覧さえあれば機械的に埋まる。項目名を推測で埋めることはしていない。
    G8(profile の FAIL リスト)も同じ文書に依存する。
15. **F8-R1〜R3 の隔離表の所在。** `F8-R` は両 repo に 1 件も無い。よって
    「対応差計算に対して成立、run 再生成は /tmp 未 digest により対象外」という
    検証範囲注記は**どこにも反映していない**。注記文は失われないよう
    2026-08-21 のセッション出力に保存してある。存在しない表を新規作成すると、
    注記が乗るべき権威そのものを捏造することになるため作成しなかった。
16. **`claims v1.0` の所在。** Cont harness の位置づけの参照先だが未確認。
    近いものとして `imported/PROV-ABM-atlas/docs/program_claims_v1.md` が
    あるが、同一である確証は無い。
17. **commit 規則(2026-08-20 承認)の正本行。** 本ファイルのヘッダにあるはず
    との指示だったが、現ヘッダは「権威の分担」宣言のみで commit 規則の記載は
    無い。**委任記録行も存在せず、前倒し 2 件(カレンダーヘッダ追記 /
    BACKLOG 起票 commit)に対応する commit も両 repo の履歴に無い**
    (`origin/main` からの差分はゼロだった)。したがって hash の追記は
    行っていない。規則本文を知らないまま復元すると、それ自体が並行権威になる。


## W1D7(2026-08-23)起票 — v0.1 凍結レビューから出た項目

成果物は sieve `main`(`docs/contract/`・`schemas/`・`fixtures/canary/`)。
**内容は複製しない。本節は作業項目のみ。** 凍結時点の状態は
`W1_review.md` を正とする。

### A. 凍結後(v0.2 以降・post-G0)

1. **G7 比較表の互換/観測分離。** canary は現行の厳格版のまま維持と決定済み。
   一般 conformance check 用に「互換性半分(field 有無・型・単位=安定)」と
   「観測半分(値域=情報のみ、hash しない)」へ割るかは post-G0。
   precondition の意味が変わるため凍結日の判断にしない。
2. **Parquet content の canonical form。** 現在 contract digest を持てるのは
   canonical serialization を定義した 4 形式のみで、Parquet は byte digest しか
   無い。byte digest には何も束縛していないので当面の実害は無いが、
   observation を chain に載せるには要る。
3. **G9〜G11 の非対称そのもの。** 8/23 は「harness を registry の横に置く」で
   解決したが、`MetricSpec` に `parameters` が無い(`BaselineSpec` にはある)、
   `TestResult` に `standard_error` が無い、`MetricRequirements` が event stream
   入力を表現できない、の 3 点は残っている。**3 件は 1 つの問いなのでまとめて
   決める。**
4. **pydantic 化。** 3 + 3 schema を `core/models.py` へ移す場合、
   **「`sieve schemas export` の出力 == 規範ファイル」の test を通ることを条件と
   する**(規範は schema ファイル側、実装は models.py 側という宣言を守るため)。
   現在は export guard で上書きを禁止している。

### B. 8/24 の前提として今日確定した事項(作業ではなく制約)

5. **Engine 1 の exact fixture は full runtime fingerprint domain で、固定
   container で 8/24 に生成する。** toy engine の interpreter 除外は
   harness self-test 限定であり contract 上の前例ではない(fixture と registry の
   両方に注記済み)。
6. **8/24 は「Engine 1 fixture の mint」と「hash chain 構築」の 2 件を同日に
   持つ。** 当初は後者のみが割り当てられていた。時間超過の唯一の予見リスク。

### B2. セッション運用(D4 由来、8/23)

6b. **push 前にローカルで full suite を回せる環境を用意する。** 8/23 に main の
   CI を 2 回赤にした根本原因は、セッション環境に numpy が無く、標準ライブラリ
   だけで走る contract 系 test しか実行していなかったこと。CI との差分を放置した
   まま push していた。`uv pip install -e ".[dev]" -c constraints.txt` を
   セッション冒頭の手順に入れる(3.11/3.12 両方)。
6c. **ガードテストで短い一般語の部分文字列検索をしない。** `getpass.getuser()` が
   runner 上で "runner" を返し、例中の "example-runner" に部分一致して偽陽性に
   なった。揮発値の混入検査は「性質を再現テストで検査する」形にする
   (環境変数を変えて再生成し byte 一致を要求)。

### C. 復元・判断待ち(W1_review.md §6 と対)

7. 8/18 隔離表(F8-R1〜R3)が全 branch に不在。書き直すか恒久クローズかは
   Yuito 判断。検証範囲注記は W1_review.md に逐語保存済み。
8. 8/19 対照表(20 項目)が**どの ref にも一度もコミットされていない**
   (両 repo の全履歴を検索して確定)。凍結内容との逐項チェックは実施できていない。
   復元は 8/20 chat からの手動投入のみ。
8b. **「chat 出力のみ」型の紛失を止める規則が要る。** 統合規則(当日 main 統合)は
   「branch 孤立」型にしか効かない。8/19 対照表は commit 禁止セッションの
   成果物で、branch にすら乗っていない。**耐久性のある成果物(対照表・解決表・
   仕様判断)を chat だけに出力して終わるセッション設計を禁じる**か、
   commit 禁止セッションの成果物を翌セッションが repo へ収容する義務を
   明文化するか。凍結後の運用規則として起票。
9. incident report 骨子が不在。**追補③の 4 項目は骨子復元が条件のため未適用**
   (部分適用もしていない)。内訳は W1_review.md §6 の 5〜8。
10. 2026-08-19 の Level-I 判断が不在。G1 は提示された選択肢の上で決定した。
