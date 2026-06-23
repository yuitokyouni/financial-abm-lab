# 003 — YH007-8: 自己組織化板 (Chiarella-Iori × Kronos) — naïve 設計の artifact を構造的に潰す

**状態: ドラフト v2 (α レビュー反映済 / 実装前)**。本 spec は
`specs/002-yh007-kronos-microstructure.md` の §5 YH007-8 行 + §10-D を展開した
**ルートコーズ修正サブ spec**。002 は ground truth のまま、本 003 は YH007-8(自己組織化板)の
設計を確定するための作業文書。

> 親 spec: 002 §8.x(全機構 ablation の結論撤回)/ §10(新課題 A〜E)。
> v2 改訂: α レビュー(2026-06-23)の 9 指摘を反映。指揮(architect)裁定は §12 に集約。

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
| Kronos = 方向 + サイズ | **Kronos = 評価値(価格分布)→ 指値価格**(分布情報を捨てない、§3.6) |
| 約定 = 常に spread クロス | **約定 = 指値が反対側 best をクロスした時のみ(marketability 内生、§3.1)** |
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

### 3.1 注文配置則(Kronos 評価値 → 指値価格)+ aggressive rate 較正 【α §9-1 BLOCKER 反映】

各 agent i は毎 bar、評価値 `v_i` を計算して**片側 1 本**の指値を出す:

- **評価値** `v_i`: Kronos 分布の quantile から取る(§3.6)。trend/fade の 2 読み(002 §4.2)で
  上下に置き分け。
- **方向**: `v_i > mid` なら buy、`< mid` なら sell。
- **指値価格** `price_i = v_i × (1 ∓ margin_i)`(buy は下、sell は上に margin。CI orderMargin 流儀)。
- **marketability(内生)**: `price_i` が反対側 best をクロスすれば**即約定(aggressive)**、
  しなければ**板に resting(passive)**。MARKET/LIMIT の二分でなく、置いた価格と反対板の関係で
  aggressive/passive が決まる。← bounce が消える本質。
- **同一 agent の両側同時 resting は禁止**【α §10-2】: PAMS の self-trade を避けるため、各 agent は
  常に片側のみ resting。前 bar の未約定指値は新規発注前に自己キャンセル(§3.3)。
- **TTL/cancel 必須**: resting 指値は `time_window` で expire / step 単位で自己キャンセル。
  さもないと YH006 の cancel/resubmit 累積による **O(N²) 板爆発**
  (`imported/.../docs/refs_sg_lob_code_semantics.md §3.1`)。

**aggressive rate a の目標帯と較正【BLOCKER 解決】**:
Roll bounce は消えるか残るかが **aggressive crossing 比率 a** で決まる。簡易見積もり
`ret_acf τ=1 ≈ -(spread_ticks/2)·a·(1 − corr(side))` より:
- `a = 0` → bounce 消失だが**約定ゼロ = 測定対象消失**(YH007-7 凍結 artifact の再来)。
- `a ≈ 0.5` → MARKET 構成と同じ bounce。
- **目標 `a ∈ [0.05, 0.20]`**(`a ≤ 0.2` で `ret_acf τ=1` が |.|<0.1 に入る Roll 簡易見積もり)。

→ **較正 step(P1.5、P1 と P2 の間)**: aggressive rate `a` を測定し、`[a_min, a_max]` に収まるよう
**`margin_i` の平均・分散を auto-tune**。実証は P1(ZI control)で取り、CI×Kronos に引き継ぐ。
`a` は run 中 **常時 monitor**(§5)。

### 3.2 【Guard 2】分散注入 — 配置層の「全員同じ」縮退を防ぐ

計算量のため Kronos 信号は共有 hub 1 本(`kronos_lob/signal_hub.py`)。**全員の `v_i` が同一だと
同一価格帯に積む → 板分散ゼロ → 薄板に逆戻り**(=「Kronos だけだと全員同じ」の**配置層版**。
最も再発しやすい)。分散源(優先順):

1. **【主】Kronos 分布の quantile-rank サンプリング**(§3.6)— agent ごとに分布の別 quantile を
   評価値に使い、**Kronos 由来の自然な分散**を入れる(人工 offset への依存を減らす)。
2. **① 2 読み**(trend/fade で上下に置き分け、002 §4.2)。
3. **【従】per-agent ランダム offset / 確信度依存 margin**(1・2 で分散不足の時の補助)。

**herding(残す)vs degeneracy(潰す)の判定【α §9-2】**:
- **残すべき herding**: market state 依存で、時系列で来たり去ったりする一斉同方向 placement
  (= 002 §2 機構 3 Lux-Marchesi switching = vol clustering 源。研究対象であって潰さない)。
- **潰すべき degeneracy**: 初期化や分散源の不在で、**全 step を通じて常に**一斉になる(戦略多様性 0)。
- **P2 合格診断**: agent 横断の placement price の **時間平均分散が seed 全体で非ゼロ、かつ時系列で
  変動**する。満たせば §3.2 OK。

### 3.3 【Guard 1 + α §9-4/§10-1 統合】bar/step 2 階層 + tick 較正

§9-4(tick 較正の現実性循環)と §10-1(bar/step)は同じ循環の表裏。統合解:

- **2 階層**: **評価値 `v_i` は bar 単位で更新**(Kronos がバー予測なので自然)、**TTL 内の
  自己キャンセル + 再貼り付けは step 単位**。
  - 全部 step 貼り替え → queue 上位が常に刷新され **queue dynamics 消失**(毎 step ZI フロー化)。
  - 全部 bar 固定 → bar 間で板が凍結 → Kronos 更新まで **mid jump 再来**。
  - → 2 階層が両極端を回避。
- **tick 較正条件**: placement 分散の中央値 ÷ tick が **~5–20** の範囲。細かすぎると全員が
  prevailing best 1 段下に置く degeneracy(§3.2 の別形)、粗すぎると mid 量子化。
- **較正成功条件(P1, ZI control で測る)**: **1 bar あたりの mid 増分の中央値が ~2–5 tick**
  (0/±1 tick 張り付き無し、かつ 100 tick ジャンプも無し)。

### 3.4 【α §10-3 統合】流動性: MMFCN 廃止 + ZI warmup

agent 自身の resting 指値が反対側流動性になるため、**外生 MMFCN は不要**(002 で「研究対象でない
構造的松葉杖」)。MMFCN 配管は YH007-8 config から外す。
- **warmup = ZI control(§4)で N bar 板を温めてから本 agent を投入**。起動直後の空板問題を
  解消し、ZI 実装を warmup でも再利用(二重利益)。

### 3.5 payoff / 参加(002 から継承)

$-game / GCMG 型・毎バー実価格結合 payoff(002 §4.3)+ 確信度連動 r_min + 両戦略 rolling score
選択(YH007-3 `adaptive_agent.py`)を**流用**。変わるのは「注文の出し方(MARKET→LIMIT)」だけ。
- **在庫/予算 bookkeeping は不要**【α §10-2】: payoff は `行動 a × バーリターン r` で在庫を
  仮想化(mark-to-market)するので、resting 量・現金の厳密会計は持たない。

### 3.6 【α NEW 反映】Kronos quantile-rank 評価値 — 分布幅を捨てない

002 §4.1 は「mode でなく sample を引いて確信度を測る」と書いたが、v1 §3.1 は中心 `p_hat` 1 値
しか使っておらず矛盾していた。修正:

- **評価値 `v_i` = Kronos 予測**分布**の quantile**(agent_id を 0..1 の quantile rank に正規化して
  サンプル)。例: agent が下位 quantile なら低い評価値 → 低い指値。
- 効果:
  1. **配置層に Kronos 由来の自然な分散**が入る(§3.2 guard を薄める)。
  2. **「Kronos の分布幅自体に予測力があるか」**を ZI 比較で同時検証(情報量大幅増)。
  3. **§10-4 のバッチ化と整合**: 1 回の `predict` で全 agent 分の quantile が取れる
     (agent ごとに呼ばない)。
- ZI-matched control(§4)は **この quantile 分布の 1・2 次モーメントを matching** する
  (= 分布幅も dose match)。中心位置の予測力を分離できる。

---

## 4. 【Guard 3 + α §9-3 BLOCKER 反映】Control baseline = Zero-Intelligence(dose matching)

**自己組織化 CDA は ZI(ランダム注文)だけでも SF の一部を生む**
(Smith-Farmer-Gillemot-Krishnamurthy 2003)。「YH007-8 で SF が出た」だけでは **Kronos 由来か
CDA 機構由来か切り分けられない**。さらに ZI の**分散を Kronos と揃えないと**、SF 差が
「Kronos の予測力」でなく「単に動かすパワーの違い(dose 不一致)」になる(intervention vs
control の dose matching 問題)。

**2 種類の ZI**:
- **ZI-naïve**: 完全独立ランダム評価値(情報ゼロの**最弱 baseline**、併走参照)。
- **ZI-matched**【headline 比較対象】: Kronos の評価値増分 `Δv_t` の**経験的 1 次・2 次モーメントを
  matching したガウス過程**(drift = 0、分散 = Kronos と一致、§3.6 の quantile 幅も match)。
  → **CI×Kronos と ZI-matched の SF 差 = 中心位置(=Kronos の予測力)の寄与**。

**dose matching の要点**(揃えるべき量):
- **drift 強度**: Kronos は平均 +drift を出しがち(constant mock がそう)。ZI-matched は drift 0 に
  揃え、「fat tail/vol clustering が drift の有無由来」になる交絡を排除。
- **評価値増分分散**: `Var(Δv_t)` を一致。
- **更新間隔**: ともに bar 単位(§3.3 の 2 階層を ZI も共有)。
- **`|v_i − mid|` 分布**: aggressive rate を揃える前提(§3.1 の `a` 較正を両者同一手順で)。

**マッチング診断【§5 に追加】**: SF 比較前に `Δv_t` のヒストグラム / Q-Q plot を出し、評価値分散の
一致を**検証**。一致していなければ SF 比較は無意味として P3 を止める。

---

## 5. 【Guard 4 + α §9-5/§9-3 反映】測定規律(最初の run から焼き込む)

002 の「120 bar single-seed」の轍を踏まない。**pre-registered** に固定:

- **≥ 500 bar**(Cont 2001)、できれば 1000–2000 bar。
- **multi-seed**(初期 8、power analysis で増減)で seed 平均 + ばらつき。
- **Hill α は jackknife / bootstrap CI 付き**(点推定の差を結論にしない)。
- **market / mid 両 metric 併記**。
- **単一ジャンプ支配の診断**: 裾質量の何 % が最大 1 bar か、`max|r|/std`。
- **mid 連続性の診断**: mid 増分の tick 単位分布(0/±1 張り付き = 量子化、§3.3)。
- **bounce 診断**: `ret_acf τ=1`(目標 ~0)。`yh007_midprice_diagnostic.py` 再利用。
- **aggressive rate `a` の常時 monitor**(§3.1、目標 [0.05, 0.20])。
- **dose-matching 検証**: `Δv_t` の ヒスト/Q-Q(§4)。
- **power analysis pilot【α §9-5】**: P1 で ZI-matched を 2 種 drift 強度 × 8 seed 走らせ、
  SF 指標の **seed 間 std を実測 → 必要 seed 数を逆算**。effect size 目標
  (例 `|Δvol_acf| > 0.1`、`|ΔHill α|` > seed間SE)を **pre-registered table** に明記。
  8 seed で不足なら **seed=16 or bar=2000 を P3 開始前に確定**(走り直しコスト回避)。

---

## 6. 成功条件(YH007-8 の検証ターゲット)

SF を「出す」ことではなく、**信用できる測定土台が立つこと**が合格条件。3 点同時:

1. **bounce 消失**: `ret_acf τ=1 → ~0`(|.|<0.1)。aggressive rate `a ∈ [0.05,0.20]` で達成。
2. **mid 連続(非量子化)**: mid 増分中央値 ~2–5 tick、0/±1 張り付き無し、裾が単一ジャンプ
   支配でない(`max|r|/std` が naïve 比で大幅低下)。
3. **ZI-matched control 比で Kronos 寄与が分離できる**: CI×Kronos と ZI-matched で SF 指標に
   **CI 付きで統計的に有意な差**(power analysis で検出力を事前担保)。

3 点が揃って初めて、**YH007-4〜7 の機構 ablation を自己組織化板の上で再走する意味が出る**。
揃わなければ §3.1(a 較正)/§3.3(tick 較正)に戻る。

---

## 7. 実験計画(β 検証 = 実装・実行セッション向け)

| Phase | 内容 | backend | 合格 |
|---|---|---|---|
| **P0** | PAMS LIMIT agent 骨格(§3.1、片側 resting + TTL)+ ZI warmup(§3.4)。tests(LIMIT で出る / 板非爆発 / 約定発生 / self-trade 無し) | mock | 疎通 GREEN |
| **P1** | ZI-naïve + ZI-matched(§4)実装 + tick 較正(§3.3)。mid 連続性診断 + **power analysis pilot**(§5) | mock | 成功条件 2 + 必要 seed 数確定 |
| **P1.5** | **aggressive rate `a` 較正**(§3.1、margin_i auto-tune で a∈[0.05,0.20]) | mock | bounce 診断(成功条件 1) |
| **P2** | CI×Kronos(§3.1–3.6、quantile-rank 評価値)実装。分散注入診断(§3.2 herding≠degeneracy) | mock | 板分散 + a 維持 |
| **P3** | ≥500 bar × multi-seed で CI×Kronos vs ZI-matched(§5 規律フル + dose-match 検証) | mock | 成功条件 3(差分有意) |
| **P4** | 実 Kronos 閉ループで P3 を再走(headline)。seed/bar は P1 で確定済 | real | 3 点同時達成 |
| **P5** | **(003 scope 外、別 spec / 002 §11 に差し戻し)** 機構 ablation を自己組織化板で再走 | real | 002 の問いに回答 |

mock で板機構と artifact 消去を検証 → 実 Kronos は headline のみ(artifact 診断は信号に依らない)。

---

## 8. 実装マップ

| 必要物 | 出発点 |
|---|---|
| LIMIT-posting PAMS agent | `kronos_lob/agents.py`(MARKET→LIMIT 差し替え)+ `pams.order.LIMIT_ORDER` |
| 評価値 → 指値価格ロジック | `chiarella_iori/model.py`(orderMargin を**参照**、PAMS agent に移植) |
| ZI-naïve / ZI-matched control | `zero_intelligence/model.py` の思想を PAMS LIMIT agent 化 + dose matching |
| Kronos quantile 取得 | `KronosPredictor`(分布 quantile を 1 回の predict で、§3.6/§10-4) |
| 信号 hub / 2 読み / 参加 / 淘汰 | `kronos_lob/{signal_hub,adaptive_agent}.py`(そのまま) |
| bar 集約 / mid metric / 診断 | `kronos_lob/bar_aggregator.py`(price_source 済)+ `yh007_midprice_diagnostic.py` |
| TTL/cancel 設計 | `imported/.../docs/refs_sg_lob_code_semantics.md §3.1` |
| SF battery | `packages/stylized_facts/` |

---

## 9. α レビュー反映状況(2026-06-23)

| 指摘 | 重み | 反映先 | 状態 |
|---|---|---|---|
| §9-1 aggressive rate 下限 | BLOCKER | §3.1(a∈[0.05,0.20] + margin auto-tune + P1.5) | ✅ 仕様化 |
| §9-3 ZI dose matching | BLOCKER | §4(ZI-naïve/matched + 分散正規化 + 診断) | ✅ 仕様化 |
| §9-4/§10-1 tick 較正 × bar/step 循環 | SEMI | §3.3(2 階層 + tick~5–20 + mid 増分~2–5tick) | ✅ 統合 |
| §9-5 検出力 / seed 本数 | DECIDE | §5(power analysis pilot を P1)+ P-plan | ✅ 仕様化 |
| §9-2 herding vs degeneracy | JUDGE | §3.2(判定基準 + P2 診断) | ✅ |
| §9-6 scope(P5 分離) | SUPPORT | §7 P5 注 + §12 裁定 | ✅ |
| §10-2 在庫 / self-trade | — | §3.1(片側 resting)+ §3.5(bookkeeping 不要) | ✅ |
| §10-3 warmup seeding | — | §3.4(ZI warmup) | ✅ |
| §10-4 Kronos バッチ化 | — | §3.6 + §8 + §10(下記、要 API 修正) | ⚠ P4 前 |
| NEW: 分布幅を捨てている | 本質 | §3.6(quantile-rank 評価値、格上げ) | ✅ 主分散源に昇格 |

---

## 10. 未解決(設計判断、P 着手前に詰める)

- **§10-4 Kronos バッチ化(P4 前 BLOCKER)**: 現 `KronosPredictor` は agent ごとに 1 回呼ぶ構造。
  共有 hub 1 本 × quantile-rank(§3.6)なら **1 回の predict で全 agent 分が取れる**はずなので、
  hub をその API に修正。002 §7 地雷 4 のレイテンシ(sample_count=16 で 1.5s/step)を**再見積もり**。
- **warmup 長 N**: ZI で何 bar 温めれば板が定常になるか(P1 で実測)。
- **quantile-rank の割り当て**: agent_id 固定 quantile か、毎 bar 再サンプルか(後者は分散↑だが
  agent identity が薄れる → 淘汰 §3.5 との整合を P2 で確認)。

---

## 11. 改訂履歴
| 日付 | 内容 |
|---|---|
| 2026-06-23 | 初版ドラフト。全 LIMIT 化 + 内生流動性(MMFCN 廃止)+ Kronos 評価値→指値。4 ガード、成功条件 3 点、実験計画 P0–P5、α/β 分担。CI/ZI は reduced-form のため PAMS LIMIT agent を新規実装する点を明記。 |
| 2026-06-23 | **v2: α レビュー(9 指摘)反映**。§3.1 に aggressive rate 目標帯 [0.05,0.20] + margin auto-tune(P1.5)+ 片側 resting 禁止。§3.2 に herding/degeneracy 判定 + 分散源優先順(quantile-rank 主)。§3.3 に bar/step 2 階層 + tick 較正条件。§3.4 に ZI warmup。**§3.6 新設(Kronos quantile-rank 評価値、002 §4.1 と整合、主分散源に格上げ)**。§4 を ZI-naïve/ZI-matched + dose matching に細分化。§5 に matching 検証 / a monitor / power analysis pilot。§7 に P1.5 追加・P5 を scope 外明示。§9 反映表・§12 裁定を新設。 |

---

## 12. 指揮(architect)裁定

- **α 全 9 指摘を採択**。うち 2 点を格上げ:
  - **NEW(分布幅)→ §3.6 として主分散源に昇格**。人工 offset 依存を減らし、ZI 比較で「分布幅の
    予測力」まで測れる。002 §4.1 との矛盾も解消。これが v2 の最大の改善。
  - **§9-3 dose matching → ZI-matched を headline 比較対象に格上げ**(ZI-naïve は最弱参照に降格)。
    これが無いと P3 は比較自体が無意味、の指摘は正しい。
- **BLOCKER(§9-1, §9-3)は本 v2 で仕様レベル解決済**。P0 着手可。
- **scope 裁定**: 003 は **P0–P4(土台確立)に限定**。P5(機構 ablation 再走)は土台合格後に
  **002 §11(新設)or 別 spec に差し戻し**。003 の合格判定を P5 で複雑化させない。
- **次アクション**: β に P0→P1→P1.5→P2 を依頼。**P1 の power analysis pilot 結果(必要 seed/bar)
  と §10-4 バッチ化の見積もりを戻してもらい**、P3/P4 の compute budget を確定してから real Kronos へ。
