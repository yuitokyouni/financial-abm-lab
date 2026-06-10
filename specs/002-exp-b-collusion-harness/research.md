# Phase 0 Research — 実験B harness の技術判断

各項目 Decision / Rationale / Alternatives。spec の Fixed Invariants（二力対決・committed=baseline・分母=myopic-Nash・認定 gate・両軸B世界・null）を前提に、plan が持ち越した未確定（収束判定・tie-breaking・B1 予算・④ 銘柄・第2アルゴリズム）を**ここで全て数値まで固定**する。

## D-B1. 学習アルゴリズム = tabular Q-learning（baseline）+ SARSA（第2変種）

- **Decision**: baseline は tabular Q-learning（off-policy・ε-greedy）。原則IV の「複数アルゴリズム」要件は **SARSA**（on-policy）を同一インターフェイス（`Policy` protocol）で実装して満たす。deep-RL 変種は本 feature 外（spec FR-013）。
- **Rationale**: Calvano 2020 と整合（比較可能性・可解釈・デバッグ容易）。SARSA は「探索を含む実際の挙動で更新する」という質的に異なる学習動学を持ち、ハイパーパラメータ違いより強い頑健性検査になる。両者とも表形式＝Q 表を直接 dump して懲罰構造を目視監査できる。
- **Alternatives**: ハイパーパラメータ変種のみ（弱い、「複数アルゴリズム」を名乗れない）／DQN 等（監査不能・収束不安定・予算爆発）→ 却下。

## D-B2. state / action / reward の具体形

- **Decision**:
  - **action**: 離散 half-spread grid `A`、**|A| = 15**、`linspace(0.5·h*_cont, 2.0·J, 15)`（h\*_cont = 連続 GM break-even）。セル内の全機構で**同一 grid**（機構間比較を grid artifact にしない）。grid は h\*_cont 近傍点と J 超え領域（sniping 完全回避域）を必ず含む。
  - **state**: 直近 memory 期の**全員の action index の組**。state 数 = |A|^(n·memory)、memory ∈ {0,1,2}（0 = myopic 縮退、C2 sweep 用）。n=2, memory=1 → 225 状態 × 15 action（Calvano 同規模）。
  - **reward**: 当期の**実現 PnL**（期待値でなく実現値）: `r_i = share_i·[noise fill ごとの (h_w ∓ disp) + fee] − share_i·(sniping 損)`。share は tie-split（D-B8）。在庫項なし（C3 初期除外）。
- **Rationale**: 自他の直近 action が state に入らないと懲罰を条件づけられず collusion が原理的に出ない（research-design §3.5）——memory はこの仮定を露出させる sweep 軸。実現 reward（noise の ∓disp 込み）は 001 の会計（mm_trading_pnl）と同一規約＝C5 同一世界。grid 上限 2J は「sniping を完全に避けつつ最大限広い」spread を含む（D-B11 の ceiling 明示と対）。
- **Alternatives**: 期待 reward（分散は減るが「学習 MM も sniped される」実現リスクを消してしまい C5 違反気味）／連続 action（表形式不能）→ 却下。

## D-B3. 学習期構造と committed / revisable の厳密定義

- **Decision**: **学習 1 期 = 1 clearing サイクル**。
  - **continuous**: 1 期 = 1 step。`observe s_t → 全 MM が h_i を選択 → belief m = v_{t-1}（1期 staleness）で気配 → 価格増分 disp → arb（確率 α、|disp|>h_w なら winner を picking-off）→ noise（確率 p_n、winner で約定）→ reward → belief 更新`。001 の D3（1期 staleness）と同一の順序。
  - **batch(N)**: 1 期 = 1 batch。batch 開始時に action 選択・belief m₀ 固定 → N step の noise 到着を蓄積（stale quote で settle）→ clear 時に arb（確率 α、|v_clear − m₀| > h_w なら 1 回 picking-off）→ uniform clearing → reward → belief 更新。001 の `_run_batch` と同一の市場規約。
  - **committed-quote（baseline）**: 上記のまま（quote は期初の belief で固定＝staleness あり）。
  - **revisable-quote（ablation）**: **clear 直前（arb の手番の前）に belief を v_clear に更新して再気配**。よって arb の利得機会が構造的に消える（抽出 ≡ 0）。noise は依然 h を払う。continuous でも同様（staleness ゼロ化）。
  - **割引 γ は学習期基準**（batch では 1 期 = N·dt の実時間）。機構間で γ の実時間換算が変わることは結果の解釈に明記し、γ を robustness 軸に含める。
- **Rationale**: predation チャネルは「遅い MM の stale quote が batch で accumulated displacement に晒される」こと（finding 0001）——committed がそれを保存し、revisable が外科的に切る。「arb の手番直前の再気配」という定義は sniping 消失を**構造的に**保証する（パラメータ依存でなく恒等的に 0、test で assert 可能）。
- **Alternatives**: revisable = 「batch 内 k 回更新」（中間段階。識別が曖昧になる。将来の精緻化に保留）／学習期 = 固定実時間（batch で action 機会が N 倍細かくなり機構比較が学習頻度比較に汚染される）→ 却下。

## D-B4. markup 分母 = 機構別・離散 stage-game 対称 Nash（解析計算）

- **Decision**: `benchmarks.myopic_nash_spread(grid, primitives, mechanism, N, staleness)` が**その機構の** one-shot stage game の対称純戦略 Nash を返す。期待 stage payoff は閉形式：
  - continuous: `π(h_i; 勝者) = p_n·(h_i + f) − α·q·(J − h_i)⁺`（q = λ·dt, p_n = noise_rate·dt）
  - batch(N): `π(h_i; 勝者) = N·p_n·(h_i + f) − α·E[(|S_N| − h_i)⁺]`（E[·] は 001 `anchors._iter_net_displacement` の binomial 厳密和）
  - revisable: 上式の sniping 項 = 0。
  - 勝者 = min h、tie は等分割（D-B8）。対称 Nash は grid 上の全対称 profile を列挙し「単独逸脱（全 grid 点）で利得が増えない」ことを直接検査して求める（n と grid が小さいので全列挙が厳密）。
- **Rationale**: A1 knot——「同一 n の myopic/one-shot Nash」が分母。離散 grid 上で解析的に解くことで (i) agent が実際に選べる行動空間と同じ空間で分母が定義され、grid 粗さによる見かけ markup を排除、(ii) grid 細分極限で GM break-even h\* に収束（`test_benchmarks` で assert）＝001 anchor への接続が検証可能、(iii) **機構別**に計算することで「batch が競争水準そのものを動かす効果」と「collusion」を分離（分母を間違えると変調と競争シフトを混同する）。`benchmarks.py` は env/qlearn を import しない（分母が学習コードのバグを共有しない、001 anchors と同じ構造担保）。
- **Alternatives**: 連続 h\* をそのまま分母（grid 粗さが markup に混入）／監督下の best-response 学習で数値的に Nash を出す（sim 依存＝独立性喪失）／monopoly 分母（A1 違反・knot 破り）→ 却下。

## D-B5. ZI floor = 解析期待値 + sim 照合

- **Decision**: ZI 集団 = 各期 grid 上の一様ランダム action。floor = E[実現 spread] = E[min(h_1..h_n)]（一様 i.i.d. の最小値、grid 上の厳密和）。`benchmarks.zi_floor` が解析値を返し、ZIPolicy の sim 実測と test で照合。floor 体系 `ZI ≤ myopic-Nash ≤ 実現` の単調性検査に使う。
- **Rationale**: 「メカニズム＋order-flow 制約だけで出る spread」の操作的定義。解析と sim の二重化は battery と同じ規律。
- **Alternatives**: ZI を sim のみで測る（独立検査にならない）→ 却下。

## D-B6. 学習ハイパーと収束判定（経験的安定）

- **Decision**:
  - 学習率 α_lr = 0.15、割引 γ = 0.95、Q 初期値 = 0、ε_t = exp(−β·t)、β = 4.6×10⁻⁶（ε ≈ 0.01 at t = 10⁶ 期）。α_lr・β・γ は robustness 軸（粗 grid では固定、robustness tier で振る）。
  - **収束 = greedy policy（全状態の argmax）が W = 10⁵ 期連続で不変**。上限 T_max = 2×10⁶ 期。到達せず終了 → 「非収束」ラベル（地図上で区別、measurement はするが認定 gate に進めない）。
  - 測定 phase: 収束後 ε = 0・学習停止で K = 10⁴ 期走らせ、実現 spread（期ごとの勝者 h）・抽出・markup を集計。
- **Rationale**: Calvano の収束概念（policy 安定）をそのまま機械判定化。数値は Calvano 規模（収束は典型 ~10⁶ 期以内）に整合し、T_max は D-B9 予算から逆算（1 run ≤ 2×10⁶ 期 ≈ 10 s）。同時学習に理論保証は無い（原則IV）ので「収束」はラベルであって主張ではない。
- **Alternatives**: Q 値ノルム収束（policy が同じでも値が漂う/逆もあり、判定が不安定）／固定 horizon のみ（収束/非収束の区別を失う）→ 却下。

## D-B7. impulse-response gate（認定プロトコル）と分類器自体の検証

- **Decision**: 収束セルのみ対象。**Q 凍結・ε = 0**（学習停止）で：
  1. pre window 100 期で基準 profile（各 MM の greedy action）と基準利得を記録。
  2. 逸脱者 i=0 に **myopic 最良応答**（他者の基準 action 所与で当期 π 最大の action＝最大 undercut とは限らない）を **1 期強制**。
  3. T_ir = 200 期観測。**懲罰検出** = 相手側の action が基準より ≥1 grid step タイト化が逸脱後 ≤10 期以内に発生 **かつ** 逸脱者の T_ir 累積利得 < 非逸脱 counterfactual（逸脱が割に合わない＝支持均衡）。**再確立検出** = 最後の 50 期、全員の action が基準 profile の ±1 grid step 内。
  4. **認定 = [markup 有意] ∧ [懲罰] ∧ [再確立]**。markup 有意 = セル内 ≥5 seed の markup 平均 − 2·SE > **0.05**（5% の経済的 floor。微小 markup を collusion と呼ばない）。
  - **分類器自体を test で固定**（`test_verdict_gate.py`）: (i) 手書き **grim-trigger** policy 組（逸脱を見たら Nash へ永久回帰…ではなく有限懲罰→復帰版）→ PASS すべき。(ii) **固定高止まり**（全員無条件に高 h、逸脱に無反応）→ 懲罰なしで FAIL すべき。(iii) ε>0 の探索ノイズを懲罰と誤検出しないこと（凍結後に注入する設計の検証）。
- **Rationale**: 原則IV の gate（A3×C2）の操作化。閾値（10 期・200 期・±1 step・5%・2SE）は懲罰の典型時定数（数期）と grid 解像度から固定し、headline 点では閾値感度を robustness 報告。**gate の検出力を学習コードと独立に検証する**のが 001 の anchor 独立性と同型の規律——gate が壊れていたら全認定が無意味になるため、ここが B の検証の本丸。
- **Alternatives**: markup のみで認定（探索不足の高止まりと区別不能＝A3 違反）／学習 ON のまま逸脱注入（Q が逸脱で汚染され、測っているものが変わる）→ 却下。

## D-B8. tie-breaking = 決定論的等分割

- **Decision**: 同率最小 h の k 体は noise fill・arb 損・fee を**全て 1/k で等分割**（実現値の分数配分、決定論）。robustness として「期ごと輪番（rotation）」を第2規則に用意し、headline 点で結果不変を確認。
- **Rationale**: 決定論（SC-008/FR-012）と対称性を最簡で満たす。対称 collusion（全員同 h）では tie が定常状態なので、この規則は reward 配分の根幹＝明示と頑健性検査が必須（spec edge case）。
- **Alternatives**: ランダム配分（決定論を seed 経由でしか担保できず監査しにくい）／時間優先固定（非対称を構造化してしまい対称均衡を壊す）→ 却下。

## D-B9. compute 予算（B1）= 総 3×10⁹ 学習期・tier 配分固定

- **Decision**: **本 feature の総予算 = 3×10⁹ 学習期**（runner が累計をカウントし、超過する run を起動拒否）。配分：
  - **Tier-1 coarse ≤ 1×10⁹**: 条件 {cont, batch N=5, batch N=20} × {committed, revisable} = 6 × セル {vol (λ,J) ∈ (5,1),(15,1.5)} × {fee ∈ 0, 0.05·J} × {memory ∈ 1,2} × {n ∈ 2,3} = 16 → 96 条件セル × 5 seed = **480 runs × ≤2×10⁶ 期 ≤ 0.96×10⁹**。
  - **Tier-2 dense ≤ 1×10⁹**: 変調の符号が変わる近傍の局所密 grid（N・vol・fee の細分）。
  - **Tier-3 robustness ≤ 1×10⁹**: SARSA 全 headline 点・α_lr/β/γ 振り・tie 規則第2種・memory 閾値 sweep（認定通過点のみ）・追加 seed（headline ≥20 seed）・impulse-response。
  - 実測 timing（runtime_sec、001 の RunResult に既設）を log し、見積り（5 μs/期）との乖離が ±3× を超えたら予算根拠を research.md に追記して更新する（数値を黙って変えない）。
- **Rationale**: B1（grid 全張り爆発の防止）。3×10⁹ 期 ≈ 4–5 h serial（5 μs/期）＝seed 並列で 1 h 級＝ローカル完結。tier を数値で固定することで「もう少しだけ回す」の漸進的爆発を遮断。
- **Alternatives**: wall-clock 予算（マシン依存で再現不能）／無制限（B1 違反）→ 却下。

## D-B10. 外部妥当性アンカー（④）= BCS ES–SPY を主、TWSE を代替

- **Decision**: 主アンカー = **Budish–Cramton–Shim (2015) の ES–SPY latency-arbitrage 推定**。mapping：jump 強度 λ ← 彼らの arbitrage 機会頻度（件/日）、jump size J ← 機会あたり利得規模（spread 単位に正規化）、fee ← CME/NYSE 公表手数料、batch N ← 同論文の FBA 提案レンジ（0.1–1 s）を dt 換算、noise_rate ← 出来高ベースの非情報 flow 近似。代替/補助 = **台湾証券取引所（TWSE）の定期 call auction（~5 s 間隔、2020-03 に連続化）**——実在の batch venue として N の現実値とスプレッド比較の自然実験文献を提供。**数値の正確な抽出は US4 実行時に原典から行う**（P4。ここで固定するのは venue 選定と mapping 手順）。C6 文献調査と並走。
- **Rationale**: BCS は本研究の sniping アンカー（Budish rent）と同一の現象・同一マーケットの推定＝内部 anchor と外部 anchor が同じ理論系に乗り、較正の整合性検査になる。TWSE は「batch が現実に走っていた」venue として N の外部値を与える。
- **Alternatives**: crypto venue（Binance 等。データは取りやすいが latency-arb の公表推定が弱く、fee/flow の対応が曖昧）／合成のみ（④ 違反）→ 却下。

## D-B11. noise 需要 = inelastic を baseline、弾力 R は robustness 軸

- **Decision**: baseline は 001 と同一の **inelastic noise**（spread によらず約定）。帰結を明示する：**stage game の monopoly／collusive ceiling は action grid 上限（2J）で外生的に決まる**（π が h で単調増のため内点最大が無い）。よって markup の「水準」は grid 範囲の関数であり、解釈は (i) 認定 gate 通過の有無、(ii) 条件間の markup **差**（同一 grid 内比較）に限定する。robustness 軸として **留保 spread R**（noise が h ≤ r, r~U(0,R) でのみ約定＝線形需要）を LearnConfig に用意し、内点 monopoly が立つ世界で headline 点の方向不変を確認する。
- **Rationale**: 001 の検証済み世界からの逸脱を最小化（原則I）。Calvano の logit 需要は内点 benchmark のためであり collusion の成立条件ではない——本研究の主張は「水準」でなく「設計による変調の方向と機構帰属」なので inelastic でも問いは成立する。ただし ceiling の grid 依存は誇張リスクなので Constitution V（honest scope）として明記。
- **Alternatives**: 最初から弾力需要（GM break-even・Budish rent・myopic-Nash の全式が変わり、001 anchors との接続を失う。R→∞ 極限で戻ることは確認済みの設計だが、battery 再検証が必要＝B と同時にやらない）→ robustness へ繰り延べ。

## D-B12. 決定論 = master seed → spawn 子ストリーム

- **Decision**: `default_rng(seed).spawn(k)` で {price, arb 到着, noise 到着/方向, 各 MM の探索} に独立ストリームを配る。同一 LearnConfig（seed 込み）→ bit 同一の Q 表・指標（FR-012）。test で assert。
- **Rationale**: 001 D7 の延長。探索と環境の乱数を分離すると「同一環境・別探索」の controlled 比較も可能になる（IR の counterfactual 計算に使用）。
- **Alternatives**: 単一ストリーム共有（agent 数変更で全乱数が崩れ、n sweep の比較が seed 違いに汚染される）→ 却下。

## 残 NEEDS CLARIFICATION

- なし（全項目 Decision 済み。spec が plan に持ち越した5点——収束判定・tie-breaking・B1 数値・④ 銘柄・第2アルゴリズム——は D-B6/D-B8/D-B9/D-B10/D-B1 で確定）。
