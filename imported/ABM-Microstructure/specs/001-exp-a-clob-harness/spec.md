# Feature Specification: 実験A — CLOB 抽出検証 harness

**Feature Branch**: `001-exp-a-clob-harness`（main 上で作業、speckit は .specify/feature.json で追跡）

**Created**: 2026-06-02 ／ **Updated**: 2026-06-02 (v2: US3 participation, tolerance, anchor battery, coverage)

**Status**: Draft

**Input**: マイルストーン1 / 実験A。市場微細構造 simulator を解析的真値に対して検証する harness。一次ソース: `docs/research-design.md` §2/§4/§6、`.specify/memory/constitution.md`、`docs/research-design-review.md`（A1/A2/C4 結び目）。

## Fixed Invariants *(constitution-locked — 冒頭で固定、本 spec 内で変更不可)*

- **市場オブジェクト = CLOB / quoting-MM**。baseline は **inventory-free**。pool は無い → **LVR は A では算出不能・anchor から完全除外**（LVR は後回しの AMM variant feature 専用）。
- **非学習のみ**。RL/学習は本 feature に一切含まない。
- **検証先行（原則I）**：解析アンカーに合格するまで実験B（学習・collusion）に進まない。本 harness の存在意義は「真値の無いBを信じる license」を作ること。
- **knot（A1+C4+C5）**：逆選択源 = arbitrageur（noise trader ではない）。competitive spread = arbitrageur 逆選択への **GM break-even**（competitive・zero-profit。monopoly spread にしない＝knot 違反）。これが markup 分母と検証アンカーを同時に決める。MM が competitive で価格する帰結として **MM の構造的利益はゼロ**——だから「インセンティブ存続」は PnL 符号ではなく participation margin で測る（US3）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 解析アンカー battery に対する simulator 検証 (Priority: P1)

研究者として、連続マッチング CLOB 上で「ルールベース quoting MM ＋ 反応的 arbitrageur ＋ noise trader」を外生 GBM(+jump) 価格の下で走らせ、sim 出力が **層ごとの解析アンカー battery** に合格することを確認したい：(a) competitive spread＝GM break-even、(b) price impact＝Kyle λ、(c) sniping 抽出量＝Budish rent、(d) uniform-price clearing＝独立単体テスト。合格は **関数形/スケーリングの再現**＋**dt→0 収束**＋**tight な統計 consistency** で判定する。

**Why this priority**: これが MVP。合格しなければ実験Bを信じる根拠（license）が存在しない。harness の唯一の存在意義。A2（最もバグの入る層を test しろ）に従い、spread だけでなく impact 層・clearing 層も埋める。

**Independent Test**: 各アンカーについて、張ったパラメータ範囲（σ・N・alpha の関連レンジ＋高σ/粗dt の stress 領域）で sim を走らせ、(i) 連続時間アンカーの関数形を再現、(ii) dt 細分で sim→anchor が収束、(iii) seed 集計の tight な SE 内で一致、を assert。

**Acceptance Scenarios**:

1. **Given** σ・alpha の関連レンジ、**When** 連続 CLOB で competitive half-spread を測る、**Then** GM break-even の**関数形（σ・alpha 依存）**を再現する（点一致でなく形）。
2. **Given** 解像度 dt を細分（dt→0）、**When** 同一連続時間パラメータで再実行、**Then** `|sim − anchor|` が期待オーダーで 0 に収束する（離散化誤差を flat tolerance に吸わせない）。
3. **Given** seed を増やし SE を縮めた、**When** 一致を判定、**Then** その**縮んだ SE**（tight 側）を許容に使う（5% に逃げない）。
4. **Given** Kyle λ・Budish rent・uniform-price clearing、**When** それぞれ独立に測る/単体テスト、**Then** 各層が該当アンカーに合格する。

---

### User Story 2 — 連続 vs batch の抽出量定量比較 (Priority: P2)

研究者として、マッチング機構を N 期 uniform-price batch auction に切り替え、速度ベース抽出が連続マッチングに比して**減少**すること（および noise の実効スプレッド変化）を、理論の定性予測どおりに定量化したい。

**Why this priority**: A の第二の正当な産物（検証に次ぐ定量化）。B の設計レバーが A 世界で期待どおり振る舞うことを確認する。

**Independent Test**: 同一連続時間パラメータで連続 / batch を走らせ抽出量を比較。`extraction(batch) < extraction(continuous)` かつ差が σ・N で理論整合の形、を assert。

**Acceptance Scenarios**:

1. **Given** 同一 (σ, alpha)、**When** 連続と N期 batch で抽出量を測る、**Then** batch < continuous。
2. **Given** σ を sweep、**When** 各 σ で連続/batch を比較、**Then** 抽出量差は σ とともに単調増（速度ベース抽出は volatility 駆動）。
3. **Given** batch interval N=1、**When** 連続と比較、**Then** ほぼ一致（N=1 batch ≈ 連続の sanity check）。

---

### User Story 3 — LP 退出による流動性崩壊（participation margin） (Priority: P3)

研究者として、市場設計（連続 vs batch）が MM の**退出判定を反転させるか**を測りたい。GM break-even で価格する competitive MM は利益ゼロなので「PnL 符号」では何も出ない（US2 に潰れる）。代わりに participation margin を導入する：MM は fill ごとに fee `f` を稼ぎ、期待ネット `margin = f·(noise 約定量) − sniping 損 − 機会コスト c` が負なら市場から退出する。問いは「連続では退出するが batch では残る（or 逆）パラメータ領域が在るか」。

**Why this priority**: spread 水準（US2）とは別の本物の問い＝「設計が LP を退出させ流動性を崩すか」。AMM の『swap fee が LVR を補償できる→LP は残るか』サステナビリティ問題と同型で、経済的に最も意味のある US3。

**Independent Test**: (f, c, σ, N) を sweep し、各機構で margin 符号＝退出/残留を判定。連続と batch で判定が反転する領域を探す。

**Acceptance Scenarios**:

1. **Given** ある (f, c, σ)、**When** 連続で margin<0（退出）かつ batch で margin≥0（残留）、**Then** その領域を「設計が退出判定を反転させる」と記録する。
2. **Given** f を上げる、**When** sniping 損が一定、**Then** participation 領域が単調に広がる（fee が逆選択を補償する sanity check）。
3. **Given** c=0 かつ f=0、**When** sniping>0、**Then** margin<0（無補償なら退出）。

---

### Edge Cases

- σ → 0：抽出量はゼロに収束（価格が動かなければ picking-off が起きない）。
- batch 内で jump：同一 batch の clearing 価格と逆選択の扱いが定義どおりか。
- 同一 batch 内に複数注文同時到着：uniform price が単一に決まり約定割当が決定論的か。
- 複数 arbitrageur が競合：本 A では 1 体固定（下記 Assumptions）。逸脱は scope 外。
- 空板 / 片側のみ：clearing が破綻せず safe な no-trade になるか。
- dt を粗くした stress：バグと離散化誤差が最大化する領域で収束チェックが効くか。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: harness MUST 外生 GBM(+jump) の true price を生成し、価格が**取引に影響されない**こと。連続時間パラメータ（drift μ, vol σ, jump 強度 λ, jump size J）＋時間解像度 dt で表現。
- **FR-002**: harness MUST 3種エージェント：(a) ルールベース quoting MM（**inventory-free**、competitive/break-even 近傍で両側気配）、(b) 反応的 arbitrageur **1体**（true price 変動時に stale quote を規則の許す範囲で picking-off、**学習なし**）、(c) noise/liquidity trader（外生到着・無方向）。
- **FR-003**: arbitrageur MUST 逆選択源として機能する（true price 変動後、MM 更新前の stale quote を抜く＝1期 staleness）。
- **FR-004**: harness MUST 連続マッチング（価格優先・時間優先 CLOB）を baseline 機構として提供。
- **FR-005**: harness MUST N 期 uniform-price batch auction を提供（batch 内全約定が単一 clearing 価格、N をパラメータ化）。
- **FR-006**: harness MUST 抽出量を「arbitrageur 累積 PnL ＝ MM 犠牲」として測定（ゼロサム整合を assert）。
- **FR-007**: harness MUST noise trader の実効スプレッド（(約定価格 − mid) 符号付き）を測定。
- **FR-008**: harness MUST **participation margin** `f·(noise 約定量) − sniping 損 − c` を測定し、MM の退出/残留を判定（fee `f`・機会コスト `c` は SimConfig パラメータ）。
- **FR-009**: harness MUST competitive spread を arbitrageur 逆選択への **GM break-even** として測定（markup 分母兼検証アンカー）。
- **FR-010**: harness MUST 時間解像度 dt を持ち、価格/到着過程を dt でスケール（jump 確率 λ·dt、diffusion σ·√dt 等）し、**dt→0 で連続時間アンカーに収束**する設計とする。
- **FR-011**: harness MUST anchor battery を**独立実装**で提供：`gm_break_even`（逆選択スプレッド）、`kyle_lambda`（price impact）、`budish_sniping_rent`（sniping）、および uniform-price clearing の**独立単体テスト**。これら anchor は engine/metrics を import しない。
- **FR-012**: harness MUST seed を与えれば完全再現、複数 seed 集計をサポート（SE 推定）。
- **FR-013**: harness MUST RL/学習・collusion 測定・inventory 状態・**LVR/pool**・compute grid を**含まない**（スコープ外、明示除外）。

### Key Entities

- **TruePrice**: 外生 GBM(+jump)、連続時間パラメータ(μ,σ,λ,J)＋dt。取引から独立。
- **Quote / Order / Fill**: MM 気配・arbitrageur/noise 注文・約定（逆選択帰属の判定可能）。
- **Agent**: MM（inventory-free・規則・competitive）/ Arbitrageur（反応・学習なし・1体）/ Noise（無方向）。
- **MarketMechanism**: Continuous（価格時間優先）/ Batch（N 期 uniform-price）。
- **Metric**: extraction / effective_spread / participation_margin（+退出判定）/ competitive_spread(GM) / price_impact(Kyle)。
- **Anchor battery**: GM break-even / Kyle λ / Budish sniping rent / uniform-price clearing 単体テスト。許容（tight SE）と収束（dt→0）判定を保持。LVR は**含まない**。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: sim competitive spread が GM break-even の**関数形（σ・alpha 依存）を再現**し、張った範囲（stress 含む）で dt→0 収束 ＋ tight な SE 内一致。
- **SC-002**: sim sniping 抽出量が Budish rent の**スケーリング（σ・N 依存）を再現**、stress 領域含む。
- **SC-003**: N 期 batch の抽出量が連続に比して理論整合的に減少し、差が σ・N で正しい形。
- **SC-004**: 任意 seed で完全再現（同一入力→同一出力）。
- **SC-005**: price impact が Kyle λ に一致し、uniform-price clearing が独立単体テストに合格（impact 層・clearing 層の検証）。
- **SC-006（US3）**: 連続 vs batch で participation/退出判定が**反転する**パラメータ領域を同定（または「反転しない」を範囲付きで結論）。
- **SC-007（B への gate）**: SC-001・SC-002・SC-005 が全て pass（形再現＋収束＋tight consistency）した時点で「実験B を信じる license 成立」と記録。pass しなければ B に進まない。**許容は『緩い方』を取らない**——統計は tight、系統ギャップは収束で分離。

## Assumptions

- **許容誤差**：(i) 統計 consistency は **tight な SE ベース**（seed を増やして縮めた精度をそのまま使う。flat 5% に逃げない＝4% のバグを通さない）。(ii) sim と連続時間アンカーの**系統ギャップ**（離散・有限頻度・fee 等）は flat tolerance に吸わせず、**dt→0 収束チェック**で扱う（単一解像度の「5%以内」はバグと離散化誤差の相殺を許す）。
- **coverage**：点数より**どこを取るか**。σ・N の関連レンジを張り、**高σ・粗dt の stress 領域**を必ず含む。判定基準は点 match でなく**関数形/スケーリングの再現**（バグは形を歪めるので検出力が高い）。
- **arbitrageur = 1 体**：monopolist sniper ＝ **gross/全抽出極限**。Budish の gross sniping rent との照合にこれが正しい選択（恣意ではない）。**sniper 間競争・arms-race 散逸は A の scope 外**——必要なら実験B で arbitrageur 数を見直す。
- **LVR は A から完全除外**：CLOB spine に pool が無く算出不能。CLOB での LP 抽出は sniping/逆選択（GM/Budish）で測る。LVR は後回しの AMM variant feature でのみ再登場。
- **fee/機会コスト**：`f`（taker fee 正 / maker rebate 負）と `c`（機会コスト＝退出閾値）は明示パラメータ。検証は f=0 を含む複数水準。
- **検証は内部整合で十分**：解析モデル相手に任意パラメータで正しさを示せばよく、実在 venue/銘柄アンカーは不要（外部妥当性は実験B＝下流）。
- **C6（文献調査）は並行**：B の novelty 検査、A の spec を変えない。

## Out of Scope *(実験B/下流)*

学習/RL、tacit collusion 測定、competitive benchmark の myopic-Nash 一般化（A では GM break-even で確定）、inventory 拡張（C3-B）、**AMM/LVR 全般**（pool 不在の A では算出不能＝別 feature）、**sniper 間競争/arms-race 散逸**、compute 予算/grid（B1）、外部妥当性アンカー（④）、novelty 主張（C6）。
