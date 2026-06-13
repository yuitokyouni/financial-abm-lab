# ABM-Microstructure Constitution
<!-- 一次ソース。設計の全文は docs/research-design.md、査読は docs/research-design-review.md。本書は不変の原則のみ。 -->

## Mission
能力非対称（速さ・賢さの差）下の市場で「誰がどれだけ抽出されるか」を決めるのは微細構造（マッチング規則）である、を ABM で検証する。中心問題は単一：**連続マッチングを batch/auction に置き換える単一介入が、速度ベース抽出と学習ベース collusion にどう効くか**。目的は trade-off を *見つける* ことではなく **設計 →(抽出, collusion) の地図を作る**こと。trade-off（A改善・B悪化）/ 整合（両改善）/ 対立（両悪化）のどれも結果として情報になる。

## Core Principles

### I. Verify before you discover（検証先行・NON-NEGOTIABLE）
実験 A は finding ではなく simulator のユニットテスト。解析的真値（Milionis LVR / Budish sniping レント）に許容誤差内で一致するまで、解析的真値の無い実験 B に進まない。検証済み harness だけが B の信用の土台。

### II. Two failure modes, one lever（混同しない）
A=速度ベース抽出（非学習・受動的 victim）と B=学習ベース collusion（戦略的協調・taker victim）は連続した一現象ではない。victim も機構も別。両者をつなぐのは「同じ設計レバーへの応答が両モードでどう違うか」という相互作用のみ。

### III. Map, don't pre-judge（地図を作る・結論を先取りしない）
batch が collusion を促進する（監視・反復性: Green & Porter）か破壊するかは曖昧。ただし破壊方向の「uniform-price で微小 undercut 全取り」は Bertrand の誤借用で、demand-reduction 誘因により脚は弱い ⇒ 理論的 prior は「促進」に傾く。よって **sim が傾いた prior を追認する confirmation risk** を自覚し、null（整合/対立も含む outcome space）を最初から入れ、結果で決める。trade-off の存在に研究を依存させない。

### IV. A single run proves nothing（頑健性必須）
結果はアルゴリズム・ハイパーパラメータ・seed に依存する。複数アルゴリズム × 複数 seed × 主要パラメータ grid の頑健性を経ない主張はしない。tacit collusion は deviation+punishment（impulse-response）で「本物の支持均衡」を確認してからのみ collusion と呼ぶ。**この検査を通過した点でのみ下流測定（memory 閾値等）を行う**＝artifact の閾値を測らない gate。同時学習は収束の理論保証なし＝経験的安定にすぎない。

### V. Honest scope（スコープを誇張しない）
外生 GBM 価格を仮定する以上、答えられるのは「誰が金を取るか・スプレッド」であって「価格は正しいか（価格発見）」ではない。collusion の最深の害（価格発見の歪み）は harness の外。collusion の創発は agent の memory/学習設定に条件付き（memory 量は sweep 対象）。さらに benchmark・検証は内部整合（解析モデル相手）にすぎないため、**σ/fee/N/flow の最低一点を実在 venue/銘柄にアンカー**した検証ケースを含め、内部結果の外部的含意を担保する。これらの限界を結果に明記する。

## Files as truth
- 設計一次ソース: `docs/research-design.md`
- 査読・未解決論点: `docs/research-design-review.md`
- 検証済み発見: `docs/findings/`（例: 0001 batch×抽出クロスオーバー → B は Green-Porter 促進 vs arbitrageur 捕食の対決）
- 用語: `ontology.md` ／ 標準事実: `CLAUDE.md` ／ 実装: `src/microstructure/`、検証: `tests/`

## Governance
本 constitution は他の慣行に優先する。設計変更は docs/research-design.md と本書を更新し、非自明な判断は ADR（docs/adr/）に残す。spec（specs/, /speckit-*）は本書と整合しなければならない。噛み合わなければ実装を止め、本書か設計書に戻る。

**Version**: 0.2.0 | **Ratified**: 2026-06-02 | **Last Amended**: 2026-06-02
<!-- 0.2.0: 査読受け II→map framing, III に confirmation-risk/null, IV に gate, V に外部妥当性を追加。 -->

## Open knots（spec 確定前に解く・優先順）
1. **A1+C4+C5（一度に）**: 逆選択源=arbitrageur 固定 → GM break-even で competitive spread(markup 分母)と検証アンカーが同時決定 → 設計マップは B 世界で測る。
2. **A3 を ① で gate**: impulse-response 通過点のみ collusion 認定 → その後 memory 閾値(C2)。
3. **② null を outcome space に**: 地図 framing を主張構造へ。
4. 残: B1 compute 予算 / C3 inventory 段階 / ④ 外部アンカー銘柄 / C6 文献調査。
