# ontology.md — ABM-Microstructure / 用語定義
<!-- ここの定義を agent は一次解釈に使う。一般的な意味で勝手に解釈しない。全文は docs/research-design.md。 -->

## 用語
- **能力非対称 (capability asymmetry)**: 参加者間の速さ・賢さの差。高能力者が低能力者から価値を抽出する駆動力。
- **抽出 (extraction)**: 高能力参加者が低能力参加者から得る富の移転。本研究では2種 — 速度ベースと学習ベース（→「混同しやすい語」）。
- **速度ベース抽出 / sniping / picking off**: stale quote（更新が遅れた気配）を、外生 true price との乖離を突いて反応的アービトラージャーが拾う抽出。実験 A の失敗モード。
- **LVR (loss-versus-rebalancing)**: 受動的 LP の保有価値と、true price で連続 rebalance する複製ポートフォリオ価値の差（Milionis et al. 2022 定義）。AMM 版の sniping。GBM 下で σ² と pool 曲率の閉形式。実験 A の検証ターゲット。
- **学習ベース抽出 / tacit collusion**: 学習 MM 同士が明示的合意なしに supra-competitive な spread を学習・維持する協調。実験 B の失敗モード。
- **supra-competitive markup**: 実現 spread の競争ベンチマークに対する超過。markup = (実現 spread − 競争 spread) / 競争 spread。競争ベンチマークは同一 n の myopic-Nash（独占ではない, A1）。
- **competitive benchmark (競争 spread)**: markup の分母。同一 n 体の myopic / one-shot stage-game Nash＝arbitrageur 逆選択への **Glosten-Milgrom break-even**。**独占（単体 MM）spread とは別物**（→「混同しやすい語」）。
- **zero-intelligence (ZI) floor**: メカニズム＋order-flow 制約だけで出る spread（知能ゼロのベースライン、固有名は出さない）。「どこからが戦略/知能の寄与か」を分離。**順序訂正（002 D-B5, 2026-06-10）**: 勝者総取り spread 競争では理論順序は **myopic-Nash ≤ 学習実現（収束時）**で、ZI（=E[min h]、grid 中央寄り）は**中間参照点**——旧記述「ZI ≤ myopic-Nash ≤ 実現」は誤り。学習実現が ZI の下（競争学習）か上（協調学習）かが診断情報。**操作的定義（混同注意）**: 本実装の ZI は各期 action grid 上の**一様 i.i.d.（完全ランダム・flow 較正なし）**＝戦略的内容ゼロの内部参照点。実データに flow 統計を較正するタイプの ZI（外部妥当性・stylized facts 再現の道具）とは別物。水準は grid 支持域に依存する（ceiling と同種の限界）。
- **demand-reduction（uniform-price）**: uniform-price clearing で marginal quote が約定全量の受取価格に効くため、undercut が自分の受取価格を不利に動かす誘因。Bertrand の「undercut 全取り」が成立しない理由（C1）。
- **Kyle λ**: 注文サイズ→価格変化の price impact 係数。実験A の anchor battery の impact 層（GM=スプレッド層、Budish=sniping 層、clearing=batch 層と並ぶ）。実装は **identity-blind flow 回帰**：sim は主体を知らずに λ̂=Σx·Δp/Σx² を測り、anchor は flow 組成から独立導出。N=1 で **GM identity（λ = competitive half-spread h\*）**＝spread 層との三角検証（D5b v2、旧 `=J` の circular 版は finding 0001 ③ で閉鎖）。
- **participation margin**: `f·(noise 約定量) − sniping 損 − 機会コスト c`。competitive MM は利益ゼロなので、流動性存続は PnL 符号でなくこの margin の符号（退出判定）で測る。連続 vs batch が退出を反転させるか＝US3。AMM の「fee が LVR を補償→LP 残留か」と同型。
- **anchor battery（実験A）**: GM break-even ＋ Kyle λ ＋ Budish rent ＋ uniform-price clearing 単体テストの4層。sim と独立実装し、形再現＋dt→0 収束＋tight SE で判定。**LVR は含まない**。
- **batch×抽出クロスオーバー（finding 0001）**: batch が速度ベース抽出を減らすか増やすかは spread の広さ h に依存。h≪J で減・h~J で増（net 変位の凸性）。検証済（独立アンカー＋sim）。
- **Green-Porter チャネル**: batch（離散・透明・反復）が監視/懲罰を容易にし collusion を**促進**する力（実験B）。
- **arbitrageur-predation チャネル**: 高 h（collusive な広い spread）で batch が広い気配を sniping に晒し collusion を**破壊**する力（finding 0001 由来、実験B）。B はこの二力の対決。
- **committed-quote / revisable-quote**: MM がバッチ内で気配を更新しない（committed＝遅い MM、predation が生きる）か、更新できる（revisable＝純 Budish FBA、sniping 消失）か。design lever の定義に関わる機構選択。
- **collusion index**: markup ＋ 逸脱に対する懲罰（reward-punishment 構造）の検出。
- **deviation + punishment test / impulse-response**: 強制 1 期逸脱後に協調が懲罰経由で再確立するかを見る検査。「本物の collusion」と「探索不足の高止まり」を区別する第一級の妥当性検査。実装（002）は決定論 rollout＋解析収支（期待 stage payoff）——frozen policy の state は action 履歴のみなので乱数不要。
- **認定 (certified)**: collusion と呼んでよい点の機械判定（A3×C2 gate の実装、002 verdict）。= markup 有意（seed 平均 − 2SE > 5% floor）∧ impulse-response pass 率 ≥ 0.8（懲罰 ∧ 逸脱不利 ∧ 再確立）∧ 全 seed 収束。markup の高止まりだけでは認定されない。
- **予算 ledger**: 学習期数の tier 別台帳（coarse/dense/robustness 各 ≤1×10⁹、総 3×10⁹、D-B9）。上限を超える run は起動拒否され、拒否自体も記録される（漸進的予算超過の遮断、B1）。
- **連続マッチング (continuous matching)**: 価格優先・時間優先の continuous LOB matching、または continuous CFMM swap。ベースライン機構。
- **batch auction (FBA)**: interval N 期ごとに注文を集約し uniform price で一括 clearing する機構。N はパラメータ。速度競争を除去する設計レバー。
- **batch interval N**: batch の集約周期。主要 sweep 対象。
- **uniform-price**: batch 内全約定が単一の clearing price で約定する規則。⚠ 逸脱誘因は Bertrand とは異なる（→「混同しやすい語」）。
- **arb-auction (arbitrage-right auction)**: 各 batch のアービトラージ権を auction し落札額を LP に rebate する機構（MEV redistribution 系）。**任意条件 C**、scope creep 注意（→ review B2）。
- **実効スプレッド (effective spread)**: (約定価格 − mid) の符号付き、ノイズトレーダーについて集計。標準の取引コスト測度。
- **adverse selection**: true price ジャンプ時に MM の stale quote を抜かれる損。**逆選択源は arbitrageur**（noise trader は無方向なので非該当, C4）。competitive spread はこの逆選択への break-even で決まる。
- **inventory risk (在庫リスク)**: MM の保有偏りに伴うコスト。quoting を根本から変える（Avellaneda-Stoikov）。state/reward に入れるかは load-bearing（→ review C3）。
- **トレードオフ・フロンティア**: 各市場設計を (抽出削減, collusion markup) 平面に置いた Pareto 図。本研究の中心測度・主結果。

## 混同しやすい語（注意）
- **抽出 A（速度ベース）と 抽出 B（学習ベース）は別物**。連続した一現象ではない。victim（A=受動的 LP/MM、B=taker）も機構（A=情報・速度非対称、B=反復ゲーム学習）も別。同じ batch がそれぞれに逆向きに効きうる、が研究の核。
- **competitive benchmark ≠ 独占(単体 MM) spread**。単体 MM の best-response は独占 spread。これを markup 分母にすると collusion を過小評価する。正しくは同一 n 体の myopic/one-shot stage-game Nash（→ review A1）。
- **uniform-price batch の逸脱誘因 ≠ Bertrand**。「微小 undercut で batch 全取り」は誤り（demand-reduction で自分の受取価格が不利化, C1）。帰結：破壊方向が弱い ⇒ 理論 prior は「batch は collusion 促進」に傾く ⇒ confirmation risk（sim が prior を追認する危険、→ review ③）。
- **実験 A は finding ではなく simulator のユニットテスト**。検証すべきは spread だけでなく impact 層(Kyle)・clearing 層も（A2 layered validation）。
- **LVR は CLOB spine では使えない**。LVR は pool 量を要する AMM 概念。実験A の市場オブジェクトは CLOB/quoting-MM＝pool 不在なので算出不能。CLOB での LP 抽出は sniping/逆選択（GM/Budish）で測る。LVR が戻るのは後回しの AMM variant feature のみ。
