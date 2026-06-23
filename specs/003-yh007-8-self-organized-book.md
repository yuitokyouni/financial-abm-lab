# 003 — YH007-8: 自己組織化板 (Chiarella-Iori × Kronos) — naïve 設計の artifact を構造的に潰す

**状態: ドラフト (実装前 / レビュー待ち)**。本 spec は `specs/002-yh007-kronos-microstructure.md`
の §5 YH007-8 行 + §10-D を展開した**ルートコーズ修正サブ spec**。002 は ground truth のまま、
本 003 は YH007-8(自己組織化板)の設計を確定するための作業文書。

> 親 spec: 002 §8.x(全機構 ablation の結論撤回)/ §10(新課題 A〜E)。
> 本 spec は 002 の negative result(naïve 設計では SF 測定が成立しない)を受けた次の一手。

---

## 0. 一行サマリ

**全エージェントを LIMIT 注文化し、Chiarella-Iori 型の自己組織化 CDA 板に Kronos 信号を
評価値として埋め込む。外生 MMFCN を廃し、流動性を内生化する。** 目的は SF を「出す」ことでは
なく、**naïve 設計(002 YH007-2〜7)を汚染していた 2 つの測定アーティファクト
(market 価格 = bid-ask bounce、mid = 量子化ジャンプ)を構造的に消去**し、初めて信用できる
価格系列の上で機構を測れる土台を作ること。

---

## 1. 動機 — 002 で何が壊れたか

002 §8.x の確定事項:

- **market 価格メトリクス = Roll (1984) bid-ask bounce**。全 agent が MARKET_ORDER で薄い
  MMFCN 板をクロス → 約定価格が bid/ask を交互に叩く → `ret_acf τ=1 ≈ -0.5`。
- **mid メトリクス = 量子化ジャンプ / best 抜け artifact**。離散・薄い板で mid が
  「best 1 段抜け」のチャンクでジャンプ → 裾を数個のジャンプが支配(baseline で既に
  Hill α≈2、spoof で α=0.13 の発散テール、`|r|_mid` が量子化天井に張り付く)。
- → **両 metric とも naïve 設計下では信用できず、機構 ablation の結論は全て inconclusive(撤回)**。

両 artifact の**共通根**:
1. **MARKET-order taking + 外生 MMFCN** = 受動的な内生流動性が無く、約定が常に spread をクロス → bounce。
2. **離散・スカスカの板** = 価格グリッド上で resting order が疎 → mid が tick チャンクでジャンプ。

YH007-8 はこの 2 根を同時に断つ。

---

## 2. 設計の核

| naïve (002 YH007-2〜7) | 自己組織化板 (003 YH007-8) |
|---|---|
| 全 agent MARKET_ORDER | **全 agent LIMIT_ORDER**(価格 + TTL) |
| 流動性 = 外生 MMFCN | **流動性 = agent 自身の resting 指値(内生)** |
| Kronos = 方向 + サイズ | **Kronos = 評価値(価格水準)→ 指値価格**(価格情報を捨てない) |
| 約定 = 常に spread クロス | **約定 = 指値が反対側 best をクロスした時のみ(marketability 内生)** |
| 価格 = 約定価格バウンス / mid 量子化 | **価格 = 密な板の連続 mid 発展** |

これは事実上 **Chiarella-Iori (2009) 型の CDA を PAMS 上に建て、fund/chart/noise 評価値を
Kronos に差し替えたもの**。

> **実装上の注意**: `packages/abm_models/abm_models/chiarella_iori/` と `.../zero_intelligence/`
> は **reduced-form アダプタ(内部 `simulate()`)で PAMS の LOB agent ではない**。よって
> 「CI を fork」ではなく、**新規の PAMS LIMIT-posting agent を作る**(現 `kronos_lob/agents.py:93`
> の `kind=MARKET_ORDER, price=None, ttl=1` を `kind=LIMIT_ORDER, price=<Kronos 由来>, ttl=<window>`
> に差し替えるのが出発点)。CI/ZI アダプタは**評価値ロジックの参照**に留める。

---

## 3. モデル仕様

### 3.1 注文配置則(Kronos 評価値 → 指値価格)

各 agent i は毎 bar(または毎 step)、評価値 `v_i` を計算して指値を出す:

- **評価値** `v_i`:
  - **順張り (trend)**: `v_i = p_hat`(Kronos 予測の次バー中心 = ドリフト先)。
  - **逆張り (fade)**: `v_i = anchor`(Kronos 中心を fair value とし、現 mid がそこから乖離していれば
    乖離を縮める向きに置く)。
- **方向**: `v_i > mid` なら buy、`< mid` なら sell。
- **指値価格** `price_i = v_i × (1 ∓ margin_i)`(buy は下、sell は上に margin 引く。CI の orderMargin 流儀)。
- **marketability(内生)**: `price_i` が反対側 best をクロスすれば**即約定(aggressive)**、
  しなければ**板に resting(passive)**。MARKET/LIMIT の二分でなく、置いた価格と反対板の関係で
  aggressive/passive が決まる。← bounce が消える本質。
- **TTL/cancel 必須**: resting 指値は `time_window` で expire / 各 step 自己キャンセル。
  さもないと YH006 で踏んだ cancel/resubmit 累積による **O(N²) 板爆発**
  (`imported/.../docs/refs_sg_lob_code_semantics.md §3.1`)。

### 3.2 【Guard 2】分散注入 — 配置層の「全員同じ」縮退を防ぐ

計算量のため Kronos 信号は共有 hub 1 本(`kronos_lob/signal_hub.py`)。**全員の `v_i` が同一だと
同一価格帯に積む → 板分散ゼロ → 薄板に逆戻り**(= 002 で潰したはずの「Kronos だけだと全員同じ」
問題の**配置層版**。最も再発しやすい)。分散は**意図的に注入**する:

1. **① 2 読み**(trend/fade で上下に置き分け)— 002 §4.2 を継承。
2. **per-agent ランダム offset**(CI の noise weight 相当)— `price_i` に i ごとの摂動。
3. **確信度依存 margin**(Kronos 分布の広さ → margin_i / 参加閾値)— 002 §4.3 を継承。

→ 共有信号でも **resting 指値が多数の価格レベルに散る**こと(= 密な板)を配置則で保証する。

### 3.3 【Guard 1】tick_size 較正 — mid 連続性の本体

mid が連続になるのは「密な板」だが、密さを決めるのは **tick_size 対 placement 分散**。
tick が分散に対し粗いと板はグリッド上で疎 → mid は tick チャンクでジャンプ。

- **設計条件**: §3.2 の placement 分散が**数十 tick に跨る**よう tick_size を取る。
- **較正手順**: ZI control(§4)で mid 増分の tick 単位分布を見て、0/±1 tick への張り付きが
  消えるまで tick_size を細かくする(or 分散を広げる)。

### 3.4 流動性: MMFCN 廃止

agent 自身の resting 指値が反対側流動性になるため、**外生 MMFCN は不要**(002 で
「研究対象でない構造的松葉杖」と位置づけたもの)。MMFCN 配管は YH007-8 config から外す。
ただし**起動直後の板が空**だと最初の約定が起きないので、**warmup での seeding**
(初期 resting order を撒く or 数 bar は ZI で板を温める)を入れる。

### 3.5 payoff / 参加(002 から継承)

$-game / GCMG 型・毎バー実価格結合 payoff(002 §4.3)と確信度連動の参加閾値 r_min、
両戦略 rolling score 選択(002 §4.4 / YH007-3 `adaptive_agent.py` で実装済)を**そのまま流用**。
変わるのは「注文の出し方(MARKET→LIMIT)」だけで、認知・淘汰ロジックは不変。

---

## 4. 【Guard 3】Control baseline = Zero-Intelligence

**自己組織化 CDA は ZI(ランダム注文)だけでも SF の一部を生む**
(Smith-Farmer-Gillemot-Krishnamurthy 2003)。よって「YH007-8 で SF が出た」だけでは
**Kronos 由来か CDA 機構由来か切り分けられない**(= 次の詰まりの種)。

- **Control**: §3 と**全く同じ LIMIT-placement 機構**で、評価値 `v_i` を **Kronos でなく
  ランダム(random walk / 一様)に差し替えた** agent 群。`zero_intelligence/` の思想を PAMS
  LIMIT agent として実装(reduced-form アダプタは流用不可、§2 注意)。
- **比較**: **CI×Kronos vs CI×ZI を同一板設定で走らせ、SF 指標の差分 = Kronos の寄与**。
- これを**最初の run から baseline に組み込む**(後付け禁止)。

---

## 5. 【Guard 4】測定規律(最初の run から焼き込む)

002 の「120 bar single-seed」の轍を踏まない:

- **≥ 500 bar**(Cont 2001)、できれば 1000–2000 bar。
- **multi-seed**(≥ 8 seed)で seed 平均 + ばらつき。
- **Hill α は jackknife / bootstrap CI 付き**(点推定の差を結論にしない)。
- **market / mid 両 metric 併記**(片方だけ見ない)。
- **単一ジャンプ支配の診断**: 裾質量の何 % が最大 1 bar か、`max|r| / std`。
- **mid 連続性の診断**: mid 増分の tick 単位分布(0/±1 tick 張り付き = まだ量子化、§3.3)。
- **bounce 診断**: `ret_acf τ=1`(目標 ~0)。再利用: `experiments/speculation_game/yh007_midprice_diagnostic.py`。

---

## 6. 成功条件(YH007-8 の検証ターゲット)

SF を「出す」ことではなく、**信用できる測定土台が立つこと**が合格条件。3 点同時:

1. **bounce 消失**: `ret_acf τ=1 → ~0`(|.|<0.1)。market/mid の乖離が縮む。
2. **mid 連続(非量子化)**: mid 増分が 0/±1 tick に張り付かず、裾が単一ジャンプ支配でない
   (`max|r|/std` が naïve 比で大幅低下)。
3. **ZI control 比で Kronos 寄与が分離できる**: CI×Kronos と CI×ZI で SF 指標に
   **統計的に有意な差**(CI 付き)。

この 3 点が揃って初めて、**YH007-4〜7 の機構 ablation を自己組織化板の上で再走する意味が出る**
(002 §8.x の含意)。揃わなければ §3.2/§3.3 の較正に戻る。

---

## 7. 実験計画(β 検証 = 実装・実行セッション向け)

| Phase | 内容 | backend | 合格 |
|---|---|---|---|
| **P0** | PAMS LIMIT agent 骨格(§3.1)+ TTL + warmup seeding。tests(注文が LIMIT で出る / 板が爆発しない / 約定が起きる) | mock | 疎通 GREEN |
| **P1** | ZI control(§4)実装 + tick 較正(§3.3)。mid 連続性診断で 0/±1 張り付き解消 | mock | 成功条件 2 |
| **P2** | CI×Kronos(§3.1–3.5)実装。分散注入(§3.2)で板が多レベルに散ることを確認 | mock | 板分散 + bounce 診断(成功条件 1) |
| **P3** | ≥500 bar × multi-seed で CI×Kronos vs ZI control(§5 規律フル) | mock | 成功条件 3(差分有意) |
| **P4** | 実 Kronos 閉ループで P3 を再走(headline) | real | 3 点同時達成 |
| **P5** | 達成後、機構 ablation(YH007-4〜7)を自己組織化板で再走 | real | 002 の問いに回答 |

mock(定数/ランダム信号)で板機構と artifact 消去を検証 → 実 Kronos は headline のみ
(artifact 診断は信号に依らないため、§5 の大半は mock で済む。002 §10-E)。

---

## 8. 実装マップ

| 必要物 | 出発点 |
|---|---|
| LIMIT-posting PAMS agent | `kronos_lob/agents.py`(MARKET→LIMIT 差し替え)+ `pams.order.LIMIT_ORDER` |
| 評価値 → 指値価格ロジック | `chiarella_iori/model.py`(fund/chart/noise + orderMargin を**参照**、PAMS agent に移植) |
| ZI control | `zero_intelligence/model.py` の思想を PAMS LIMIT agent 化 |
| Kronos 信号 hub / 2 読み / 参加 / 淘汰 | `kronos_lob/{signal_hub,adaptive_agent}.py`(そのまま) |
| bar 集約 / mid metric / 診断 | `kronos_lob/bar_aggregator.py`(price_source 済)+ `yh007_midprice_diagnostic.py` |
| TTL/cancel 設計 | `imported/.../docs/refs_sg_lob_code_semantics.md §3.1`(O(N²) 回避) |
| SF battery | `packages/stylized_facts/` |

---

## 9. 論理・戦略レビュー観点(α 検証 = レビューセッション向け)

実装前に**潰すべき前提**(ここを突いてほしい):

1. **「全員 LIMIT で bounce が消える」は本当か**: marketable 指値が多ければ結局クロスして
   bounce が残るのでは? aggressive/passive 比のどこで bounce が消えるか、理論的下限はあるか。
2. **分散注入(§3.2)は十分か**: per-agent offset を入れても、共有信号の強い drift 下では
   全員が同じ側に寄る瞬間がある(= 一方向 only の板)。これは herding として**残すべき現象**か、
   **潰すべき degeneracy** か。研究問いとの整合。
3. **ZI control の公平性**: CI×Kronos と ZI で「分散の大きさ」を揃えないと、SF 差が
   「Kronos の予測力」でなく「分散スケールの違い」になる。control の正規化をどう定義するか。
4. **tick 較正の循環**: tick を細かくすれば mid は連続になるが、現実の tick は外生制約。
   「artifact 消去のための tick 較正」が**現実性を犠牲にしていないか**(YH007-5 で tick/depth を
   いじったら逆に artifact が出た前例)。
5. **成功条件 6.3 の検出力**: 8 seed × 500 bar で Kronos vs ZI の SF 差を有意に検出できる
   サンプルサイズか。事前に power analysis すべきか。
6. **scope**: P5(機構 ablation 再走)まで含めると巨大。003 は P0–P4(土台確立)に絞り、
   P5 は 002 に差し戻す / 別 spec にするべきか。

---

## 10. 未解決(設計判断)

- **bar 単位 vs step 単位の意思決定**: Kronos はバー予測。指値を「毎 bar 更新」か「毎 step
  貼り替え」か(貼り替え頻度が queue dynamics に効く)。
- **在庫/予算制約**: LIMIT で resting 中の在庫・現金の扱い($-game payoff との整合)。
- **warmup seeding の方式**: ZI で温める / 初期 resting を撒く / fundamental 周りに seed。
- **実 Kronos のバッチ化**: 共有 hub 1 本 × sample_count をどう CPU 並列するか(002 §7 地雷 4)。

---

## 11. 改訂履歴
| 日付 | 内容 |
|---|---|
| 2026-06-23 | 初版ドラフト。002 の negative result(両 metric artifact / inconclusive)を受けた YH007-8 自己組織化板(CI×Kronos)設計。全 LIMIT 化 + 内生流動性(MMFCN 廃止)+ Kronos 評価値→指値。4 ガード(分散注入 / tick 較正 / ZI control / 測定規律)、成功条件 3 点(bounce 消失 ∧ mid 連続 ∧ ZI 比で Kronos 寄与分離)、実験計画 P0–P5、α(論理レビュー)/β(実装実行)分担。CI/ZI は reduced-form アダプタのため PAMS LIMIT agent を新規実装する点を明記。 |
