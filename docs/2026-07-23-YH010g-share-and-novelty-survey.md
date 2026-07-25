# YH010-g 日本の助言会社利用状況の一次ソース ＆ AI議決権エージェント新規性再サーベイ

- 調査日: 2026-07-23
- 消し込み対象: `docs/2026-07-23-YH010g-prior-art.md` §4 の残アクション2件（日本シェア一次ソース／(c)新規性再サーベイ）

---

## Part 1: 日本市場におけるISS/Glass Lewis利用状況の一次ソース

### 結論

- **投資家側利用率の一次数値は存在する**（下記1・2）。シミュレータ（ワークストリームB）の追随エージェント混成比のキャリブレーションに直接使える。
- **「ISS対GLの日本国内シェア」を直接示す公的数値は存在しない**。ISS 6割・GL 3割等の流通数値は米国市場のもの。日本のシェアは金融庁2019年参考資料のグローバル顧客数（ISS約2,000社 / GL約1,300社）からの間接推定にとどまる——**論文では「日本の直接シェア統計は存在しない」ことを限界として明記し、利用率×利用形態の分布（下記）でパラメータ化する**。

### 一次ソース一覧

1. **資産運用業協会（旧・日本投資顧問業協会）「日本版スチュワードシップ・コードへの対応等に関するアンケート（第11回）」**（2025年9–10月実施、回答262/288社）
   [PDF](https://www.imaj.or.jp/statistics/report/pdf-cms/steward_enq2025.pdf)
   - 助言機関活用: 全体192社中**60社（31.3%）**、日本株残高有の111社では**42社（37.8%）**。活用機関数の平均**1.3社**。
   - 活用形態（60社中・複数回答）: 「参考にする」43.3% / 「自社ガイドラインに沿った行使案作成を委託」46.7% / 「親会社等（利益相反局面）で助言に沿う」23.3% / 「基本助言に沿う」15.0% / **「必ず助言に沿う」1.7%**。
   - **含意**: 日本では自己申告上のrobo-voting（機械的追従）はほぼ皆無で、「カスタムポリシーの執行委託」と「利益相反局面の限定利用」が主形態。**米国のrobo-voting実測（下記Part 2の6）と対照的な構図であり、シミュレータの追随タイプ混成（完全追随/閾値追随/独立）の日本パラメータはこの分布から設定する**。
2. **投資信託協会（現・資産運用業協会）「日本版スチュワードシップ・コードに関するアンケート調査」**（令和8年3月公表、国内株自社運用の正会員70社）
   [PDF](https://www.imaj.or.jp/statistics/report/pdf-cms/2025_plan_survey.pdf) / [調査一覧](https://www.imaj.or.jp/statistics/report/voting/)
   - 助言機関利用: **70社中43社（61.4%）**（前年58.6%）。利益相反管理として「助言会社の推奨適用」32社（45.7%）。
   - 注: 1と母集団・設問が異なる（投信運用者中心・利用の定義が広い）ため、両数値の併記が必要。
3. **金融庁「スチュワードシップ活動の実態に関する調査」**（2025-06-02、フォローアップ会議資料4）
   [PDF](https://www.fsa.go.jp/singi/follow-up/siryou/20250602/04.pdf)
   - 定性調査（ヒアリング先にISS Inc.明記）。匿名「助言会社B社」の日本体制（日本株専属アナリスト7名・平均在籍14年・東京常駐、繁忙期臨時約50名）を記録。「カスタムポリシー要請の増加」の記述。
4. **金融庁 スチュワードシップ・コードに関する有識者検討会 参考資料**（2019-10-02 資料4）
   [PDF](https://www.fsa.go.jp/singi/stewardship/siryou/20191002/04.pdf)
   - 両社概要: **ISS 115市場・約44,000総会・顧客約2,000社 / GL 100市場・約20,000総会・顧客約1,300社**（グローバル値）。2020年再改訂コードの助言会社向け原則8につながった検討会。
5. 補足: 経産省「新時代の株主総会プロセスの在り方研究会」[一覧](https://www.meti.go.jp/shingikai/economy/shin_sokai_process/index.html)（利用率の具体数値は未特定）／JPX金商法研究会・梅本剛正「わが国の議決権行使助言会社の規制」（2021）[PDF](https://www.jpx.co.jp/corporate/research-study/research-group/nlsgeu000005ontt-att/20211224_2.pdf)

### 日本市場対象の学術実証（μ条件付け・識別設計の参照点）

- **Ishida & Kochiyama (2024)** "ISS Proxy Voting Guidelines and ROE Management", *European Financial Management* 30:375-402（査読済み）[DOI](https://onlinelibrary.wiley.com/doi/10.1111/eufm.12418) — ISSのROE 5%基準（2015年2月導入）後、日本企業が5%達成に向けた利益調整を行うことを実証。**助言基準が企業行動を変える＝ID-g3（閾値RDD）の日本での実行可能性とconfound（発行体側の閾値操作）の両方を示す重要文献**。RDD設計時にthreshold manipulation（McCrary検定等）が必須。
- **Miyachi & Takeda (2024)** "Empirical study on voting results and proxy advisor recommendations in Japan", *JIFMIM*（査読済み）[DOI](https://www.sciencedirect.com/science/article/abs/pii/S1042443124000398) — 2010–2022年の日本の総会議案1,025件でISS/GL反対推奨と賛成率の負の相関を実証。**日本でID-g1（推奨分裂）に使える推奨データが構成可能なことの実例**（データソースの確認は原文精読で）。
- **Masumoto & Takeda (2022)** "Market reactions to proxy advisory companies' recommendations in Japan", *Finance Research Letters* 50（査読済み）[DOI](https://www.sciencedirect.com/science/article/abs/pii/S1544612322005104) — 報道された推奨125件のイベントスタディ。

---

## Part 2: AI議決権行使エージェント新規性再サーベイ（2025–2026）

### 結論

**重複度「高」は未発見 → 新規性(c)（ISS/GL複占が生む投票相関のABM測定＋介入実験）への直接の脅威は現時点でない。**ただし包囲網は急速に狭まっている:
- Lee & Souther (2025): LLMがISS推奨を**79%再現**——「AI化してもモノカルチャーは残る」論点の先取り
- Bakker/Demir系グループ（Cooperative AI Foundation支援）がAI代理投票×助言会社評価を連作中——次作がシミュレーション・介入系に踏み込む蓋然性
- Matsusaka-Shu系のrobo-voting実証が「複占→投票相関」の測定を米国実データで確立済み

**差別化の置き所: 「日本市場パラメータ（Part 1の利用率・利用形態分布）＋ABM上の反実仮想介入（助言者数・ポリシー重複度の操作＝IV-1）」**。定点観測は四半期ごとに継続すること。

### 文献リスト（重複度順）

**重複度: 中**

1. **Matsusaka & Shu** "Robo-Voting: Does Delegated Proxy Voting Pose a Challenge for Shareholder Democracy?" (SSRN 4564648 / Seattle Univ. Law Review) [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4564648) — 2008–2021年の投信14,582本・6,500万票超で機械的追従を定量化: **ISSほぼ完全追従 2007年7%→2021年23%、GL 0%→9%、2021年に投信の33%がrobo-voting**（ISS 22%/GL 4%/経営陣6%）。米国実データの記述統計であり介入なし。**この実測値はシミュレータの米国側キャリブレーション目標にそのまま使える**（日本側はPart 1の1）。
2. **Matsusaka & Shu** "The proxy advisory industry: Influencing and being influenced" (*JFE* 2024, 査読済み) [DOI](https://www.sciencedirect.com/science/article/abs/pii/S0304405X24000333)
3. **Lee & Souther** "Beyond Bias: AI as a Proxy Advisor" (SSRN WP, 2025-08) [報道](https://techxplore.com/news/2025-09-ai-successfully-outcomes-iss-guidelines.html) — ISS公開ガイドライン+議案情報からAIが推奨を生成、**ISS推奨と79%一致**。ISS推奨を統制してもAI "for"推奨は賛成票を2–6%押し上げる（米国株主提案2009–2021）。
4. **Bakker, Couvert, Demir & Michaely** "The AI Proxy Advisor" (WP, 2026-04, HKU) [PDF](https://hkujcesgri.hku.hk/wp-content/uploads/2026/04/The-AI-Proxy-Advisor.pdf) — RDD+因果MLでAI推奨追従がISS/GL追従より高リターンと主張。
5. **Fulay, Demir, Hines-Pierce, Landemore & Bakker** "Shareholder Democracy with AI Representatives" (arXiv:2510.23475, 2025-10, 未査読) [arXiv](https://arxiv.org/abs/2510.23475) — 個人株主選好を学習したAI代理投票の提案（prior-art文書で既知）。
6. **Hu, Malenko & Zytnick** "Other People's Votes: The Law and Economics of Proxy Advice" (SSRN 6798600, 2026-05) [SSRN](https://ssrn.com/abstract=6798600) — 直近の包括レビュー（関連研究地図として有用）。

**重複度: 低〜中**

7. Majumdar et al. "Generative AI voting: fair collective choice is resilient to LLM biases and inconsistencies" (*EPJ Data Science* 2025, 査読済み; arXiv:2406.11871) [DOI](https://link.springer.com/article/10.1140/epjds/s13688-025-00612-3) — 5万超のLLM投票ペルソナ×81実選挙。LLM代理投票のバイアス・均質性の方法論的隣接（政治投票文脈）。

**重複度: 低**（金融ABMだが投票なし／法学検討）

8. Wang "Outsourcing Voting to AI" (*Fordham J. Corp. & Fin. L.* 29(1), 2023–24) [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4413315)
9. TwinMarket (arXiv:2502.01506) / StockAgent (arXiv:2407.18957) / LLM-ABM金融市場 (arXiv:2510.12189) / Shachi (arXiv:2509.21862) / 行動一貫性検証 (arXiv:2602.07023) / FlockVote (arXiv:2512.05982) / LLM Voting (arXiv:2402.01766)

### 実務動向（研究ではないが動機付け・時事に使用可）

- Kekst CNC「AI as the New Proxy Advisor」(Harvard Law School Forum, 2026-04-20) [記事](https://corpgov.law.harvard.edu/2026/04/20/ai-as-the-new-proxy-advisor-reshaping-shareholder-activism-communications/) — 委任状争奪戦でAI推奨はISS/GL歴史的推奨から大きく乖離との分析。
- **J.P. Morganが2026年1月に助言会社購読を打ち切り自社AIエンジンへ移行**、2025-12-11の米大統領令が助言会社規制見直しを指示 [記事](https://corpgov.law.harvard.edu/2026/03/16/will-curbs-on-proxy-advisors-make-shareholder-votes-less-predictable/) — **「複占の解体とAI内製化への移行期」という時代文脈は、IV-1（助言者数・構成の反実仮想）の政策的意義を直接高める**。

### YH010-gへの設計上の含意（3点）

1. **キャリブレーションの二本立て**: 追随タイプ混成比は日本（資産運用業協会: 機械的追従ほぼ0%・執行委託47%・利益相反限定23%）と米国（Matsusaka-Shu: robo-voting 33%）で大きく異なる。シミュレータは両パラメータ設定を持ち、日本設定を主系にする。
2. **ID-g3の追加検定**: Ishida & Kochiyamaが示す発行体側の閾値操作（ROE 5%そばへの利益調整）はRDDの識別を脅かす。McCrary型の密度検定を受入基準に追加すること。
3. **時事の追い風**: J.P. Morgan離脱・米大統領令・AI助言の登場は「助言者構成が変化したとき投票相関と厚生はどうなるか」というIV-1の問いを現実の政策問題にした。モチベーション節はこの2026年の転換点から書ける。
