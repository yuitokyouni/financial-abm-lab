# Feature Specification: 実験B — 学習 MM collusion harness

**Feature Branch**: `002-exp-b-collusion-harness`（main 上で作業、speckit は .specify/feature.json で追跡）

**Created**: 2026-06-10

**Status**: Draft

**Input**: マイルストーン2 / 実験B。検証済み実験A harness（001、anchor battery 緑、finding 0001 ③ Kyle λ 独立化済み）の上に、quoting MM を tabular Q-learning MM 集団へ差し替え、tacit collusion の創発と市場設計（連続 vs batch、committed vs revisable quote）による変調を測る。一次ソース: `docs/research-design.md` §3/§4/§6、`docs/findings/0001-batch-collusion-crossover.md`、`.specify/memory/constitution.md`。

## Fixed Invariants *(constitution-locked — 冒頭で固定、本 spec 内で変更不可)*

- **中心問題 = 二力対決（finding 0001）**: Green-Porter チャネル（batch の離散・透明・反復が監視/懲罰を容易にし collusion を**促進**）vs arbitrageur-predation チャネル（高 h で batch が collusive spread を accumulated-displacement sniping に**晒す**）。どちらが勝つかを先取りしない（原則III）。**促進/抑制/無影響のどれも publishable な outcome space に最初から含める**（null も成果）。
- **機構選択は design lever の定義そのもの**: **committed-quote**（MM はバッチ内で気配を更新しない＝遅い MM。predation チャネルが生きる）が baseline。**revisable-quote**（純 Budish FBA、clear 直前に再気配＝sniping 消失）は predation の **ablation**＝チャネル分離の識別戦略。
- **markup 分母 = 同一 n 体の myopic/one-shot stage-game Nash**＝arbitrageur 逆選択への GM break-even（A1 knot、001 と同一の結び目）。**独占（単体 MM）spread を分母にしない**。floor 体系: ZI floor ≤ myopic-Nash ≤ 実現 spread。
- **collusion 認定 gate（原則IV・A3×C2）**: deviation+punishment（impulse-response）検査を**通過した点のみ** collusion と認定。memory 閾値等の下流測定は**認定通過点のみ**で行う。markup の高止まりだけでは collusion と呼ばない（探索不足 artifact と区別）。
- **設計マップは両軸 B 世界（C5）**: (抽出, collusion markup) とも学習 MM 世界で測る。実験A は検証アンカーに徹し、frontier のデータ源にしない。
- **頑健性必須（原則IV）**: 単一 run・単一アルゴリズム・単一 seed の主張はしない。
- **honest scope（原則V）**: 外生価格を仮定する以上、価格発見の歪みは scope 外。collusion 創発は memory/学習設定に**条件付き**（memory は sweep 対象であり結果の但し書き）。
- **前提**: 実験A（001）の SC-007 license 成立済み（anchor battery 緑＋③ Kyle λ 独立化閉鎖）。B は検証済み harness の上にのみ立つ（原則I）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 — collusion の創発検出と認定（連続・committed・n=2 baseline） (Priority: P1)

研究者として、連続マッチング上で tabular Q-learning MM n 体（baseline n=2）を収束まで走らせ、(i) 実現 spread の supra-competitive markup を floor 体系（ZI ≤ myopic-Nash ≤ 実現）の上で測り、(ii) impulse-response 検査（強制 1 期逸脱 → 懲罰 → 再確立）で「本物の支持均衡」か「探索不足の高止まり」かを機械判定し、**認定通過点のみ**を collusion と呼びたい。

**Why this priority**: Calvano (2020, Bertrand) の orderbook/MM 版は未開拓＝実験B の存在意義そのもの。認定 gate なしの markup は artifact と区別できない（原則IV）。創発するか・しないかのどちらでも結論が出る MVP。

**Independent Test**: 単一パラメータ点（連続・committed・n=2・固定 memory）で「学習 → 収束判定 → markup 測定 → impulse-response → 認定/棄却」の全パイプラインが回り、null（創発せず）でも探索範囲付きで結論が出る。

**Acceptance Scenarios**:

1. **Given** 収束判定基準（経験的安定）を満たした policy、**When** markup を複数 seed で測る、**Then** markup 点推定±SE と floor 体系の単調性（ZI ≤ myopic-Nash ≤ 実現）が報告される。
2. **Given** markup>0 が有意な点、**When** 強制 1 期逸脱（undercut）を注入、**Then** 懲罰（逸脱後の利得低下）と協調の再確立が検出されれば「認定」、されなければ「高止まり（非認定）」と機械分類される。
3. **Given** n=1（独占）への縮退、**When** 同一学習設定で走らせる、**Then** 実現 spread が monopoly 方向（myopic-Nash 超）へ行く sanity が通る。
4. **Given** memory=0（myopic）への縮退、**When** 走らせる、**Then** 実現 spread が myopic-Nash 近傍に収束する（懲罰を条件づけられない → collusion 不能、の理論整合）。

---

### User Story 2 — 設計レバー効果とチャネル分離（連続 vs batch × committed/revisable） (Priority: P2)

研究者として、同一の学習 MM 集団を連続 vs N 期 uniform-price batch で走らせ、markup の変調（促進/抑制/無影響）を測りたい。さらに committed-quote vs revisable-quote の対比で predation チャネルを ON/OFF し、観測された変調を二力（Green-Porter vs predation）へ**帰属**させたい。

**Why this priority**: 本研究の中心問題。変調の符号だけでなく**機構帰属**（どちらの力がどのレジームで効いたか）が結果の中身。

**Independent Test**: US1 で認定された（または高止まりの）点 1 つで、4 条件 {連続, batch} × {committed, revisable} の markup・抽出・懲罰構造が比較できる。

**Acceptance Scenarios**:

1. **Given** US1 の認定点、**When** batch(N) に切り替える、**Then** markup 差が SE 付きで推定され、促進/抑制/無影響に分類される。
2. **Given** committed で batch、**When** 実現 spread が広い（collusive）、**Then** arbitrageur 抽出が連続比で増えるか（finding 0001 クロスオーバーの emergent 版＝predation の前提条件）が検査され、markup への効果と同時に記録される。
3. **Given** revisable-quote への切替、**When** 抽出 ≈ 0（sniping 消失）を確認、**Then** 残る markup 差は Green-Porter 側へ帰属され、committed との差分が predation の寄与として分離される。
4. **Given** N の sweep、**Then** 変調の N 依存（離散性・透明性の強度）が形として報告される。

---

### User Story 3 — 設計マップと頑健性 grid (Priority: P3)

研究者として、各市場設計を (抽出, collusion markup) 平面（両軸 B 世界）に置いた**設計マップ**を、tiered grid（粗 → 局所密）と事前固定 compute 予算の下で作り、主結果の頑健性（≥2 学習アルゴリズム × 複数 seed × 主要パラメータ）を確認したい。memory 閾値（C2）は認定通過点のみで測る。

**Why this priority**: 地図が本研究の主成果物（trade-off/整合/対立のどれでも情報）。頑健性なしの主張はしない（原則IV）。

**Independent Test**: 粗 grid 1 周で地図の初版が出る。null（どの設計でも collusion 無し）でも地図として publishable。

**Acceptance Scenarios**:

1. **Given** 粗 grid（n × memory × vol(λ,J) × N × fee × seed）、**When** 全セルを回す、**Then** 各設計の (抽出, markup) が SE・認定状態・収束状態付きで地図に配置される。
2. **Given** 変調の符号が変わる近傍（興味領域）、**When** 局所密 grid を張る、**Then** 境界/クロスオーバーが解像される。
3. **Given** 主結果、**When** 第 2 学習アルゴリズム・別 seed 群で再実行、**Then** 方向が一致するか、依存性が明示される。
4. **Given** 認定通過点の集合、**When** memory を sweep、**Then** collusion 維持に必要な最小 memory（C2 閾値）が gate 違反ゼロで測られる。

---

### User Story 4 — 外部妥当性アンカー (Priority: P4)

研究者として、vol・fee・N・flow の少なくとも 1 点を実在 venue/銘柄の公開パラメータに較正した検証ケースを走らせ、合成パラメータの内部結果に外部的含意を与えたい（追加点④）。

**Why this priority**: 内部整合（解析モデル相手）だけでは結果の意味が定まらない（原則V）。ただし主結果の構造（US1–US3）が先。

**Independent Test**: 較正済み 1 点で主比較（連続 vs batch）が走り、地図上の位置が出る。

**Acceptance Scenarios**:

1. **Given** 実在 venue/銘柄から較正した 1 パラメータ点、**When** 主比較を走らせる、**Then** 地図上の位置と主結果の方向が報告される。
2. **Given** 較正値、**Then** 出典と対応（実パラメータ → sim パラメータ）が文書化される。

---

### Edge Cases

- 学習が収束しない/振動する → 「経験的安定」の機械判定基準を持ち、非収束セルは地図上で区別（収束の理論保証はない、原則IV）。
- 複数 MM が同一価格を提示したときの fill 配分（tie-breaking）が決定論的・文書化済みで、主結果が配分規則の選択に頑健か検査する。
- reward が arbitrageur 損で恒常負（参加不能領域）→ 最大 spread への張り付き＝事実上の退出として識別（US3 の地図で「退出」セルを区別）。
- ε 減衰前の探索ノイズを「懲罰」と誤検出しない（impulse-response は収束後にのみ注入）。
- n>2 での非対称均衡（一部のみ collude）→ 集計 markup と個体別 markup の双方を保持。
- batch 内での MM action 更新タイミングと clearing の順序が機構定義（committed/revisable）と厳密に整合（ここが狂うと predation の ON/OFF が無意味になる）。
- 学習中に Q 値が探索不足の状態を「収束」と誤判定する → 収束判定と認定 gate の二段で防御。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: harness MUST 学習 MM 集団 n≥2（設定可能）を提供する。state = 自他の直近 action 履歴（長さ memory、0 を含む sweep 対象）、action = 離散 spread grid（myopic-Nash 近傍から monopoly 超までカバー）、reward = 期 PnL（noise からの spread 捕捉 + fee − arbitrageur 逆選択損。在庫項なし＝C3 初期除外）。
- **FR-002**: 学習 baseline は tabular Q-learning（ε-greedy 減衰・学習率・割引率を明示パラメータ化）。頑健性のため第 2 変種（最低 1 つ）を同一インターフェイスで差し替え可能にする。
- **FR-003**: 市場側は 001 の外生価格・連続/batch エンジンを共有し、**committed-quote**（baseline）と **revisable-quote**（clear 直前に belief 更新後の再気配＝sniping 消失）を機構フラグとして提供する。
- **FR-004**: 競争ベンチマーク＝同一 n の myopic/one-shot stage-game Nash spread を sim と独立に算出する（arbitrageur 逆選択への GM break-even、001 anchor を再利用）。monopoly spread は n=1 sanity 専用とし、markup 分母に使わない。
- **FR-005**: ZI floor（ランダム action 集団の実現 spread）を測定し、floor 体系 ZI ≤ myopic-Nash ≤ 実現 の単調性を検査する。
- **FR-006**: markup = (実現 spread − myopic-Nash) / myopic-Nash を、収束 policy 上・複数 seed・SE 付きで測定する。収束（経験的安定）の判定基準を明示し機械判定する。
- **FR-007**: impulse-response 検査を機械判定で実装する: 収束後に強制 1 期逸脱（undercut）を注入 → 懲罰の有無 → 協調再確立の有無。**認定 = markup 有意 AND 検査通過**。
- **FR-008**: memory 閾値（C2）は認定通過点のみで測定する（gate、原則IV。非認定点の閾値は報告しない）。
- **FR-009**: 設計マップを出力する: 条件 {連続, batch×N} × {committed, revisable} ごとに (抽出, markup, 認定状態, 収束状態) を B 世界で集計する。
- **FR-010**: grid は tiered（粗 → 局所密）。compute 予算（総 run 数または総 step 数）を plan で数値固定し、超過しない（B1）。
- **FR-011**: 外部妥当性アンカー: 実在 venue/銘柄に較正した 1 点以上を grid に含め、出典と対応を文書化する（④）。
- **FR-012**: 決定論: 同一 config（seed 含む）→ 同一結果。複数 seed 集計（SE 推定）をサポートする（001 と同一規律）。
- **FR-013**: harness MUST 次を**含まない**（明示除外）: deep-RL を主結果にすること（robustness 拡張のみ）、inventory リスク（C3 後段）、arb-auction（条件C、scope creep 警戒）、価格発見品質の測定、sniper 間競争（arbitrageur は 1 体・反応的を維持）。

### Key Entities

- **LearningMM**: Q-table、state encoder（自他の action 履歴）、離散 action grid、学習ハイパーパラメータ（ε 減衰・学習率・割引）。
- **MarketEnv**: 001 エンジン + 機構フラグ（連続/batch、committed/revisable）+ 学習ループの期構造（observe → quote → clear → reward）。
- **CollusionVerdict**: markup±SE、impulse-response 結果（懲罰検出・再確立・時定数）、認定フラグ、収束状態。
- **DesignMapPoint**: (設計条件, 抽出, markup, 認定状態, 収束状態, seed 統計)。地図の 1 点。
- **Benchmarks**: myopic-Nash spread（GM break-even, 001 anchor）、ZI floor、monopoly spread（n=1 sanity）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 連続・committed・n=2 で collusion 認定（markup 有意＋impulse-response 通過）される点が同定される、**または**探索範囲を明示して「創発しない」と結論される（null も成果、原則III）。
- **SC-002**: 認定点（または代表点）で batch(N) との markup 差が SE 付きで推定され、全比較セルが促進/抑制/無影響に分類される。
- **SC-003**: revisable-quote で抽出 ≈ 0 を確認した上で、committed との markup 差分により predation 寄与と Green-Porter 寄与が分離して報告される（チャネル帰属）。
- **SC-004**: 設計マップ初版: 最低 {連続, batch×2 水準の N} × {committed, revisable} の 6 条件以上が (抽出, markup) 平面に SE 付きで配置される。
- **SC-005**: 主結果の方向が ≥2 学習アルゴリズム・セルあたり ≥5 seed・粗 grid 横断で再現される、または依存性が明示される。
- **SC-006**: memory 閾値の測定に gate 違反ゼロ（非認定点の閾値を一切報告しない）。
- **SC-007**: 外部アンカー 1 点の結果が出典付きで報告される。
- **SC-008**: sanity 縮退が全て通る: n=1 → monopoly 方向、memory=0 → myopic-Nash 近傍、floor 体系の単調性。

## Assumptions

- **001 再利用**: 外生価格・機構・抽出会計・anchors は 001 をそのまま使う。B で新たに入る市場側要素は revisable-quote フラグと学習ループのみ（検証済み部分を最大化、原則I）。
- **arbitrageur は 1 体・反応的のまま**（gross 抽出極限、A と整合）。学習 MM も sniped される（C5: 両軸同一世界）。
- **「収束」= 経験的安定**（同時学習に理論保証なし、原則IV）。基準の具体値（窓幅・許容変化）は plan で確定。
- **vol レジームは pure-jump (λ, J) で張る**。diffusion σ>0 は A 側残課題 ①（収束検査の本物化）の完了後に robustness 軸として追加（gate は塞がない、finding 0001）。
- **compute 予算の数値・外部アンカーの銘柄選定は plan/research で確定**（B1・④、constitution open knots）。
- **tie-breaking（同価格 quote の fill 配分）は plan で確定し文書化**。主結果の配分規則依存性は edge case 検査対象。
- **committed-quote が baseline である理由**: 速度非対称（遅い MM）の自然な表現であり、001 の 1 期 staleness と連続的に整合。revisable は ablation。

## Out of Scope *(下流・別 feature)*

deep-RL 主結果（robustness 拡張のみ）、inventory リスク（C3 後段 robustness）、arb-auction（条件C）、価格発見の歪み（外生価格の限界、原則V）、sniper 間競争・arms-race 散逸、AMM/LVR 全般、規制提言・実市場への直接主張。
