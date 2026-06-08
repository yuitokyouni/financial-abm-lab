# 約定アルゴリズム (Execution Algorithms) — study primer

**目的**: 大口注文を LOB 上でどう「捌く」かの理論と実務を、quant microstructure の
語彙で一気通貫に整理する。後半 §9 で本研究 (YH006 系、Speculation Game × LOB) の
凍結機構・軸2 (執行層) アイデアに接続する。textbook 級の established 知識をベースに、
出典は §10 に集約。数式は最小限だが省略しない。

---

## 1. 執行問題の定義 — 何を最適化しているか

執行 (execution) とは、**親注文 (parent order)** を「資産 X を数量 Q、時刻 0→T の間に
売買せよ」という指示として受け取り、それを**子注文 (child orders)** の列に分解して
市場に流し込む問題。alpha (どっちに賭けるか) は所与で、執行は「決めた賭けを**いくらの
コストで**実現するか」だけを扱う。alpha generation とは別レイヤであることが本質。

最適化する目的関数は **implementation shortfall (IS, Perold 1988)**:

```
IS = (実現した平均約定価格 − 意思決定時点の価格 S_0) × Q + 機会損失(未約定分)
```

これを期待値と分散の両面で評価する。コストの分解:

```
E[コスト] = スプレッド支払い + 手数料 + マーケットインパクト + ドリフト
Var[コスト] = タイミングリスク (執行を引き延ばすほど価格変動に晒される)
```

執行アルゴリズムの仕事は本質的に **インパクト (速く出すほど大) と タイミングリスク
(遅く出すほど大) の trade-off** を、リスク選好に応じて解くこと。これが §5 の
Almgren-Chriss 効率的フロンティアに直結する。

---

## 2. コスト構造の解剖

### 2.1 スプレッド・手数料 (確定的コスト)
- **bid-ask spread**: 成行で板を渡る (cross the spread) と半スプレッド分を即失う。
- **手数料 / maker-taker**: 多くの venue は流動性を**取る**側 (taker) に手数料、
  **置く**側 (maker, 指値で板に乗せて約定された) に rebate を払う。これが指値 vs
  成行の経済性を歪め、§7 の order placement tactics の駆動力になる。

### 2.2 マーケットインパクト (内生的コスト) — 最重要
自分の注文が価格を動かす。2 成分に分ける:

- **一時的インパクト (temporary)**: その瞬間の流動性を消費して価格を押す。注文を
  止めれば回復する。執行速度 v (= dQ/dt) の関数。線形近似で `h(v) = η·v`。
- **恒久的インパクト (permanent)**: 自分の売買が「情報」と解釈され mid 自体が
  恒久シフトする。累積出来高 x の関数。線形近似で `g(x) = γ·x`。

実証的に最も頑健なのが **square-root law (平方根則)**:

```
インパクト ≈ Y · σ · sqrt(Q / V)
```

σ = ボラティリティ、Q = 注文サイズ、V = その期間の市場出来高、Y = O(1) の定数。
「注文が市場出来高に占める割合の平方根」でインパクトが効くという、資産・市場・年代を
跨いで成り立つ stylized fact。線形モデル (Kyle) より実データに合う。直感: 板の depth が
価格から離れるほど薄くなる凸性 + メタオーダーの自己相関。

**Kyle's λ (1985)**: 情報トレーダーモデルから `ΔP = λ · (order flow)`。λ = 価格弾力性
= 流動性の逆数 (illiquidity)。market impact を 1 パラメタで表す古典。

### 2.3 タイミングリスク / 機会コスト
執行を T に引き延ばすと、その間の価格ドリフト・ボラに晒される。分散は概ね
`σ² · (残ポジション)² · 時間` で積み上がる。**速く執行 = インパクト大・リスク小、
遅く執行 = インパクト小・リスク大**。adverse selection (指値が約定するのは価格が
自分に不利に動いた時ばかり) も実質的なタイミング由来コスト。

---

## 3. ベンチマーク — 何に対して「良い執行」か

アルゴは必ずベンチマーク対比で評価される。ベンチマークの選択がアルゴ設計を決める:

| ベンチマーク | 定義 | 対応アルゴ | 性質 |
|---|---|---|---|
| **Arrival price (IS)** | 意思決定時の mid S_0 | IS / arrival-price algo | front-load 気味、リスク回避を反映 |
| **TWAP** | 期間の時間平均価格 | TWAP | 単純、impact 無視 |
| **VWAP** | 期間の出来高加重平均 | VWAP | 機関投資家の標準ベンチ |
| **Close** | 引け値 | MOC / close-tracking | index リバランス系 |

注意: ベンチマークは**ゲーム可能**。VWAP に連動させると自分が VWAP を動かして
自己成就する (特に大口・薄い銘柄)。だから「VWAP を打ち負かした」は薄商いだと無意味。

---

## 4. スケジューリング系アルゴリズム (when to trade)

親注文を時間軸でどう割り振るか。板の中の置き方 (§7) と直交する上位レイヤ。

### 4.1 TWAP (Time-Weighted Average Price)
Q を T で等分し一定レートで流す。`child = Q/N` を N スライス。最も単純で、出来高
プロファイルを使わない。隠れる効果 (predictability) が弱点 — 規則的だと front-running
される。実務では時間/サイズに乱数 (randomization) を足す。

### 4.2 VWAP (Volume-Weighted Average Price)
**過去の日中出来高プロファイル** (典型的に始値・引け前が厚い U 字) に合わせて子注文を
配分する。market が厚い時に厚く出す = 相対インパクト最小化。`child_t ∝ 予測出来高_t`。
最も普及した機関アルゴ。弱点: プロファイルは予測であり、当日の出来高が外れるとズレる。

### 4.3 POV / Participation Rate (出来高追随)
**リアルタイム出来高の固定割合** (例 10%) を維持。`child_t = ρ · (実出来高_t)`。
VWAP が事前プロファイル依存なのに対し POV は実測追随でロバスト。ただし「市場が動いて
出来高が増えると自分も増やす」= 不利な時に加速しうる。完了時刻が出来高次第で不確定。

### 4.4 Implementation Shortfall (IS) / arrival-price algo
arrival price をベンチに、**front-load** (序盤に多く出す) して未約定ポジションの
タイミングリスクを削る。リスク選好パラメタで「攻め (速い・impact 大) ↔ 守り (遅い・
risk 大)」を連続調整。理論的裏付けが §5 の Almgren-Chriss。実務で最も「考えている」
カテゴリ。

---

## 5. 最適執行の理論 — Almgren-Chriss (2000)

執行の規範モデル。離散時間 N スライス、保有量軌道 `x_0=Q → x_N=0` を選ぶ。
線形インパクト (temp `η`, perm `γ`)、価格は `dS = σ dW` のランダムウォーク。

**目的関数 (mean-variance)**:

```
minimize   E[コスト] + λ · Var[コスト]
```

λ = リスク回避係数。コストは IS。線形インパクト下で閉形式解が出る:

- **λ = 0 (リスク中立)**: コスト期待値だけ最小化 → 解は **TWAP (等速)**。インパクトの
  みなら均等割りが最適。
- **λ > 0 (リスク回避)**: 序盤に多く売る **front-loaded** な指数的減衰軌道:

```
x_k = Q · sinh(κ(T − t_k)) / sinh(κT),   κ ≈ sqrt(λ σ² / η)
```

κ (urgency) が大きい (リスク回避強 or 流動性薄) ほど速く畳む。

**効率的フロンティア**: λ を振ると (E[コスト], Var[コスト]) 平面に凸フロンティアが
描ける。「同じ期待コストでリスク最小」「同じリスクで期待コスト最小」の軌道集合。
ポートフォリオ理論の執行版。**これが「速さ vs リスク」trade-off の正準的定式化**。

拡張: square-root インパクト版 (Almgren 2003)、連続時間 stochastic control での
**HJB 方程式** 定式化 (Cartea-Jaimungal-Penalva 2015)、出来高・ボラの確率性、
複数資産 (ポートフォリオ執行で相関を使う)。

---

## 6. Smart Order Routing (where to trade)

現代市場は**断片化** (fragmented): 同じ銘柄が複数の lit venue + dark pool で取引される。
SOR は子注文を venue 横断で割り振る:

- **lit vs dark**: lit = 板公開 (price discovery, but 露出)。dark pool = 板非公開で
  主に mid 約定 (インパクト隠せるが fill 不確実・adverse selection)。
- **latency / queue**: 速い venue・有利な queue position を狙う。
- **fee/rebate 最適化**: maker rebate を取りに行くか taker fee を払って確実に取るか。
- **best execution 義務** (規制): 顧客に最良条件を提供する受託者責任。SOR はこの
  compliance も担う。

レイテンシ競争・HFT・maker-taker の歪みはこの層で顕在化する。単一市場モデル
(本研究の YH006) では §6 は捨象されるが、一般化 (YH006_2 以降) では effect する。

---

## 7. 板の中のミクロ執行 (how to place each child)

スケジュール (§4) が「いつ・どれだけ」を決めたら、各子注文を板にどう置くか:

### 7.1 成行 vs 指値の基本 trade-off
- **成行 (aggressive, cross spread)**: 即約定 (fill 確実) だが半スプレッド + temporary
  impact を払う。taker fee。
- **指値 (passive, post & queue)**: スプレッドを**稼ぐ** (maker rebate) が、(1) 約定
  不確実、(2) **adverse selection** — 約定するのは価格が自分に不利に動いた時ばかり
  (情報を持つ相手に取られる)。queue 後方だと永遠に約定しない。
- **pegging**: best bid/offer や mid に追従して指値を貼り替える。

### 7.2 queue position と cancel/replace
指値は FIFO 待ち行列。前にどれだけ並んでいるか (queue position) が約定確率を支配する。
価格が動くと貼り替え (cancel→re-post) するが、貼り替えると queue 最後尾に戻る。
**この cancel/re-submit の累積が本研究の design A' で O(N²) 板爆発を起こした経路**
(§9 で再述)。

### 7.3 隠す技術
- **iceberg / hidden**: 表示数量だけ見せ残りを隠す。大口の露出を抑える。
- **midpoint peg**: mid で受動的に待つ (dark 的)。

### 7.4 微視的最適化の制御論的視点
「今この瞬間、指値をどの価格・どの数量で置くか」を **stochastic optimal control** で
解く流派 (Cartea-Jaimungal ら)。状態 = 在庫・スプレッド・queue、制御 = 指値の深さ。
在庫リスク (inventory risk) と adverse selection を HJB でバランス。market making の
最適化 (Avellaneda-Stoikov 2008) と数学的に地続き。近年は **RL for execution**
(状態→子注文を学習) も実務化。

---

## 8. 評価と落とし穴

- **slippage 計測**: arrival price 対比の実現コスト。符号・ベンチを明示しないと無意味。
- **ベンチマークのゲーム性** (§3): VWAP 自己成就、薄商いでの見かけ上の勝ち。
- **インパクトの非定常性**: square-root の係数 Y は regime 依存。較正した環境と
  実行環境がズレると外れる (← 本研究の c_ticks self-consistency 問題と同型、§9)。
- **backtest の生存バイアス・流動性楽観**: 過去板で「自分がいなかった世界」を仮定
  すると自分のインパクトを過小評価する。agent-based sim が効く所以。

---

## 9. 本研究 (YH006 / Speculation Game × LOB) への接続

ここが本 primer の価値。執行理論を君のモデルの語彙に翻訳する。

### 9.1 SG には「執行層が無い」
Katahira-Chen SG の sizing は `q = ⌊w/B⌋`。これは「親注文サイズ q を**一発で MARKET
として出す**」ことに相当し、§4 のスケジューリングも §7 の placement tactics も**存在
しない**。aggregate 版では注文は即時に価格へ集計されるのでインパクトも擬似的。
LOB 移植 (design A') で初めて「q を CDA の板にぶつける」現実が入る。

### 9.2 design A' は「素朴な単発成行執行 + 防御弁」
dossier §2.2: open/close は MARKET_ORDER + 次 step self-cancel + **opposing-liquidity
guard**。これは執行理論的には:
- 「親 = 子 = 1」の最も素朴な aggressive 執行 (TWAP の N=1 極限、§4.1 の退化形)。
- opposing-liquidity guard = 反対板が薄い時に注文を抑制する弁。**これが §7.2 の
  cancel/re-submit 板爆発を防ぐために必要だった**が、同時に「大口 q が反対板を
  食い尽くす状況で約定を弾く」装置でもある。

### 9.3 凍結機構と「執行不在」仮説の射程
dossier §5.3 の凍結経路: **約定が rare → sg_wealth が動かない → bankruptcy (w<B) に
到達しない → hazard→0**。執行理論から見た「約定が rare」の候補因:
1. **大口 q の単発成行が薄い反対板で歪む / guard に弾かれる** (§9.2)。→ ここを
   **分割執行 (TWAP/POV 的 child schedule)** で埋めるのが「軸2 (執行層導入)」の発想。
   slicing すれば各 child が約定 → sg_wealth が動く → bankruptcy 判定が生き返る →
   turnover 機構的回復、という因果仮説。
2. **trigger 率そのものが低い** — そもそも RT (round-trip) が rare。これは執行の
   placement ではなく SG の**認知閾値 c_ticks** が SG 投入後 regime に対し
   self-consistent でない (P2) ことに起因しうる。

**ここが重要な切り分け**: 軸2 (slicing) は (1) の fill 側を埋めるが (2) の trigger 側
には効かない。原因が (1) か (2) か未決着のまま slicing を打つと、効いても効かなくても
解釈が交絡する。→ だから **S5.9 (c_ticks 再較正で trigger 寄与を切り分け) が軸2 より
先**、という設計判断になる。square-root law の係数が環境で外れる §8 の話と、c_ticks を
SG 投入前 regime で較正した P2 は**同型の「較正環境と実行環境のズレ」問題**。

### 9.4 もし執行層を入れるなら (YH006_2 への設計メモ)
- **Almgren-Chriss を SG agent に内蔵するのは過剰**。SG agent は myopic な strategy-table
  で、最適執行の mean-variance 最適化を解く主体ではない。
- 自然な設計は**別レイヤ**: parent order (= SG が決めた q と方向) を受け取り、それを
  child schedule (TWAP/POV/IS のどれか) に分解する **execution layer** を SG と LOB の
  間に挟む。SG の認知ロジックは不変、約定の現実だけ差し替える (design A' の wealth
  2-account 分離思想と同じレイヤリング)。
- LIMIT 注文拡張 (YH006_2) は §7 の passive placement を初めて可能にする = adverse
  selection / queue という新しい摩擦が入る。これは「funnel を浅くする microstructure
  真効果」の機構をさらに分解できる軸。

### 9.5 一行まとめ
本研究の「funnel 減衰 = LOB microstructure 真効果」は、執行理論の語彙では
**「素朴な単発成行執行 + liquidity guard が、SG の資産→注文→約定→淘汰のフィードバック
ループを切断している」**可能性として読める。軸2 はそのループを執行層で再接続する
介入だが、切断点が fill 側 (執行) か trigger 側 (c_ticks) かの同定が前提。

---

## 10. 出典 / さらに読む

- Perold (1988) "The Implementation Shortfall: Paper versus Reality" — IS の原典。
- Kyle (1985) "Continuous Auctions and Insider Trading" — λ、線形インパクト。
- Almgren & Chriss (2000) "Optimal Execution of Portfolio Transactions" — 規範モデル。
- Almgren (2003) — nonlinear (square-root) impact 版。
- Almgren, Thum, Hauptmann, Li (2005) — square-root law の実証較正。
- Bouchaud, Bonart, Donier, Gould "Trades, Quotes and Prices" (2018) — LOB
  microstructure の現代教科書。square-root law / メタオーダーの decisive な整理。
- Cartea, Jaimungal, Penalva "Algorithmic and High-Frequency Trading" (2015) —
  stochastic control / HJB による執行・market making の統一的扱い。
- Avellaneda & Stoikov (2008) — market making の最適 quote (inventory risk)。
- Gatheral (2010) "No-dynamic-arbitrage and market impact" — impact モデルの整合性。
- Guéant "The Financial Mathematics of Market Liquidity" (2016) — 最適執行の数理。

---

## 改訂履歴
| 日付 | 内容 |
|---|---|
| 2026-06-08 | 初版。執行アルゴリズム study primer。§9 で YH006 凍結機構・軸2・S5.9 切り分けに接続。 |
