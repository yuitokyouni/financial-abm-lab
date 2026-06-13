# YH006–YH006_1 研究 Dossier — 研究計画書素材

**目的**: YH006 (Phase 1) → YH006_1 (Phase 2 S1–S5.8、S6 進行中) の全経緯・確定数値・
方法論 protocol・残存課題を研究計画書 / proposal / oral 用に一元化する。
個々の stage の一次ソースは `experiments/YH006_1/README.md` と `plans/stage_*_{plan,diff}.md`。
本書は 2026-06-07 時点 (S5.8 完了、S6 Windows 実装済・Mac 実行待ち) のスナップショット。

---

## 1. 研究課題

**「現実的な注文板 (LOB) を介した取引は、Speculation Game の資産駆動型の市場機構を
どう変質させるか」**

Katahira-Chen (2019) の Speculation Game (SG) は「口座残高 → 注文サイズ」の連動
(q = ⌊w/B⌋) を持つ minimal な投機市場モデルで、aggregate な価格形成
(注文を集計して即時に価格へ反映) を仮定する。本研究はこの SG を
PAMS (Platform for Artificial Market Simulations) の連続ダブルオークション LOB に
移植し、**約定摩擦の存在が SG の創発構造 — 特にファネル構造 (長期取引ほど損益分散が
広がる構造) — に与える影響**を、条件統制された 2×2 (市場機構 × 初期資産分布) +
ablation の実験系で測定する。

**研究の核になった発見の連鎖** (時系列):
1. **F1** (Phase 1): LOB 化すると初期資産格差 (Pareto) がファネルを大幅減衰させる —
   aggregate では起きない交互作用が単一 seed で観察された
2. **F1 interaction は ensemble で null と確定** (Phase 2 S3): 単一 seed の −0.27 は
   LOB の seed 間分散による noise。一方 **marginal な世界効果 (LOB ≪ agg の funnel)**
   は razor-sharp に確定
3. **本物の発見は survival gap**: LOB では agent の退場 hazard が初期 shake-out 後に
   完全凍結する (aggregate は一定 hazard で cohort 絶滅)。初期資産分布が refresh
   されずに persist する — この「凍結」が funnel 減衰の機構候補 (仮説 A revised)
4. 凍結は**定常** (S5.8: T=10000 延長で退場 event 0 件) — 有限 T artifact ではない

---

## 2. 対象モデルと移植設計

### 2.1 Speculation Game (Katahira-Chen 2019) の要点

- N=100 agent、各 agent は S=2 の戦略表 (5^M state → {buy, sell, hold})、M=5
- 戦略は仮想損益 G で淘汰 (virtual round-trip で非 active 戦略も毎 step 評価)
- **資産連動**: 注文量 q = ⌊w/B⌋ (B=9)。round-trip close で w += ΔG × q
- w < B で bankruptcy → 戦略・資産を再 draw して交代 (substitute)
- ファネル構造: round-trip horizon が長いほど ΔG の分散が広い。Katahira らは
  これを資産不平等 (大口 agent の長期取引) の帰結と解釈
- 標準時間長 T=50,000

### 2.2 LOB 移植 (YH006 Phase 1) の主要設計判断

| 設計判断 | 内容 | 理由 / 帰結 |
|---|---|---|
| **設計 A'** | open/close は MARKET_ORDER + 次 step self-cancel + opposing-liquidity guard | 反対板 dry 時の cancel→resubmit 累積で book が爆発し O(N²) (T² scaling) になる経路を probe で特定して遮断 |
| **2-account wealth** | SG cognitive wealth (sg_wealth) と PAMS LOB cash を分離 | sizing と bankruptcy 判定は sg_wealth のみ。LOB cash が deep negative でも SG ロジック不変。final_wealth は YH005 と直接比較可能 |
| **流動性供給** | MMFCN agent × 30 (orderVolume 30、ttl = timeWindowSize ∈ [100,200]) | fundamental 弱・chart ほぼ無効の liquidity 特化層。ttl が定数なので T 不変 (S5.8 で T=10000 でも book 堆積なしを実証) |
| **認知閾値 c_ticks** | SG の価格認知を tick 単位に変換、SG 投入前の C1 mid 揺らぎで較正 (=28 tick) | **既知の弱点**: SG 投入後の volatility regime に対して self-consistent でない (P2、未処理 — §9) |
| **時間長** | LOB main = 1,500 step (Katahira 標準 50,000 の 1/33) | sim コスト制約。この timescale 留保は S5.8 で「測定済み result」に格上げ (§5.4) |
| **stale-fill recovery** | pending なし & position=0 & asset_volumes≠0 で flatten 注文 | warmup→main 境界・substitute 後 re-init 境界の遅延約定が entry_quantity を倍化するバグの恒久対策 (S4 で発見・修正) |

### 2.3 実験条件 (Phase 2 で確定した命名)

| cond | world | wealth init | 備考 |
|---|---|---|---|
| C0u / C0p | aggregate (T=50,000) | uniform / Pareto α=1.5 | YH005 実装の再走 baseline |
| C2 / C3 | LOB (T=1,500) | uniform / Pareto α=1.5 | Phase 1 主実験の ensemble 化 |
| C2_A1 / C3_A1 | LOB | uniform / Pareto | **A1 ablation**: q = q_const 固定 (資産→注文サイズ経路の遮断) |
| C3_A3 | LOB | Pareto | **A3 ablation**: 在籍 τ_max=121 step で強制交代 (lifetime cap、S6) |

A2 は存在しない (ablation は A1/A3 の 2 種のみ)。全条件 100 trial (seed 1000–1099)。

---

## 3. Phase 1 (YH006) の成果と限界

- SG の LOB 上動作を確立 (上記設計 A')。aggregate parity test で YH005 実装との
  数値一致を保証
- **F1 初観察**: 単一 seed の 2×2 で「LOB × Pareto 初期格差 → ファネル大幅減衰」
  (bin_var_slope の interaction ≈ −0.27)
- 限界: 単一 seed。YH005_1 で自ら定めた「single-seed は ensemble 確認まで robust
  扱い禁止」に照らし、Phase 2 で 100 trial ensemble 化することにした
  (→ ただし設計順序に問題があった。§7 P4)

---

## 4. Phase 2 (YH006_1) stage 経緯と確定数値

### 4.1 Stage 一覧

| Stage | 内容 | Verdict / 主数値 |
|---|---|---|
| S1 | Phase 1 データ多指標再分析 | 指標セット確定 (5 主指標) |
| S2 | aggregate 100 trial ensemble | C0u/C0p 確定。agg は over-powered と後に判明 (§7 P5) |
| S3 | LOB 100 trial + 4 条件 interaction | **F1 interaction ≈ 0 (CI が 0 跨ぎ)**。marginal world effect は razor-sharp。survival gap (raw censoring 81.1% vs 0.9%) が浮上 |
| S4 | A1 較正 (q_const) + 後方互換 hook | q 固定の wiring 確立。stale-fill バグ発見・修正 |
| S5 | A1 ablation 100 trial × 2 cond | **仮説 A 単純版 反証**: C2_A1 は C0u 側へ大きくシフト (−0.31) するが C3_A1 は C3 のまま (−0.09)。q を切っても LOB Pareto の funnel 構造は動かない → **仮説 A revised** (wealth persistence dominant) |
| S5.5 | aggregate sub-sample 再分析 | **H_micro 強支持**: RT10k (sample size を LOB の 2.2x に揃え) でも agg pooled bin_var −0.37 を保持、LOB (−0.06〜−0.13) との gap は sample disparity で説明不能 |
| S5.6 | MMFCN orderVolume sensitivity scan | **H_artifact_negated_strong**: 弾力性 ε(4x)=0.254 ≤ 0.3、MMFCN は副次的供給源。約定 starve artifact 説を棄却 |
| S5.7 | KM survival S(τ) matched-τ 比較 (post-processing) | **survival gap は hazard 起源**。raw 81.1% vs 0.9% を retire、matched τ=1499 で S(τ): LOB 73–91% vs agg 1.3–1.8% (**52x/58x**)。hazard 構造: agg = ramp→steady 3.0–3.2e-3、LOB = 即時 shake-out→凍結 |
| S5.8 | LOB T=10000 延長 (equilibration check) | **H_frozen 確定**: 延長 8500 step で退場 event **0 件** / 5.09M agent-steps、h 95% UB = 5.9e-7 (pre-registered 閾値 2e-5 の 1/34)。agg は cohort 絶滅 (max lifetime 5748)。Layer-2-timescale 留保が消えた |
| S6 | A3 ablation (進行中) | Windows 実装完了 (hook + subclass + τ_max=121 較正 + parity 27 件 PASS)。Mac 100 trial 待ち |

### 4.2 Funnel 指標の確定値 (pooled bin_var_slope、主指標)

| 条件 | pooled bin_var_slope | 解釈 |
|---|---:|---|
| C0u | −0.4036 | agg uniform baseline (深い funnel) |
| C0p | −0.2879 | agg Pareto baseline |
| C2 | −0.0593 | LOB uniform (funnel ほぼ消失) |
| C3 | −0.1264 | LOB Pareto |
| C2_A1 | −0.3071 | **q 固定で agg 水準へ復帰** — uniform では q 経路が支配的 |
| C3_A1 | −0.0901 | **q 固定でも動かず** — Pareto LOB は別経路 (→ 仮説 A revised) |

- 倍率引用の規約: 「5x」= RT10k pooled agg −0.37 vs LOB −0.06〜−0.13 (S5.5)。
  出所 metric/pairing を材料間で統一すること (§7 P6)
- 5 主指標 (rho_pearson / rho_spearman / tau_kendall / bin_var_slope /
  q90_q10_slope_diff) は同一構造の operationalization 違い。**headline は
  bin_var_slope 1 本**、他は robustness 併記

### 4.3 Survival 構造の確定値 (agent lifetime、S5.7/S5.8)

**対象物ラベル規約 (必須)**: agent lifetime (birth→退場、agg median ≈ 390) と
RT horizon (open→close、agg median = 2) は別対象。数字には必ずラベルを付ける。
両者の取り違えが研究内で 3 回発生しており (P1 起案 / review / cross-check)、
oral でも必ず起きる。RT 定義は YH005_1 と完全一致 (median=2、0.209 rt/agent/step)
— cross-experiment drift はない (S5.7 diff §6.1 で検算済)。

| 量 | C0u | C0p | C2 | C3 |
|---|---:|---:|---:|---:|
| matched S(1499) [KM、T=1500 窓] | 1.75% | 1.27% | 91.0% | 73.0% |
| hazard 構造 | ramp (0.8e-3→) steady 3.0e-3 | 同左 3.2e-3 | 即時低 (~4e-4) → 0 | 即時高 (2.2e-3) → 0 |
| S(9999) [T=10000 窓、S5.8] | (cohort 絶滅へ) | 同左 | 91.2% | 72.1% |
| 延長区間 [1500,9999] event | — | — | **0 件** | **0 件** |

- **Katahira スケール (T=50,000) の最終形**: agg は cohort 絶滅 (一定 hazard
  2.7–3.0e-3、max/min ≤ 1.11x で外挿妥当、uncensored max lifetime 5748)。
  LOB は 95% UB hazard で外挿しても **≥ 89% (C2) / 70% (C3) 残存**。
  報告形は「**LOB 残存 vs agg 絶滅**」 — 比は agg≈0 で定義不能のため出さない
- 52x/58x は「**matched 窓末 τ=1499 の survival ratio**」ラベル + curve 添付限定。
  ratio は τ 単調増加 (τ=250 で ~1.9x) なので τ ラベルなしは endpoint cherry-pick
  に見える
- 採用 figure: `fig_S5.7_survival_curves.png` (matched 窓 KM + Λ)、
  `fig_S5.8_survival_extension.png` (agg 絶滅直線 vs LOB 完全水平 — 1 枚で
  hazard 起源を主張できる proposal 級)

---

## 5. 現時点の機構像 (科学的結論のドラフト)

### 5.1 確定済み

1. **LOB 化は funnel を桁で浅くする** (marginal world effect)。sample size でも
   (S5.5)、MMFCN 約定設定でも (S5.6) 説明できない microstructure 真効果
2. **F1 (world × wealth interaction) は ensemble で null** — Phase 1 の単一 seed
   観察は LOB の seed 間分散による noise (真に null であって underpowered ではない:
   agg 側 CI 幅 0.003 の精度で 0 を跨ぐ)
3. **LOB は agent turnover を凍結する**: 初期 shake-out (C3 では Pareto 下位 tail の
   flush、[0,100] hazard 2.2e-3) の後、hazard は検出限界以下 (≤ 5.9e-7/step) に落ち、
   T=10000 まで 1 件も退場しない。aggregate は ramp 後 一定 hazard ~3e-3 で
   cohort 絶滅まで回り続ける
4. **仮説 A 単純版 (q 経路) は反証**: q 固定 (A1) で uniform LOB は agg 水準へ
   戻るが、Pareto LOB は動かない

### 5.2 検証中 (S6)

**仮説 A revised**: 「Pareto LOB では agent が凍結して初期 Pareto wealth
distribution が refresh されずに persist し、その wealth-tail structure が funnel
減衰の dominant 因子」。S6 (A3: τ_max=121 で強制交代 = 凍結の人為的解除) が
direct causal test。判定は **funnel 復元のみ** (C3_A3 pooled bin_var が
C0u/C2_A1 側 ≈ −0.31〜−0.40 へシフトすれば確定、C3 のまま ≈ −0.13 なら fail)。
lifetime 分布の変化は manipulation check でありトートロジー (成功条件にしない)。

### 5.3 解釈上の注意 (examiner 対策)

- τ_max (121) と shake-out 帯 ([0,250]) の重なりは「同じ C3 lifetime 分布の下位
  tail 特徴量どうし」で construction 上の相関 — 独立な機構の alignment として
  売らない
- C3 の初期 shake-out は「LOB でも退場 dynamics は最初の ~100 step は生きている」
  ことを示す — 凍結は「取引が成立しない」ことの帰結であって、agent が退場
  しない規則を入れたわけではない (friction-induced)
- 凍結の機械的経路: 約定が rare → sg_wealth が動かない → bankruptcy 判定
  (w < B) に到達しない。fill/matching 律速 (S5.6 で MMFCN 供給は余裕と確認済) —
  ただし c_ticks の self-consistency (P2) が trigger 率に効く可能性は未排除 (§9)

### 5.4 Layer-2-timescale 留保の格上げ

「LOB T=1500 は Katahira T=50000 の 1/33」という留保は S5.8 により hand-wave
から測定済み result になった: T を 6.7x 延長しても凍結は 1 event も解けない。
凍結は定常であり有限窓 artifact ではない (pre-registered 閾値で確定、dead zone
に掠りもしない)。

---

## 6. Headline 規約 (proposal / oral 用言語)

1. **Retire 済み**: 「LOB censoring 81.1% vs agg 0.9%」(horizon 交絡、33x の T 差)
2. **主 headline** (hazard 構造、τ 不変):
   > aggregate の agent 退場 hazard は早期 ramp 後 ~3×10⁻³/step で安定し続け、
   > cohort は T=50000 で絶滅する。LOB は τ≲250 の初期 shake-out 後に hazard が
   > 検出限界以下 (≤6×10⁻⁷) へ凍結し、population の 72–91% が残存し続ける。
3. 補助数値: matched τ=1499 survival ratio 52x (uniform、lead) / 58x (Pareto、併記)。
   curve 添付必須、τ ラベル必須
4. funnel は bin_var_slope 1 本で張る。「LOB で 5x 浅い」(RT10k pairing)
5. 全数字に対象物ラベル (agent lifetime / RT horizon)。両 median (390 vs 2) は
   並べて先出しすれば矛盾に見えない

---

## 7. 方法論 protocol と scheme-level lessons

### 7.1 再現性の柱 (全 stage 共通で運用、研究計画書の「方法」節に転用可)

- **plan → 承認 → 実行 → diff**: 各 stage は `stage_*_plan.md` (Draft、stop
  trigger と完了条件を事前定義) → Yuito 承認 → 実行 → `stage_*_diff.md` で報告
- **determinism guard**: 新しい sim 経路は seed 固定 2 回独立 run の
  bit/semantic 一致を確認してから ensemble に入る
- **Phase 1 後方互換 protocol**: Phase 1 code への変更は「default で既存挙動と
  bit-一致する hook 追加」のみ許容。subclass で override (monkey patch 禁止)。
  毎回 parity test 全再走 + archived data との等価チェック (LOB 側は aggregate
  parity では検証できないため、archived trial との semantic 一致を別途確認)
- **fail-fast の前倒し**: 高コスト run の前提検証 (S3 等価チェック等) は run の
  前に置く (S5.8 P1 で確立)
- **pre-registration**: 判定閾値と dead zone の処理は数字を見る前に plan に焼く
  (S5.8 P2)。閾値は便宜的な絶対値でなく、主張が依存するスケール (Katahira
  T=50000 での gap 生存) に anchor する
- **matched estimand**: 条件間比較は window / sample size / birth-composition を
  揃えた estimand で行う (raw censoring 比較 → matched KM S(τ) への置換が典型例)

### 7.2 Scheme-level lessons (P4–P6、findings.md へ YH006_1 完了時に転記)

- **P4 (estimand 順序)**: second-difference (interaction) を primary に置いて
  full 2×2×100 に commit したのは順序が逆。分散が最大の条件 (LOB) の single-seed
  値で S/N を見積もらず投資した。正: marginal を先に確定し、interaction の
  seed 安定性を 5–10 seed で見てから refinement として後置
- **P5 (trial allocation)**: agg は trial 間 SD≈0.008 で 100 trial は ~10x 過剰、
  LOB は SD≈0.087 で CI 半減に 400 必要。分散が乗る側に厚く配分する
  (以後の scaling は「agg 10–20 / LOB に厚く」)
- **P6 (metric 冗長)**: 同一構造の operationalization を 5 本並べて interaction
  表にすると「CI 0 跨ぎセル多数」で null が歯切れ悪く見える。headline 1 本 +
  robustness 併記。倍率引用の出所を統一
- **対象物ラベル強制** (P1 系): カテゴリエラー (lifetime vs RT duration) は
  研究者本人にも繰り返し起きる。図表・本文の全数字にラベルを付ける規約で塞ぐ

### 7.3 無駄でなかった投資 (正直な収支)

- 100 trial で marginal が razor-sharp に出て interaction が「真に null」
  (underpowered ではない) と確定できた
- pareto arm のデータは wealth-persistence 証拠 (survival 構造) に転用できた
- adapter / ensemble / parallel infra は S4–S6 まで全 stage で再利用
- N を揃えない α 比較の error を publish 前に 1 個潰した (−0.56 → −1.93 補正)

---

## 8. 進行状況と次の手 (2026-06-07 時点)

| 項目 | 状態 |
|---|---|
| **S6 (A3 ablation)** | gate (S5.8 H_frozen) 通過。Windows 実装完了 (hook + LifetimeCapSpeculationAgent + τ_max=121 + parity 27 件 PASS)。**次: Mac で C3 等価チェック → A3 smoke → determinism → 100 trial (~2-3h 想定、agent 入れ替え overhead で S3 の 1.5-2x)** → Windows 集計 + L3 判定 |
| S7 (Phase 2 完了 + proposal 素材) | S6 完了後、別 plan |
| S5.9 候補 (P2: c_ticks self-consistency) | 後置確定。SG 投入後 price で 1 パス再較正 → 数 seed 再走で trigger 率 robustness を確認。gap の解釈に効くが大きさには効かない (censoring は fill/matching 律速) |
| S1-secondary | 保留 (4 条件 bootstrap CI 再確定、優先度は Yuito 判断) |
| YH006_2 | LIMIT 注文拡張 + 論文 Fig.11/12/13 のフル再現 (将来) |

### S6 の判定設計 (再掲、pre-registered)

- **仮説 A revised 確定**: C3_A3 pooled bin_var が −0.31〜−0.40 (C2_A1/C0u 側) へ
- **fail**: C3 のまま (≈ −0.13) → 別 mechanism 探索 (S7 で static wealth
  distribution effect 等を検討)
- KPI L3: 5 主指標の shrinkage ratio ≤ 0.7 + CI 0 非跨ぎ、PASS 件数を報告
- 中間予測 (forced_retire_rate↑ 等) は manipulation check (成功条件ではない)

---

## 9. Limitations / 残存 threat (研究計画書の Limitations 節素材)

1. **c_ticks self-consistency (P2、最大の残存 live issue)**: 認知閾値は SG 投入前の
   価格揺らぎで較正されており、SG 投入後 regime に対する再較正をしていない。
   trigger 率 (= RT が rare な理由の一部) に効く可能性。S5.9 で 1 パス再較正 +
   数 seed 感度確認を計画
2. **MMFCN scan の範囲**: orderVolume 1 パラメタ × 4 設定 × 2 seed。numAgents や
   timeWindowSize の sensitivity は未走査 (ε ベース判定で副次性は強く支持済みだが
   全数走査ではない)
3. **LOB run 長**: 主系列は T=1500 (S5.8 で凍結の定常性は T=10000 まで実証済。
   funnel 指標自体の T 依存は未測定 — RT が rare なため T 延長で n_rt は増えるが
   S5.8 の 12 trial では bin_var 再計算に足る規模でない)
4. **単一市場・単一資産**、MMFCN 30 体の specific な流動性生態系。一般化可能性は
   YH006_2 (LIMIT 拡張) 以降の課題
5. **wealth 2-account 設計**は Phase 1 固有の決定 (SG cognitive wealth と LOB cash
   の分離)。LOB cash を sizing に使う変種は別物の model になる
6. interaction の null は「この N / この T / この 4 条件」での null。より強い
   friction regime や別の wealth 分布での交互作用は未探索

---

## 10. 関連 YH との接続

- **YH005 / YH005_1**: SG aggregate 実装と 3 層機構の実証。round-trip 統計
  (median=2 / 0.21 rt/agent/step) は YH006_1 と完全一致 — 実装系譜の整合検算済
- **YH006_2** (計画): LOB での論文フル再現 (LIMIT 注文 + Fig.11/12/13)
- **YH007** (構想): 認知閾値の自己組織化 — P2 (c_ticks self-consistency) の
  根本解決はこの系譜に接続する
- **YH008** (並行): 別系列 (loss-conditional ATH)。本 dossier の scope 外

---

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-06-07 | 初版。S5.8 完了 / S6 Windows 実装済の時点で作成。S6 結果確定後に §5.2/§8 を更新すること。 |
