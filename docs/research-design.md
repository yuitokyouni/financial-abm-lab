# 市場微細構造実験 A / B 設計計画書
### 能力非対称下の「抽出」と「協調」、およびその設計トレードオフ

<!-- 著者: Yuito。本書は人間が著した設計の一次ソース。査読メモは research-design-review.md（分離）。 -->

---

## 0. 概要

エージェントの**能力非対称**（速さ・賢さの差）が存在する市場では、能力の高い参加者が低い参加者から価値を抽出する。**どれだけ・誰から抽出されるかを決めるのは市場の微細構造（マッチング規則）である**、というのが本研究の出発点。

この単一の摩擦には、洗練度の異なる二つの実例がある。

- **速度ベースの抽出**（反応的アービトラージ）— stale quote の picking off。
- **学習ベースの抽出**（戦略的協調）— アルゴ同士が暗黙に学習する collusion。

本研究が検証する中心問題は次の一点に尽きる：

> 連続マッチングを **batch / auction** に置き換えるという単一の介入は、速度ベースの摩擦に対する教科書的な処方である。ではこの同じ介入は、学習ベースの摩擦（collusion）を **抑えるのか、無影響なのか、むしろ悪化させるのか**。

collusion は古典的に「透明・離散・反復的な相互作用」によって *促進* される（逸脱の検知と懲罰が容易になるため）。batch auction はまさに離散・透明な反復ゲームである。したがって **latency-fairness と collusion-resistance の間にトレードオフが存在しうる**。

本研究の目的は trade-off を *見つける* ことではなく、**設計 → (抽出, collusion) の地図を作る**ことである。結果が trade-off（batch が A を直し B を悪化）でも、整合（両改善）でも、対立（両悪化）でも、いずれも情報になる。trade-off の存在に研究を依存させない framing にすることで「綺麗な仮説への確証」を避ける（→ §3.2 の prior 傾き、§6 の null 取り扱い）。

成果物は二つ。(1) 既知の理論値で検証済みの市場 simulator（実験 A）、(2) 学習エージェント下で「速度対策が協調耐性とトレードオフするか」を測った結果と、それを踏まえた deployable な市場設計上の含意（実験 B）。

**なぜ重要か。** batch auction（FBA）や、AMM における LVR / MEV 対策の auction 設計は、現実に提案・部分採用が進んでいる venue 単位の規則である（ある venue が単独で採用でき、採用 venue が増えるほど cross-venue の latency arbitrage が減るという network 効果も持つ）。一方アルゴ make が市場の主流となった今、アルゴが暗黙に collude するかは設計・規制双方の現実的関心事である。そして「片方の失敗モードへの主要な対策が、もう片方の失敗モードを悪化させるか」という *相互作用* は、各問題を個別に研究すると見落とされる。本研究はそこを正面から狙う。

**なぜ simulation が必須か。** 速度ベースの抽出（実験 A）は解析的に特徴づけられている（後述）。だが学習された collusion の創発条件と、それに対する微細構造の効果（実験 B）は、解析でも実市場データでも解けない（だからこそ Calvano et al. 2020 も simulation を走らせた）。本研究では simulation を *結果を出す唯一の方法* として使う。

---

## 1. 共通の枠組み

両実験は **同一の設計レバー**（連続マッチング vs batch auction）を、**二つの異なる失敗モード**に対して振る。

| | 実験 A | 実験 B |
|---|---|---|
| 失敗モード | 速度ベースの抽出（sniping / LVR） | 学習ベースの抽出（tacit collusion） |
| エージェント | 非学習（反応的） | 学習（RL / Q-learning） |
| 解析的真値 | 存在する | 存在しない |
| 本研究での役割 | simulator の検証ベンチマーク | 未解決問題のフロンティア |

**注意**：A と B は「同じ現象を賢さで連続的につないだもの」では *ない*。A は情報・速度の非対称（victim は受動的、対策は速度優位の除去）、B は戦略的協調（victim は taker、駆動は反復ゲーム学習）であり、**同じ設計が逆方向に効きうる**。両者をつなぐのは「同じ設計レバーへの応答が両失敗モードでどうなるか」という *相互作用* であって、連続的な一現象ではない。この点が研究全体の知的中心である。

---

## 2. 実験 A：抽出のベンチマークと simulator 検証

### 2.1 目的（発見ではなく検証）

実験 A は新規の発見を目的としない。「batch / auction は速度ベースの抽出を減らす」という *定性的* 結論は既に解析的に分かっている：

- CLOB における stale quote sniping のレント構造と、batch interval によるその縮小は **Budish, Cramton & Shim (2015)** が特徴づけている。
- AMM における同一現象は **LVR（loss-versus-rebalancing; Milionis, Moallemi, Roughgarden & Zhang 2022）** として閉形式で与えられる。外生価格が GBM に従うとき、受動的 LP の instantaneous LVR は volatility（σ²）と pool の曲率で書ける簡潔な形を持つ（厳密式は同論文参照）。

したがって実験 A の正当な役割は、**simulator を既知の閉形式に対して検証すること**である。simulator が Milionis の LVR 値・Budish の sniping レントを許容誤差内で再現すれば、それは「解析的真値の無い実験 B を信じてよい」という license になる。**A は世界についての finding ではなく、simulator のユニットテストである。** 本研究が auditability / reproducibility を重視する以上、解析的真値に対して検証された simulator が、真値の無い B の信用の土台となる。

### 2.2 エージェント

- **流動性供給者（passive LP もしくは quoting MM）**：戦略を持たず、規則に従って気配を出す／pool に資金を置く。
- **アービトラージャー（反応的、≥1体）**：外生 true price と市場価格の乖離を、規則の許す限りで突く。学習はしない。
- **ノイズ／流動性トレーダー**：外生に到着し、方向を持たない（または弱い需要）注文を出す。実効スプレッドの測定対象。

### 2.3 環境

- 外生の **true / fair price** を GBM で生成（必要なら jump を付加）。価格はエージェントの取引に影響されない（重要な単純化、2.6 参照）。

### 2.4 条件（A/B、必要なら C）

1. **連続マッチング**（continuous LOB matching または continuous CFMM）。
2. **N 期 batch auction**（uniform-price、batch interval N をパラメータ化）。
3.（任意）**arbitrage-right auction**：各 batch のアービトラージ権を auction で売り、収益を LP に rebate する（AMM/MEV redistribution 系の設計）。

### 2.5 指標と検証

- **抽出量**：LP/MM → アービトラージャーへの富の移転（= LVR / sniping loss）。アービトラージャーの LP 犠牲 PnL の累積として直接測定。
- **ノイズトレーダーの実効スプレッド**：(約定価格 − mid) の符号付き、標準の取引コスト測度。LP/MM が依然タイトな気配を出す意欲を保つかを捉える。
- **LP/MM 純 PnL**（手数料込み）：fees − LVR が正に保たれ、流動性供給が成立し続けるか（＝「インセンティブを殺さない」検査）。
- **検証**：上記 LVR を、パラメータを揃えた Milionis 閉形式と照合。一致が成果物。

### 2.6 スコープの限界（明示）

外生価格を前提とするため、A が答えるのは**「誰が金を取るか」であって「価格は正しいか」ではない**。mid を外生 GBM に固定した時点で、collusion の最も深い害である *価格発見の歪み* は harness の外にある。抽出量・スプレッドの問いには使えるが、価格発見の問いには使えない。

---

## 3. 実験 B：学習された協調と設計トレードオフ（本研究の核）

### 3.1 目的（未解決のフロンティア）

反応的アービトラージャー／MM を **学習エージェント** に差し替え、次を問う：

> 学習する MM 同士の間に tacit collusion（supra-competitive な spread、協調的な気配拡大）は **創発するか**。そして決定的に、**市場設計はそれをどう変調するか** — batch は連続マッチングに比して collusion を抑えるのか、無影響か、*促進* するのか。

**Calvano et al. (2020)** は Q-learning エージェントが明示的合意なしに supra-competitive 価格を学習し維持することを示したが、それは **Bertrand 価格設定** の文脈である。**orderbook / market-making 版**（queue priority、partial fill、在庫リスク、informed flow からの adverse selection を伴う構造）は Bertrand とは構造的に異なり、相対的に未開拓である。したがって B は Calvano の再演ではない。

### 3.2 両方向の仮説（結論を先取りしない）

batch が collusion に与える効果は *先験的に曖昧* であり、これが simulation を必須にする理由そのものである。

B の中心問題は、名前のついた**二力の対決**である（M1 finding 0001 から創発、`docs/findings/0001-batch-collusion-crossover.md`）。collusion ＝ MM が spread を広げる ＝ **高 h**、を起点に辿る：

- **Green-Porter チャネル（促進）**：tacit collusion は監視の良さ（行動の可観測性）と反復性によって維持される（**Green & Porter 1984** 系）。batch auction は離散・透明な clearing であり、逸脱の検知と懲罰を容易にし collusion を**支える**。
- **arbitrageur-predation チャネル（破壊, ← finding 0001・検証済）**：高 h では batch が抽出を**増やす**（net 変位の凸性）。よって batch は広い collusive spread を arbitrageur の accumulated-displacement sniping に**晒す**。連続は広い spread を守る（個別ジャンプが spread を超えない）。batch は collusion を**掘り崩す**。
- （補足・訂正済）当初の「破壊方向＝uniform-price で undercut 全取り」は Bertrand 直観の誤った密輸（demand-reduction で脚が弱い）。破壊方向の本体はこの Bertrand 論ではなく predation チャネルである。

**B の問い**：Green-Porter 促進 vs arbitrageur 捕食――どちらが、どのレジーム（h, N, σ, memory）で勝つか。predation チャネルの発見により、以前の「prior は促進に一方的に傾く」懸念（③）は**再均衡**した（本物の対抗力が立った）。それでも null（§6）と妥当性検査（A3／§3.4 gate）は固く回す。どちらが勝つかは解析では出ず、**地図上のどこで何が起きるかが結果である。**

> 前提: predation チャネルは **committed-quote モデル**（MM がバッチ内で気配更新しない＝遅い MM）で生きる。この機構選択は design lever の定義そのもの（finding 0001 参照）。B spec で明示する。

### 3.3 条件

実験 A と同一の市場設計条件（連続 / batch /〔arb-auction〕）を、学習 MM 集団の下で走らせる。

### 3.4 指標

- **supra-competitive markup**：実現 spread の競争ベンチマークに対する超過。markup = (実現 spread − 競争 spread) / 競争 spread。**競争ベンチマークは独占（単体 MM）spread ではなく、同一 n 体の myopic / one-shot stage-game Nash**（履歴に条件づけない best-response の不動点）。これは「arbitrageur からの逆選択への Glosten-Milgrom break-even」で決まる（§4.1 C4 と同一の結び目＝A1+A2+C4）。さらにその下に **zero-intelligence floor**（メカニズム＋order-flow 制約だけで出る spread、知能ゼロのベースライン）を置き、「どこからが戦略/知能の寄与か」を分離する。floor 体系：ZI floor ≤ myopic-Nash floor ≤ 実現 spread。
- **collusion の安定性／頑健性**：supra-competitive 状態が (i) 新規 MM の参入、(ii) 需要／volatility ショック、(iii) 強制的な 1 期逸脱（reward-punishment が再確立するか）に対して持続するか。Calvano 流の deviation + punishment 分析。**この impulse-response 検査を通過した点のみ collusion と認め、その後でのみ §3.5 の memory 閾値を測る（artifact の閾値を測らないための gate＝追加点①）。**
- **設計マップ（本研究の中心測度）**：各市場設計について **両軸とも学習(B)世界で測った** (抽出量, collusion markup) を平面にプロットする（学習 MM も sniped される＝同一世界で coherent）。実験 A は frontier のデータ源ではなく**検証アンカー**に徹する（A=unit test, B=findings を漏らさない）。比較は単一勝者でなく地図であり、trade-off / 整合 / 対立 のどれも読み取れる。

### 3.5 決定的な設計選択（正直に）

collusion の創発は **エージェントが懲罰のために履歴を条件づけられるか** に依存する。state に競争相手の直近行動が含まれなければ、懲罰が組めず tacit collusion は生じない。したがって B の結果は「エージェントに十分な memory を与えたとき」という条件付きであり、**memory の量自体が sweep すべきパラメータ**である。この依存性を隠さないことが結果の信頼性を支える。

### 3.6 頑健性要件

結果は学習アルゴリズム・ハイパーパラメータに依存する。**単一の run は何も証明しない。** 複数アルゴリズム・複数 seed・主要パラメータ grid にわたる頑健性が必須である。検証済み harness（実験 A）が、この信頼性の土台となる。

---

## 4. 詳細設計仕様

### 4.1 エージェント仕様

| 種別 | state | action | objective(reward) |
|---|---|---|---|
| passive LP / quoting MM（A） | なし（規則ベース） | 規則に従う気配 / pool 残高 | — |
| 反応的アービトラージャー（A） | 市場価格 − true price の乖離 | 規則の許す範囲で抽出取引 | 即時アービトラージ利益 |
| ノイズ／流動性トレーダー（A,B） | 外生到着 | 方向ランダム（または弱需要）の注文 | — |
| 学習 MM（B、≥2体） | 自他の直近 spread/quote（在庫は初期除外→robustness で導入: C3） | 離散 grid からの spread / quote 選択 | 期 PnL = spread 捕捉 − adverse selection − 在庫コスト |

**逆選択源の明示（C4 訂正）**：noise trader は無方向なので逆選択源ではない。**逆選択源は arbitrageur**＝true price がジャンプした時に MM の stale quote を抜く速い主体。したがって学習 MM の competitive spread は「この arbitrageur 逆選択への break-even」（Glosten-Milgrom 論理）で決まり、§3.4 の markup 分母・§2.5 の検証アンカーと同一の結び目になる（**A1+A2+C4 を一度に固定する**）。

### 4.2 価格プロセス

GBM：drift μ、volatility σ。任意で jump（強度 λ、jump size 分布）。σ は抽出量を直接駆動するため主要 sweep 対象。

### 4.3 マーケット機構（厳密な clearing 規則）

- **連続**：価格優先・時間優先の continuous LOB matching（または continuous CFMM の swap）。
- **batch auction**：interval N 期ごとに注文を集約し、uniform price で一括 clearing。N をパラメータ化。
- **arb-auction（任意）**：各 batch のアービトラージ権（pool に対する先頭/独占アービトラージ）を auction し、落札額を LP に rebate。

### 4.4 手数料・インセンティブ構造

LP fee（CFMM なら swap fee、CLOB なら maker rebate / taker fee）。「batch が LP インセンティブを殺さないか」の問いは fee に依存するため、fee 水準は明示パラメータとして固定・sweep する。

### 4.5 指標の定義

- **LVR**：LP 保有価値と、true price で連続 rebalance する複製ポートフォリオ価値の差（Milionis 定義）。
- **実効スプレッド**：(約定価格 − mid) 符号付き、ノイズトレーダーについて集計。
- **markup**：3.4 の定義。
- **collusion index**：markup と、逸脱に対する懲罰の有無（reward-punishment 構造の検出）。

### 4.6 学習設定（実験 B）

- **アルゴリズム**：まず tabular Q-learning（Calvano に整合・可解釈・debug 容易）。頑健性のため関数近似／deep-RL 変種に拡張可能。
- **state 離散化**：自他の直近行動を含む（懲罰の条件づけに必要）。memory 長は sweep。
- **action**：spread / quote の離散 grid（任意で在庫考慮）。
- **exploration**：ε-greedy、ε は減衰。
- **エージェント数 n**：≥2、sweep（一般に n が大きいほど collusion は困難）。
- **収束**：policy が安定するまで run、収束 policy 上で測定、複数 seed。

### 4.7 検証・頑健性プロトコル

- **A の検証**：sim LVR vs Milionis 閉形式（パラメータ整合）、許容誤差を事前設定。
- **B の頑健性**：(アルゴリズム × memory 長 × n × σ × N × fee) の grid、各セル複数 seed。設計マップはこの grid 上で評価。
- **grid は tiered（B1）**：粗 grid で trade-off の在処を当てる → 局所を密に。compute 予算を事前に数値で固定（grid 全張りは run 数が爆発する）。
- **外部妥当性アンカー（追加点④）**：内部整合（benchmark/検証は解析モデル相手）だけでは結果の意味が定まらない。σ・fee・N・flow の少なくとも一点を **実在 venue/銘柄のパラメータにアンカー**した検証ケースを必ず含める。任意の合成パラメータで綺麗な内部結果を出しても外部的な含意が不明になる。

---

## 5. 主張できること / できないこと

| | 主張できる | 主張できない |
|---|---|---|
| 実験 A | (i) simulator が既知の閉形式抽出を再現する（検証）。(ii) 非学習エージェント下で、batch/auction が連続マッチングに比べ速度ベース抽出を、与えられた fee の下でどれだけ減らすか（定量化）。 | 価格発見の質（外生価格を仮定）。戦略的・学習的挙動。**新規性**（定性的結論は既知 — A の価値は検証と定量化であって発見ではない）。 |
| 実験 B | (i) orderbook/MM 設定で tacit collusion が創発するか（Calvano の Bertrand 結果を超える）。(ii) 市場設計が collusion に与える方向（抑制／無影響／促進）。(iii) 抽出削減と collusion 耐性のトレードオフ・フロンティア。 | 閉形式の結果。実市場への直接の主張（sim のみ、アルゴ・パラメータ横断の頑健性が前提）。collusion の不可避性（エージェントの memory／学習設定に条件付き）。 |

---

## 6. 実装順序とマイルストーン

1. **harness 構築 + 検証**（実験 A）：passive LP / 反応的アービトラージャー / ノイズトレーダー、GBM 価格、連続マッチング。LVR を Milionis 閉形式と照合。RL 不要、数百行規模。← *これが完了するまで B に進まない。*
2. **抽出の A/B 比較**：連続 vs batch（vs arb-auction）で抽出量・実効スプレッド・LP PnL を測り、理論の定性予測を再現することを確認。
3. **学習エージェント差し替え**（実験 B）：反応的アービトラージャー／MM を Q-learning MM 集団に置換。
4. **設計 × 学習 grid**：同一の市場設計条件で collusion の創発と、設計による変調を測定。
5. **頑健性 sweep**：アルゴリズム・memory・n・σ・N・fee・seed。
6. **設計マップ分析**：各設計を (抽出量, collusion markup)（両軸とも B 世界・C5）平面に置く。**結論は trade-off / 整合(両改善) / 対立(両悪化) のいずれでも可**で、どれも publishable な情報（null を outcome space に最初から含める＝追加点②）。← *本研究の主結果。*

なお同じ「小さな sim で頑健な mechanism を探す」型は、無担保レンディングの screening 設計や MEV の再分配規則など他ドメインにもそのまま適用できる。市場微細構造を選んだのは、最も簡易に検証可能で設計余地が開いているためであり、ドメインは関心に応じて差し替え可能である。

---

## 7. 関連研究（位置づけ）

- **Budish, Cramton & Shim (2015)**, *QJE* — 連続時間 LOB が生む機械的アービトラージ（sniping）と、frequent batch auction による速度競争の除去。
- **Milionis, Moallemi, Roughgarden & Zhang (2022)** — AMM の LVR。受動的 LP の抽出損を閉形式で特徴づけ。sniping と同型。
- **Calvano, Calzolari, Denicolò & Pastorello (2020)**, *AER* — Q-learning が Bertrand 文脈で明示的合意なく collusion を学習。本研究はその orderbook/MM 版（未開拓）を扱う。
- **Green & Porter (1984)** — 不完全監視下の collusion。監視の良さ・反復性が collusion を支えるという、batch が collusion を促進しうるという仮説の理論的根拠。

---

*本書は二実験の設計仕様である。実験 A の目的が simulator 検証であること、および実験 B の主結果が「速度対策（batch）が設計 →(抽出, collusion) 地図上でどう効くか（trade-off/整合/対立いずれも情報）」であることを、実装上の指針として保持されたい。*

---

## 8. 改訂メモ（v0.2, 2026-06-02）

Yuito の査読評価を受けて訂正・追加。詳細根拠と provenance は `docs/research-design-review.md`。

- **訂正（doc の誤りを確定）**：C1（§3.2 破壊方向の Bertrand 借用 → demand-reduction で脚が弱い）／C4（§4.1 逆選択源＝arbitrageur を明示）／C5（§3.4 設計マップを B 世界に統一、A は検証アンカー）。
- **追加（critique の上に・置換ではない）**：① A3×C2 の gate（妥当性検査を通った点でのみ memory 閾値を測る）／② null を outcome space に（地図 framing、§0・§6）／③ C1 帰結＝prior が collusion 促進に傾く→confirmation risk→null と検査を固く（§3.2）／④ 外部妥当性アンカー（§4.7）。
- **floor 体系**：ZI floor ≤ myopic-Nash floor ≤ 実現 spread（A1 を一段補強、固有名は出さない）。
- **rhetoric 訂正**：査読の「最もバグの入りにくい層」は言い過ぎ（CFMM 会計＋連続アービ極限を正しく出すのは自明でない）。相対主張（matching engine と学習ループ未検証）は維持。
- **実装前に解く結び目の優先順**：**A1+C4+C5（一度に）→ A3 を①で gate → ② null を最初から outcome space に**。
