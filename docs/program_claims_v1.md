# Program Claims v1 — claim-first ループと P1/P2/P3 の目標文

**Status**: draft v1.1（2026-06-11）。本書がプログラム全体（本 repo = P1、ABM-Microstructure = P2、将来の監査 repo = P3）の主張構造の一次ソース。

**改訂履歴**
- v1.1（2026-06-11）: Yuito レビュー反映——P1 トリオ確定 = **CB/LM/ALW（古典踏襲、「世界標準たるために古典を踏襲するのが筋」）**。ZI の正準定義 = Farmer 原典準拠。CB の観測チャネル欠如は主張から逃がさず **{CB, ZI} 応答等価類の事前予測**として目標文に組み込んだ（§2.2）。
- v1（2026-06-11): 初版 draft。

---

## 0. スコープ文（最上位——全実験はここから演繹する）

> **本プログラムが主張するのは、合成データ上で ground truth が構成的に既知のモデル間識別までである。実データからの機構同定（どの機構が現実の市場を生成しているか）は主張しない。**

この一文を一度でも踏み越えた主張（論文・スライド・会話を問わず）は書かない。PRISM 本体の死因（実データ×ABM の category mismatch、`PRISM/docs/CELL_VALIDITY_AUDIT.md`）はこの境界の実証であり、本プログラムの credibility はこの境界を自分から引いたことに立脚する。

## 1. 駆動原理 = claim-first

各イテレーションは次の順で回す。逆順（作れるから作る）は禁止。

1. **どの権威に、どの一文を否定不能にさせたいか**を書く（権威=学会/機関を名指し、一文=目標文）。
2. その一文の**必要十分**な実験を導出する（必要でない実験は予算ごと削る。十分でない実験は主張を縮める）。
3. 判定基準・解釈規則を**結果を見る前に** spec に落とし、OSF に公開タイムスタンプ付きで登録する（§3）。
4. 実装・実行・判定。基準は動かさない（criterion-shopping 禁止）。縮退規則（結果が negative のときに主張がどう縮むか）も事前に書く。

実装が安いことの罠：安いと「実験の量」が増えて「主張の鋭さ」が増えない。spec 改定の議論は必ず手順 1（目標文）から始める。

## 2. 三論文の目標文と順序

**順序は固定: P1 / P2 → P3。** P3 を先にやると無所属研究者による攻撃と読まれて潰される。P1/P2 は「審判が自分の競技で反則を捕まえられる」ことの実績であり、P3 の監査資格を構成する。

### P1（Atlas コア）

> **古典機構トリオ（Cont-Bouchaud / Lux-Marchesi / Alfarano-Lux-Wagner）とゼロ知能陰性対照（Farmer 原典準拠）が、事前固定された stylized facts battery を統計的等価（TOST）で通過する一方、事前登録された介入応答プロトコルは、観測チャネルを持つ全機構ペアを family-wise α = 0.05・検出力 1−β ≥ 0.9（最小検出効果 = chance + 15pp）で識別し、観測チャネルを欠く {CB, ZI} は事前予測どおり応答等価（TOST）に留まる。**

識別の主張（観測チャネルあり）と等価の予測（チャネル無し）が**同じ理論から両側に**出る構造——介入応答は「分けられるはずのもの」を分け、「分けられないはずのもの」を分けない。後者は falsifiable な理論予測であり、CB が flat でなければ機構理解の方が間違っている。

- 対象権威：計算経済学（JEDC / Computational Economics）＋ ML 側（NeurIPS Datasets & Benchmarks）。
- 中身：真・PRISM toy の成功経路（GO）の論文化。機構トリオ＋ZI 陰性対照＋検出力解析。
- **検出力設計（paper-grade run の事前登録値、§2.1）**——v0.3 toy の pre-registered 判定基準（§2/§14、post-hoc 変更禁止）には触れない。toy が GO を出した後、paper-grade run を**新規の事前登録**として切る二層構造。

#### 2.1 P1 検出力の数値目標（paper-grade run 用、提案値）

| 項目 | 値 | 根拠 |
|---|---|---|
| 識別の検定 | 機構ペア (i,j) × 介入 scheme s ごとに H0: accuracy = 0.5（一側） | ペア単位が主張の単位 |
| 多重比較 | Holm、family = 観測チャネルを持つ全ペア × 全 scheme（{CB,LM,ALW,ZI} → 識別 5 ペア × 4 scheme = 20 検定。(CB,ZI) は識別 family から除外し等価予測側で検定） | family-wise α = 0.05 |
| 最小検出効果（MDE） | accuracy = 0.65（chance + 15pp） | GO 閾値 0.75 より下に置き、閾値ギリギリの効果も検出力内に収める |
| 検出力 | 1−β ≥ 0.9 @ MDE、Holm 最悪 α' ≈ 0.05/24 | 二項検定の正規近似で n ≈ 190/条件 → **CV 依存性の補正（Nadeau–Bengio）で ×2 して n = 400 runs/条件以上**。v0.3 の M=1000 はこれを満たす |
| SF 等価性 | 「識別できない」は TOST で主張：CV accuracy の 90% CI が [0.45, 0.55] に収まること | 棄却失敗 ≠ 等価。v0.3 の pass band 50–55% の形式化 |
| 陰性対照 | ZI の介入応答 flat も TOST（介入有無の判別 accuracy CI が [0.45, 0.55] 内） | 「応答しないこと」も等価性検定で主張する |
| 分散報告 | 全指標 seed 横断 mean ± SE + n、CV は fold 間分散を別記 | プログラム共通様式（§3） |

#### 2.2 トリオ確定（2026-06-11、Yuito 決定）と前提リスク

**トリオ = CB / LM / ALW（古典踏襲）＋ ZI 陰性対照。** 根拠：世界標準を主張するベンチが識別して見せる対象は、分野が 30 年読んできた古典でなければならない（自前モデルでの識別は「自分に都合のいい機構を分けた」と読まれる）。v0.3 toy の T/H はそのまま toy の §14 判定に使い、paper-grade で古典セットに移行する。T/H/SG は補助機構として残す（N≥4 拡張は任意）。

- **CB の観測チャネル欠如は欠陥ではなく主張の一部**：古典形 CB はクラスタ形成が外生確率で、観測情報を使わない → B2 介入面が無い。これを「{CB, ZI} は応答等価」という**事前予測**として目標文に組み込んだ（§2 冒頭）。識別と等価予測が同一理論から出る両側構造になり、主張はむしろ強くなる。
- **ZI の正準定義 = Doyne Farmer の原典準拠**（Farmer, Patelli & Zovko 2005, PNAS——continuous double auction での ZI order flow。起源としては Gode & Sunder 1993 を引く）。他 repo で ZI の解釈ばらつきが既に観測されているため、実装は原典の order-flow 仕様に対して audit する。orphan branch `feat/intervention-sweep`（commit 0ebb6f9）の `toy/models/zi.py` port 草稿は**この audit を通すまで正準と見なさない**。
- **LM の部分観測**は実装リスクとして残る（B2 介入面の切り出しに設計判断が要る）。出発点 = 同 branch の `toy/models/lm.py` port 草稿。
- **ZI（および CB）の SF 通過は経験的に非自明**（vol clustering は両者から自然に出にくい）。縮退規則を事前登録する：通過しない機構があれば、目標文は「SF 等価集合 + SF でも区別される機構」の階層形へ縮む（どの機構がどちらに落ちても主張構造は立つ）。縮退規則の文言確定は paper-grade OSF 登録時。

### P2（共謀 × 市場設計 = ABM-Microstructure）

> **Calvano 型アルゴリズム共謀の成立は、毎期・決定論的報酬という Bertrand 環境の特殊性に依存する。現実的な市場 making の疎・高分散報酬構造に移植すると、(i) Calvano の収束概念は構造的に到達不能になり、(ii) 認定可能な共謀 regime は事象密度 × 学習率空間の特定領域に限られる——あるいは tabular 予算内に存在しない。実在 venue（BCS ES–SPY 較正点）はこの空間の疎側に位置する。**

- 対象権威：EC / Management Science / JEDC、JPX・日銀。
- 主従：**主 = 移植可能性監査**（Calvano AER の現実的 microstructure への移植審査）、従 = latency-fairness × collusion-resistance 設計マップ。詳細は `ABM-Microstructure/docs/research-design.md` §9。
- density spoke の帰結がどちら（regime 有/無）でも主張が立つ縮退構造は事前登録済み。

### P3（有名 LLM-ABM の監査）

> **NeurIPS 採択水準の LLM-ABM の主要主張のうち、X 割が認定プロトコル（再現 → 分散測定 → 介入統制）の下で支持されない。**

- 対象権威：ML コミュニティ（NeurIPS/ICLR）と Sakana 圏。対象候補：TwinMarket 級。
- 監査順序：再現（seed 規律で run が立つか）→ 分散測定（主張効果が seed 分散を超えるか）→ 介入統制（効果が主張機構由来か、Model Contract の intervene 面で統制）。
- **着手条件：P1 GO ＋ P2 の監査結果公表後。**それまでは設計のみ（対象選定・主張の抽出・効果量の事前見積り）。

## 3. プログラム共通要件

1. **検出力設計**：「識別できた/できない」は必ず効果量と β で語る。検出力未設計の null は報告しない。
2. **多重比較の統制**：family を spec に明記（何の集合の中で何回検定するか）。既定は Holm。
3. **OSF 公開タイムスタンプ付き事前登録**：判定基準・解釈規則・縮退規則を、結果生成**前**に OSF へ登録する。git 履歴は内部 timestamp として併用（public repo push も改竄耐性はあるが、第三者向けの標準は OSF）。**P3 で他者を監査する資格の前提なので、P1 paper-grade run と P2 density spoke 解釈規則から運用を開始する。**手順：(i) spec の該当節を frozen PDF 化 → (ii) OSF プロジェクトに registration として登録 → (iii) registration URL を spec に逆記入。
4. **分散の報告様式**：seed 横断 mean ± SE + n を最低単位とし、CI を出すときは方法（正規近似/bootstrap）を明記。単一 run の数値は本文に出さない。
5. **シード規律**：master seed → spawn 子ストリーム、同一 config+seed → bit 同一（両 repo で実装・検証済み）。

## 4. Model Contract との関係

採用（最終目標）はプロトコルの中身と同じくらい**契約の切り方**で決まる（Gym の `env.step()` の前例）。シミュレータ側の最小契約は `docs/model_contract_v0.md`。P1 の参照アダプタ群が契約の最初の実例、P2 harness が最初の外部アダプタ、P3 の被監査モデルが最初の「他者実装」になる——三論文は契約の adoption 経路としても一本につながる。

## 5. 改訂規則

本書の目標文・検出力数値・縮退規則の変更は versioned に切り直す（v1 → v2、サイレント編集禁止）。OSF 登録後の変更は amendment として OSF 側にも記録する。
