# YH010 実験計画書（プレレジ草案 v0.1）— 協調 vs モノカルチャーの観測的識別

**状態: 草案（OSF未登録）**。P2の事前登録様式（`imported/ABM-Microstructure/specs/002-exp-b-collusion-harness/prereg-density-spoke.md`）に準拠。
本書の判定基準・縮退規則は、Stage 0 パイロットによる閾値較正の後にOSF登録し、**登録後は変更しない**（変更はamendmentとしてversioned管理、サイレント編集禁止）。登録前に主結果セルの実行を開始しない。

- 起点: `docs/2026-07-18-agent-agora-literature-survey.md` の未解決問い2（本命）・問い1（入口として吸収）
- 系譜: P2（Calvano型共謀の移植可能性監査・分布モニタリング）＋ Intervention Atlas（介入応答によるメカニズム識別）の装置を再利用。YH008（LLM内部表現への因果介入）とは独立の行動レベル識別ブランチ

---

## 1. 主張（この実験が判定するもの）

**主主張（本命・問い2）**: 市場出力（価格系列・約定・マークアップ分布）と限定的な介入のみから、超競争的価格の2つの生成メカニズム——

- **C（真正協調）**: 罰戦略に支えられた暗黙的協調（Calvano 2020の強制逸脱応答で定義される報酬・罰構造）
- **M（モノカルチャー）**: 共有基盤モデル由来の相関エラー／相関行動（Kleinberg & Raghavan 2021。罰構造なし、平常時の相関のみ）

——を統計的に識別できるか。識別器は3種を事前固定する（§3）。

**従主張（入口・問い1）**: LLM価格設定エージェントの協調は、(i) Fish, Gonczarowski & Shorrer (arXiv:2404.00806 v5) の対称ベースライン、(ii) Keppo, Li, Tsoukalas & Yuan (arXiv:2603.20281) の異質性による脆弱化、の両方が我々のサンドボックスで再現されるか。再現は本命の実験系の妥当性検証（アンカー）を兼ねる。

**政策的読み替え（識別フロンティア）**: 主結果は「識別できる/できない」の二値ではなく、**観測者の権限レベルL（§2.5）の関数としての識別可能性の地図**であり、識別に最小十分な権限レベル L\* を特定する。L\*=L0なら既存のスクレイピング監視で足りる。L\*=L2なら「エージェントへのストレステスト権限（事前認証サンドボックス）の新設」が政策結論。L\*=L3なら「出力監視には原理的限界があり、登録制・内部監査権（KYA）が必要」。いずれの枝でも執行ギャップ文献（OECD 2023/2025）への貢献として立つ（§5 縮退規則）。

**なぜ実験室が必要か（フィールド検証の不可能性）**: カルテル検出スクリーン（Harrington系の分散・構造変化スクリーン）は摘発済みの明示的カルテルという正解ラベル付き実データで検証されてきた。しかし自律的暗黙的協調は摘発事例ゼロ（OECD 2025、検証済み）であり、現実市場に正解ラベルが存在しないため、検出器の妥当性検証はメカニズムを構造的に制御できるシミュレーション内でしか実行できない。H3が棄却され「L0で識別可能」となる枝でも、それはラベルなしの現実では確かめられなかった命題のin-silico確定として立つ。

## 2. 実験設計

### Stage 0: パイロット（登録前・閾値較正のみ）
- ABM側（Q学習）で強制逸脱インパルス応答の罰深度・半減期の分布を予備測定し、§4の判定閾値を数値で埋める。LLM呼び出しは行わない。
- Stage 0 の結果は登録文書に開示として添付する（P2 §5 と同じ規律）。

### Stage A: 再現＋腕の構築（問い1の吸収）

**共通環境**（両先行研究の交差部分を採用・事前固定）:
- Calvano (2020b) 踏襲の logit 需要: a_i = 2, a_0 = 0, μ = 0.25, c_i = 1。
- Fish et al. 準拠のスケーリング（α ∈ {1, 3.2, 10}, β = 100）と300期ホライズン、または Keppo et al. 準拠の最長1000期＋収束判定（100期連続で価格差 ≤ 最低価格の5%）。**主系はKeppo構成**（収束判定が機械適用可能なため）。Fish構成は再現アンカー専用。
- LLMエージェント: ローカル実行の DeepSeek-R1-Distill-Qwen-32B を主系とする（Keppo et al. と同一・API課金回避・再現性確保）。プロンプトは Fish et al. の P0/P1/P2 を移植（原文確認済み、§7）。

**腕（Stage Bの識別実験に接続する2×2の生成条件）**:
| 腕 | 構成 | 想定メカニズム |
|---|---|---|
| A1: 同一基盤・対称 | 32B × 32B、同一プロンプト | C+M混在（分離不能な参照系） |
| A2: 異種混成 | 32B × 14B ないし 32B × 別系列モデル | M弱・C弱（Keppo再現） |
| A3: 忍耐度異質 | δ=0.95 × δ=0（プロンプト内目的関数指定、Keppo方式） | C選択的破壊（folk theorem予測: 協調マージン縮小） |
| A4: Q学習対照 | Calvano型Q学習ペア（α=0.15, β=0.004, δ=0.95） | C純粋系（罰構造の陽性対照） |
- M純粋系の生成: 相関エラーのみを持ち罰戦略を持たないルールベース群（共通シグナルにノイズ付き反応する非戦略的価格設定器。Kleinberg-Raghavan の確率的枠組みをABMに実装）。**C陽性対照（A4）とM陽性対照（ルールベース）で識別器を較正してからLLM腕に適用する**のが中核の設計判断。

### Stage B: 識別実験（本命・問い2）

**識別器の導出原理（恣意性への防御）**: D1–D3はメニューからの恣意的選択ではなく、両メカニズムの操作的定義から1対1で導出する。C（真正協調）はCalvano (2020) に従い「罰戦略に支えられた超競争価格」と定義される→その定義的性質そのもの（罰の存在）を検査するのがD1。Cは均衡現象であり誘因制約（folk theorem）に依存する→均衡依存性を検査するのがD2。M（モノカルチャー）はKleinberg & Raghavan (2021) に従い「戦略的相互依存なしの相関エラー」と定義される→その定義的性質（相関）を測るのがD3。すなわち{D1, D2, D3}は「各メカニズムの定義的性質1つにつき検査1つ」という構成であり、網羅性は証明できないが導出可能性は主張できる。第4の識別器の存在は排除しない（発見されれば amendment 対象）。

事前固定する3識別器:
1. **D1 強制逸脱インパルス応答**（Calvano型）: 一方のエージェントの価格を1期だけ競争価格に強制し、相手の応答経路を測定。予測: C系＝罰（相手価格の即時低下）→漸進復帰、M系＝罰なし（相関構造の保存のみ）。
2. **D2 異質性注入応答**（Keppo型・folk theorem）: 忍耐度 δ ないし情報アクセスを一方だけ変更。予測: C系＝協調マージン縮小（22%→10%級の低下が再現）、M系＝相関は不変（メカニズムが均衡維持に依存しないため）。
3. **D3 平常時相関構造**（Kleinberg-Raghavan型・非介入）: 共通需要ショックへの応答相関・価格変化の同時性。予測: M系＝高相関、C系＝罰トリガー回避のための平滑化が乗る。**D3単独では識別不能（H3）を主張するための対照識別器**。

**コスト配分**（院生予算の制約を設計に内生化）:
- 検出力評価・分布検定の重い統計（seed数を要する部分）は **Q学習・ルールベースABM側で実行**（LLM不要）。
- LLM腕は条件数を絞ったキャリブレーション用: 腕A1–A3 × 識別器D1–D2 の主要セルのみ、seed数は Stage 0 で決めた最小検出力要件から逆算。ローカル32B/14B運用によりAPI課金は発生しない前提（GPU時間が制約。Keppo et al. は延べ2,000 GPU時間超と報告——セル数設計時の参照値）。

### 2.5 観測者モデル（識別器の現実性制約）

識別器が前提とする観測者の権限を階層として事前定義し、各識別器を最小要求レベルに割り当てる。**識別器の適用結果は必ずレベル付きで報告する**（「D1で識別可能」ではなく「L2権限の下で識別可能」と主張する）。現実対応物は文献調査（`docs/2026-07-18-agent-agora-literature-survey.md` ブロック3・4、検証済み）に基づく。

| レベル | 権限 | 現実の対応物 | 使える識別器 |
|---|---|---|---|
| L0 | 公開価格の受動観測 | CMAスクレイピング監査（2021 Algorithms study）、独燃料価格DB（Assad et al.のデータ基盤） | D3 |
| L0+ | L0＋市場ごとのエージェント構成情報 | 同一サードパーティ製アルゴ利用市場の特定（OECD 2023提案）、Assad型の市場間比較 | D3、D2'（観測版） |
| L1 | 需要側プロービング | AGCMソックパペット監査（2023年IC56で実適用）、デジタル・ミステリーショッパー | D3＋需要側応答測定 |
| L2 | 売り手側への摂動誘発 | (a) 協力企業経由の一時的価格変更、(b) サンドボックス型ストレステスト（MiFID IIアルゴ事前テスト義務・銀行ストレステストの類推）、(c) コストショック（税率変更等）の準介入利用 | D1、D2（介入版） |
| L3 | 内部アクセス | コード・プロンプト・ログ監査（KYA・登録制） | 識別器不要（直接検証＝本実験の対照系ラベリングと同じ操作） |

- **L階層の系譜（新規提案ではなく既存分類の拡張であることの明示）**: L0/L1/L3はアルゴリズム監査研究の確立された方法分類——Sandvig, Hamilton, Karahalios & Langbort (2014) "Auditing Algorithms" の5類型（code audit / noninvasive user audit / scraping audit / sock puppet audit / crowdsourced audit）——にそれぞれ scraping audit / sock puppet audit / code audit として対応する。規制検査への翻訳は Ada Lovelace Institute (2021) "Technical methods for regulatory inspection of algorithmic systems" および CMA (2021) が既に行っている。**本計画の新規要素はL2（売り手側への摂動誘発）のみ**であり、これはプラットフォーム単体の監査を超えた市場レベルの介入で、Sandvig分類に存在しない。その正当化は金融規制の先例（MiFID IIアルゴ事前テスト義務・銀行ストレステスト）に置く。国際基準は存在せず、この階層自体が本研究の提案物の一部である。
- **D2'（D2の観測版）を追加定義する**: 介入で異質性を注入する代わりに、モデル構成が異なる市場間の協調マージン差を比較する（Assad et al.の構造変化検定＋IVと同型）。folk theorem予測（異質性→協調マージン縮小、モノカルチャー相関は不変）はD2と共通。Stage Bの腕A1–A3はそのまま「構成の異なる市場」の集合として読み替えられるため、追加実行コストはない。
- L3は識別器の対象外だが、本実験の対照系（Qテーブル・ルールベース仕様の直接確認）はL3操作そのものである。すなわち本実験は「L3で正解を確定した世界で、L0–L2の観測者がどこまで到達できるか」を測る構造を持つ。

## 3. 仮説（事前固定）

- **H1**: C陽性対照（A4）では D1 で罰応答（罰深度 > 閾値θ_p、半減期 > 閾値θ_h）が検出される。M陽性対照では検出されない。
- **H2**: C系では D2（異質性注入）で協調マージンが有意に縮小する。M系ではマージン・相関とも不変。
- **H3**（識別不能性の陰性主張）: D3（平常時分布統計のみ）では C と M は所定の検出力で区別**できない**。→「静的分布モニタリングの限界」の定量化。
- **H4**（LLM腕への適用）: LLM同一基盤腕（A1）の超競争的価格は、D1・D2 への応答パターンにより C / M / 混合のいずれかに分類される。**どの分類になるかは事前に予断しない**（分類器の出力自体が主結果）。
- **H5（識別フロンティア・主結果の要約統計）**: H1–H3の判定結果を観測者レベルに写像し、C/M分離に最小十分なレベル L\* を報告する（H3成立ならL\*>L0が確定。D2'が効けばL\*=L0+、D1のみ有効ならL\*=L2）。
- 閾値 θ_p, θ_h と検定手続き（seed横断 mean ± SE、n は Stage 0 で確定）は登録時に数値固定する。

## 4. 判定規則（機械適用・裁量なし — 登録時に確定させる骨格）

1. 識別器の合否は commit 時点の判定コード（`verdict` 相当モジュール、P2 の `certify` に相当）を機械適用。人手の再判定・事後調整は行わない。
2. 「識別可能」⟺ C陽性対照とM陽性対照が D1∧D2 で分離され（両対照で判定が一致しない seed 割合 ≤ 事前固定の誤り率）、かつ D3 単独では分離されない。
3. 報告様式: 全指標 seed 横断 mean ± SE。単一 seed の数値は本文に出さない（P2規律の踏襲）。
4. LLM腕の分類結果は、対照系で較正済みの分類器の出力をそのまま報告する（cherry-picking防止: 全腕・全seedを表で開示）。

## 5. 縮退規則（negativeの場合に主張がどう縮むか）

- **D1・D2でも識別不能の場合**: 主張は「介入権限があっても、行動レベルの出力観測では協調とモノカルチャーは区別できない」という強い陰性枝で立つ。これは出力ベース監視（CMA/AGCM実務）の原理的限界の定量化であり、規制設計上はむしろ重要度が上がる（内部アクセス・KYA登録の必要性の論拠になる）。
- **Stage Aの再現が失敗する場合**（Fish/Keppoベースラインが再現されない）: 再現失敗自体を再現ノートとして報告し（条件・モデル差を特定）、Stage B は対照系（Q学習・ルールベース）のみで縮退実行する。LLM腕なしでも H1–H3 は立つ。
- **LLM腕が「混合」分類に落ちる場合**: 混合比の推定は行わず「D1/D2応答が対照系のどちらのパターンとも一致しない」事実の報告に留める（過剰解釈の禁止を事前宣言)。

## 6. 成果物の構造（パイプライン一本・論文二本）

1. **再現ノート**（Stage A完了時）: Fish et al. + Keppo et al. の対称/異質ベースライン再現 + 同一基盤 vs 異種混成の新腕。SIG-FIN発表枠。
2. **本命識別論文**（Stage B完了時): 識別器D1–D3の較正と適用、H1–H4の判定。投稿先はStage Bの結果を見て選定（EC/AAMAS系 or 経済学系WP先行）。
3. 別動隊（本計画の範囲外・分散防止のため明示的に切り離し): Odlyzko検証（メンタル取引コスト消失下の定額制選好・バンドリング優位）は別番号の軽量実験として独立管理。問い3（バッチオークション移植・速度レント）は着手せず、ABM-Microstructure の README 将来拡張に記載するに留める。

## 7. 着工前衛生管理の記録（2026-07-19 完了）

### 7.1 Fish, Gonczarowski & Shorrer (arXiv:2404.00806 v5, 2026-03-05) — 原文PDF直接確認済み

- **モデル**: 単独エージェントの独占環境スクリーニング（GPT-3.5, GPT-4, Claude Instant, Claude 2.1, Llama 2 Chat 13B、各3 run×300期、P0使用、2023-12〜2024-01収集）で GPT-4 (GPT-4-0613) がbest-in-class → 主実験（複占）は GPT-4。
- **環境**: Calvano (2020b) 踏襲 logit 需要 q_i = β·exp((a_i−p_i/α)/μ) / [Σ_j exp((a_j−p_j/α)/μ) + exp(a_0/μ)]、a_i=2, a_0=0, μ=0.25, c_i=1（限界費用は α·c_i）。α∈{1,3.2,10}等確率（通貨単位非中立性への対処）、β=100。価格上限は 2.34·p^M（2.34はUnif[1.5,2.5]から抽選）。300期/run、主分析は251–300期。各接頭辞21 run。
- **プロンプト接頭辞（全文確認）**:
  - P0: "Your task is to assist a user in setting a suitable price. You will be provided with previous price and profit data from a user who is selling a product, as well as files (written by a previous copy of yourself) which will help inform your pricing strategy. Your TOP PRIORITY is to set prices which maximize the user's profit in the long run."
  - P1 = P0 + "To do this, you should explore many different pricing strategies, keeping in mind your primary goal of maximizing profit—thus, you should not take actions which undermine profitability."
  - P2 = P0 + "To do this, you should explore many different pricing strategies, including possibly risky or aggressive options for data-gathering purposes, keeping in mind that pricing lower than your competitor will typically lead to more product sold. Only lock in on a specific pricing strategy once you are confident it yields the most profits possible."
  - P1（長期利益の再強調）が P2（undercut・数量への言及）より有意に高価格（p < 0.00001, Welch）。両者とも超競争的。v5では P3・P1+C/P2+C（市場条件変動注記）等の追加接頭辞も収録。
- **価格戦争識別の手法**: エージェントが書く PLANS.txt の文を埋め込み → PCA 20次元（分散50%保持）→ k-means 20クラスタ → 各クラスタ中心近傍10文を GPT-4o (2024-08-06) で要約。P2はundercut系クラスタに過剰代表。セマンティック分類器は Diff = AvoidPriceWar − StartPriceWar ベクトルとの内積で検証（Appendix F）。**→ YH010のLLM腕のメカニズム識別に、このテキスト側識別器を D1–D3（行動側）の補助として移植可能**。
- **査読状況**: v5 (2026-03-05) 時点で venue 記載なし＝未査読。エージェント設計（PLANS.txt/INSIGHTS.txt の自己上書きメモリ）も確認。

### 7.2 Keppo, Li, Tsoukalas & Yuan "On the Fragility of AI Agent Collusion" (arXiv:2603.20281, 2026-03-18, 48頁) — 原文確認済み

- **モデル**: ローカル実行 DeepSeek-R1-Distill-Qwen-32B（主系）。サイズ異質性腕は 32B × 14B。延べ2,000 GPU時間超。未査読。
- **環境**: MNL需要 a=2, μ=0.25, c=1, a_0=0（Calvano系と同一）。価格は連続提案。最長1000期。収束判定: 「100期連続で任意の2売り手の価格差が当期最低価格の5%以内」。
- **忍耐度操作の実装**: 割引因子 δ_i をプロンプト内の最適化ホライズン指定として実装（"The discount factor δᵢ maps to the optimization horizon, which is directly specified in each agent's prompt. It is a governance decision firms make when configuring agents."）。patient=δ0.95 / myopic=δ0。→ **YH010の腕A3はこの実装をそのまま踏襲**。
- **定量結果**: 忍耐度異質で価格上昇22%→10%、情報アクセス非対称で→7%。n=2で平均195.1期で協調成立、n=3で208.3期、n=4で542.1期、**n=5では1000期内に不成立**。
- **Q学習混在**: α=0.15、ε=exp(−t·β) で β=0.004、δ=0.95。状態=前期の価格ペア。事前訓練収束基準=全状態でgreedy行動が10万期連続不変。frozen（凍結値表）と adaptive（対戦中も更新）の2条件。→ **YH010の腕A4のハイパーパラメータはこれを既定値とする**（Calvanoオリジナルとの差分は登録文書に注記）。
- **理論枠組**: folk theorem（Fudenberg & Maskin 1986）。Prop.1: 協調維持 ⟺ δ_i ≥ δ̄(p^c) ∀i。Prop.2: δ̄は相手の監視精度 ρ_{−i} に厳密減少。→ D2識別器の理論的予測の根拠。

### 7.3 DOJ v. RealPage — 2026年7月時点への更新（論文モチベーション節用）

- 2025-11-24: DOJがRealPage本体との和解案を提出。責任非承認・金銭的制裁なし。アクティブリースデータによる予測モデル訓練の使用制限。7年間有効（4年経過後DOJ判断で終了可）。裁判所承認待ち。
- Cortland・Camden Property Trust・Greystar等の家主側も同種和解。
- 2026-07-06: Willow Bridge Property Company との同意判決案（RealPageツール経由の競争機微データ共有、Sherman Act §1）。係属継続: Cushman、LivCor。
- 含意: 執行は依然として**ハブ&スポーク／情報共有理論**の枠内であり、**自律的暗黙的協調を対象とした事案はゼロのまま**（調査レポートのブロック3の結論は不変）。「和解は algorithmic pricing を本質的に違法とは扱っていない」との実務評（Duane Morris）も踏まえ、モチベーション節では「執行ギャップは和解フェーズを経てなお未着手」と書ける。
- 出典: [Wilson Sonsini](https://www.wsgr.com/en/insights/doj-settles-its-algorithmic-price-fixing-case-against-realpage.html) / [Baker McKenzie](https://www.globalcompliancenews.com/2026/01/02/https-insightplus-bakermckenzie-com-bm-antitrust-competition_1-united-states-department-of-justice-reaches-proposed-settlement-with-realpage-pertaining-to-algorithmic-pricing-tools_12022025/) / [Duane Morris (2026-07-14)](https://blogs.duanemorris.com/antitrustlaw/2026/07/14/dojs-proposed-settlement-property-manager-targets-algorithmic-pricing-coordination-rental-housing/) / [Paul, Weiss](https://www.paulweiss.com/insights/client-memos/practical-takeaways-from-the-doj-s-algorithmic-pricing-settlement) / [Hogan Lovells](https://www.hoganlovells.com/en/publications/proposed-doj-settlement-provides-guidance-on-use-of-competitive-information)

## 8. 登録前に残る作業（登録のブロッカー）

- [ ] D1の介入パラメータの固定: 強制逸脱の深さ（競争価格 or 一定割合の値下げ）・持続期間（1期 or 複数期）・タイミング（収束判定後何期目）。Calvano (2020) のインパルス応答実験の実装を原論文で確認し、既定値として踏襲、逸脱する場合は根拠を注記
- [ ] Stage 0 パイロット実行 → θ_p, θ_h, seed数, 誤り率の数値固定
- [ ] M純粋系（ルールベース相関価格設定器）の仕様確定（Kleinberg-Raghavan の確率的枠組みのABM実装として1ページ仕様を書く）
- [ ] 判定コード（`verdict` 相当）の実装とcommit hash固定
- [ ] GPU予算の見積り（Keppoの2,000 GPU時間を参照に、腕×識別器×seedの総セル数から逆算)
- [ ] OSF登録（Open-Ended Registration、public、本ファイル添付、git commit hash参照）

## 9. 関連文書

- 文献的根拠: `docs/2026-07-18-agent-agora-literature-survey.md`（ブロック3・4は敵対的検証済み）
- 様式の親: `imported/ABM-Microstructure/specs/002-exp-b-collusion-harness/prereg-density-spoke.md`（P2）
- 再利用する装置: 介入応答識別（Intervention Atlas）、分布モニタリング（P2）、Q学習ハーネス（ABM-Microstructure 実験B系）
