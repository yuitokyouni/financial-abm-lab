# YH010-g 議決権行使 個別開示の目録（9社実査）— Task 1前提資料

- 実査日: 2026-07-23（全URLはWebFetch/curlで実取得確認。「未確認」明記箇所を除く）
- 消し込み対象: `specs/YH010g_HANDOFF.md` §10 残課題2（目録化）・残課題3（robots/利用規約確認）
- 検証済み実ファイル: 大和 202506.xlsx（13,086行）/ アモーヴァ 25q1_voting_results_jp.xlsx（14,364行）/ ニッセイ report_ex2507.xlsx / りそな giketuken_201901.pdf（Wayback経由）— スクラッチパッドに保存済み（セッション終了で消えるため、パイロット着工時に再取得すること）

## サマリー表

| 社 | 個別開示URL | 形式 | 個別開示の起点 | Excel/CSV化 | 頻度 | robots/取得性 |
|---|---|---|---|---|---|---|
| アセットマネジメントOne | am-one.co.jp/company/voting/ | **PDFのみ** | 2017Q2(4-6月) | なし | 四半期 | robots無し・制約なし |
| 野村AM | nomura-am.co.jp/special/esg/vote/ | PDF+xlsx | 2017Q1(1-3月)※最古 | 2023Q1〜 | 四半期 | robots無し。規約文言は9社中最強 |
| 三菱UFJ信託 | tr.mufg.jp/houjin/jutaku/about_stewardship.html | **xlsx全期間** | 2017Q2 | **2017Q2〜全期間** | 四半期 | robots無し・制約なし |
| 三菱UFJ AM | am.mufg.jp/investment_policy/responsible_stewardshipcode.html | PDF→xlsx | 2016年度(粒度未確認) | 2023Q1〜 | 四半期(2018Q3〜) | **WAF/403あり・robots未確認** |
| 三井住友トラストAM | smtam.jp/company/policy/voting/result/ | PDF+**CSV** | 2017Q2 | CSV 2023Q1〜 | 四半期 | robots無し。ファイルURLのID連番が非規則 |
| 三井住友DS AM | smd-am.co.jp/corporate/responsible_investment/voting/report/ | PDF+xlsx | 2019Q2(現体制)/旧2社別掲2017〜 | 2023Q1〜 | 四半期 | robots有り（該当パス許可） |
| 大和AM | daiwa-am.co.jp/company/stewardship/voting-results.html | PDF+xlsx | **2019年1月(月次)** | 2023年1月〜 | **月次** | robots無し・制約なし |
| アモーヴァAM(旧日興) | amova-am.com/about/vote/results | PDF+xlsx | 2017年6月総会 | 2023Q1〜 | 四半期 | **robots有り・該当パス明示的に許可** |
| りそなAM | resona-am.co.jp/sustainability/voting.html | PDF+xls | 2018Q3(10-12月) | 2023Q1〜 | 四半期 | **エッジ403（海外IP遮断）— 自動取得不可** |
| ニッセイAM | nam.co.jp/company/responsibleinvestor/cvr.html | PDF+xlsx | 2017年6月総会 | 2023Q2〜 | 四半期 | robots無し（規約に「解析」禁止文言あり） |

## 横断所見（パイプライン設計に効く事実）

1. **Excel/CSVの分水嶺は2023年**: 9社中8社が2023年に機械可読形式を開始（例外: 三菱UFJ信託は**2017年から全期間xlsx**、アセマネOneは現在も全期間PDF）。→ 2017–2022年の遡及分析にはPDF表抽出が必須。**三菱UFJ信託だけはPDF抽出なしで9年分の個別データが取れる**。
2. **列構成が判明した3社**（実ファイル検証済み）:
   - 大和: コード/企業名/総会種類/総会日/議案番号/議案種類(会社・株主)/議案分類/役員情報/判断/利益相反/賛否判断理由/不統一行使
   - アモーヴァ: 企業コード/企業名/総会種類/総会日/親議案番号/子議案番号/議案分類/提案者/弊社賛否/賛否理由/備考（集計シート＋個別開示シートの2部構成）
   - ニッセイ: 議案番号/候補者番号/議案区分/提案/判断/主な判断理由（月別シート分割に注意）
   → 共通スキーマ: (証券コード, 総会日, 総会種別, 親議案番号, 子議案/候補者番号, 議案分類, 提案者, 賛否, 理由テキスト) でほぼ吸収可能。HANDOFF §4 A-1の名寄せ設計と整合。
3. **行使理由テキストの粒度差**: ニッセイ=全議案に理由 / 野村=2019Q4以降全議案 / りそな=会社提案への反対理由+株主提案への賛成理由 / 大和=反対議案のみ。→ 理由テキストを使う分析（将来のLLM分類）はニッセイ・野村が最良。
4. **棄権**: 実査した範囲の個別ファイルでは賛成/反対のみで棄権値は未確認（りそなの集計部には棄権・白紙委任区分あり）。→ HANDOFF §3の「棄権系の別コード化」は、個別開示に棄権がほぼ現れない可能性を織り込み、Task 1で実データの値域を確定してからエンコーディングを固定すること。
5. **取得性の障害は2社のみ**: りそな（Akamaiエッジで海外IP遮断——日本国内IPからの挙動は未確認。手動DL+sha256固定の代替経路が必要）と三菱UFJ AM（WAF/403の可能性、robots未確認）。他7社はrobots制約なし。ただし全社とも利用規約に一般的な無断複製禁止条項があり（野村・大和は「電子的・機械的方法を問わず」の文言、ニッセイは「解析」禁止文言）、**取得は低頻度・研究目的・原本保存(sha256)+出典明記の方針で行い、規約上の懸念があれば手動ダウンロードに切り替える**。
6. **社名・体制の変遷に注意**: 日興AM→アモーヴァAM（2025、ドメイン移行中・旧URLは301）/ 三菱UFJ国際投信→三菱UFJ AM（2023）/ 三井住友AM+大和住銀=三井住友DS AM（2019、旧2社アーカイブ別掲）/ 三井住友信託銀行分はsmtb.jpに別掲（2017Q2–2018Q3）。名寄せテーブルに社名変更履歴を持たせること。

## パイロット2〜3社の推奨（HANDOFF Task 1）

選定基準（prior-art文書§3の提案基準: 機械可読・遡及・追随度対比）に照らして:

- **第1候補: 三菱UFJ信託**（2017Q2から全期間xlsx——PDF抽出なしで最長時系列。パーサ1本で9年分）
- **第2候補: アモーヴァAM**（robotsが該当パスを明示許可・列構成検証済み・14k行/四半期の規模感確認済み。2017–2022はPDF）
- **第3候補: ニッセイAM または 三井住友トラストAM**（ニッセイ=全議案理由テキストで将来拡張に強い / SMTAM=CSVでパース最軽量、ただしURL連番が非規則でリンク一覧のスクレイプが必要）
- 大和は月次粒度が魅力だが遡及が2019年1月までで、四半期社との期間整合に変換が要る。りそなは取得障害があるためパイロットから除外（スケール段階で手動取得）。

**パイロットの最小構成案**: 三菱UFJ信託×アモーヴァ×ニッセイの3社 × 直近2総会シーズン（2024・2025年6月総会を含む四半期）。3社ともExcelがあり、パーサ3本・実ファイルフィクスチャでHANDOFF Task 1の受入基準（行列がサイドカー付きで組めること）を検証できる。

## 会社別詳細

### アセットマネジメントOne
- URL: https://www.am-one.co.jp/company/voting/ （「5. 議決権行使指図結果 個社別開示」）
- ファイルパターン: `/img/company/16/voting-eq-YYYYMM.pdf`（四半期末月。例外: 2017年4-6月期のみ `2017.pdf`）、年間集計 `year-YYYY.pdf`、議案分類別集計は2016.pdf（2016年10月〜2017年6月）から
- 遡及: 個社別2017Q2〜2026Q1欠落なし。全期間PDFのみ（1ファイル数百KB〜1.7MB）
- 行使理由: 利益相反上重要な会社・方針と異なる判断・重要議案は理由公表とページに記載（PDF内実査は未実施）
- robots: 404（不存在）。規約: 無断転用・複製不可の一般条項

### 野村アセットマネジメント
- URL: https://www.nomura-am.co.jp/special/esg/vote/index.html
- パターン: PDF `/special/esg/pdf/voteYYYY_qN.pdf`（2017–2020年分は `/corporate/service/responsibility_investment/pdf/`）、Excel `/special/esg/excel/voteYYYY_qN.xlsx`（2023Q1〜）。qNは暦四半期。2017Q1のみ `vote2017.pdf`
- 遡及: 2017Q1〜2026Q1。※vote2024_q2のリンク欠落（理由未確認）
- 行使理由: 2019Q2から一部、2019Q4から全議案
- robots: 404。規約: 「電子的方法または機械的方法を問わず…無断で複製、引用、転載または転送等を行うことはできません」（9社中最強の文言）

### 三菱UFJ信託銀行
- URL: https://www.tr.mufg.jp/houjin/jutaku/about_stewardship.html
- パターン: 旧 `/houjin/jutaku/docs_download/unyou_kabu/kobetsu_YYYYMM.xlsx`（2017年6月分〜2024年6月分）、新（2024Q3〜）`/new_assets/houjin/jutaku/docs_download/unyou_kabu/YYMM-YYMM_kobetsu_gianbetsu_koushikekka.xlsx`。年度集計PDF `koushikekka_YYYYMMnendo.pdf`（2016年度〜）、行使事例PDFあり
- 遡及: **2017Q2〜2026Q1全期間xlsx・欠落なし**
- 注意: サイトはShift_JIS。信託銀行本体の受託財産分
- robots: 404。規約: 無断使用・複製・改変禁止の一般条項

### 三菱UFJアセットマネジメント
- URL: https://www.am.mufg.jp/investment_policy/responsible_stewardshipcode.html
- パターン: `/assets/pdf/investment_policy/giketsu_YYYYMM-YYYYMM.xlsx`（2023Q1〜、同名.pdfが概況）。2018Q3–2022Q4は四半期PDF、2016年7月〜2018年6月は年度PDF（旧PDFの粒度は未確認）
- 遡及: 2016年度〜2026Q1（※2023Q3リンク欠落未確認）
- 注意: **WebFetchで403（WAF）。robots未確認**。旧三菱UFJ国際投信（2023年商号変更）、MUI投資顧問の活動報告を統合掲載
- 規約: 全内容の無断使用・複製・改変禁止

### 三井住友トラスト・アセットマネジメント
- URL: https://www.smtam.jp/company/policy/voting/result/ （外国株式は別ページ）
- パターン: `/file/{連番ID}/voting_YYYYQn.pdf|.csv`（**IDが非規則のためURL機械構成不可→一覧ページのスクレイプが必要**）。Qnは同社FY基準（2025Q4=2026年1-3月総会）。CSVは2023Q1（2023年4-6月総会）〜
- 遡及: 個別2017Q2〜、年次集計は2013年5-6月総会分から。三井住友信託銀行分（2017Q2–2018Q3）はsmtb.jpに別掲
- robots: 404。規約: 私的使用超の複製等禁止・無断リンク許諾制

### 三井住友DSアセットマネジメント
- URL: https://www.smd-am.co.jp/corporate/responsible_investment/voting/report/
- パターン: PDF `.../pdf/YYYYMM-MM_report_of_voting_rights_jp.pdf`、Excel `.../files/smdam_votingresults_{Mon}-{Mon}-YYYY_jp.xlsx`（2023Q1〜）、四半期解説PDFあり（2023Q2〜）
- 遡及: 現体制2019Q2〜2026Q1。旧三井住友AM分は別ページ（2017年6月総会〜2019Q1、全件個別は2018年6月総会以降、PDFのみ）。旧大和住銀分も別掲（内容未確認）
- robots: 存在（`Disallow: /smdam/` のみ、該当パス対象外）。規約: 一般条項

### 大和アセットマネジメント
- URL: https://www.daiwa-am.co.jp/company/stewardship/voting-results.html
- パターン: PDF `/company/stewardship/files/giketsuYYYYMM.pdf`（**月次**、2019年1月〜2026年5月、89ファイル）、Excel `同/YYYYMM.xlsx`（2023年1月〜2025年12月、36ファイル）。Glass Lewis Viewpoint検索ツール併設（`viewpoint.glasslewis.com/WD/?siteID=DaiwaAM`）
- 列構成: 検証済み（サマリー表の項2）。反対議案に理由記載。「利益相反」「不統一行使」列あり
- robots: 404。規約: 「電子的または機械的方法を問わず」複製等禁止
- 注意: **同社がGlass Lewisのプラットフォームを開示に使用している事実は、助言会社との関係を示すシグナルとしてそれ自体が分析対象**（追随度対比の腕の選定材料）

### アモーヴァ・アセットマネジメント（旧日興AM）
- URL: https://www.amova-am.com/about/vote/results （nikkoam.comから301）
- パターン: Excel `/files/lists/voting/{YY}q{N}_voting_results_jp.xlsx`（23q1〜）、PDF同パス（2017年6月分〜22q4、初期はファイル名不規則）
- 列構成: 検証済み（集計シート＋個別開示シート、親議案/子議案別）
- 遡及: 2017年6月〜25q4（38ファイル）
- robots: 200。**/about/vote/ と /files/lists/voting/ はDisallow対象外**（明示的にクロール可能な状態）
- 規約: 一般条項。注意: ドメイン移行中

### りそなアセットマネジメント
- URL: https://www.resona-am.co.jp/sustainability/voting.html
- パターン: PDF `/sustainability/pdf/giketuken_YYYYMM.pdf`（対象四半期の開始月）、Excel `.xls`（2023Q1〜）、年度集計 `giketukenjoukyo_YYYY.pdf`（外株・REIT別あり）
- 粒度: 集計（賛成/反対/棄権/白紙委任）＋個別（会社提案への反対理由・株主提案への賛成理由付き）の2部構成
- 遡及: 2018Q3〜（Wayback 2025-11-12時点で2025Q2まで確認。以降未確認）
- **取得障害: サイト全体が海外IPにHTTP 403（Akamai）。Wayback経由で実査。日本国内IPからの挙動未確認。xlsはWayback未アーカイブ**
- 規約: 一般条項（Wayback経由確認）

### ニッセイアセットマネジメント
- URL: https://www.nam.co.jp/company/responsibleinvestor/cvr.html
- パターン: PDF `/company/responsibleinvestor/pdf/reportYYMM.pdf`（YYMM=公表年月、36ファイル）、Excel `/excel/report_exYYMM.xlsx`（2023Q2〜、12ファイル）
- 列構成: 検証済み。**全議案に「主な判断理由」を記載**（9社中最も理由テキストが豊富）。REIT別シートあり。月別シート分割に注意
- 遡及: 2017年6月総会分〜2026Q1
- robots: 404。規約: 無断複製・改変・**解析**・アップロード等禁止の文言（「解析」の語が入る点は留意）
