# Stage S5.7 plan v1 — Survival function S(τ) matched-τ 比較 (KM 推定、post-processing only)

| 項目 | 値 |
|---|---|
| Stage | S5.7 — agent lifetime survival curve S(τ) の matched-window 比較 (4 条件) |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Windows ~10 分 (post-processing のみ、新規 sim ゼロ) |
| 新規 sim | なし (既存 `data/{C0u,C0p,C2,C3}/lifetimes_*.parquet` × 400 のみ使用) |
| 前提 | S5.5 完走済 (`recensor_lifetime_T1500` で matched censoring 既算出)。S6 (A3) より先に実施 |

## 0. 背景と estimand の再定義 (Yuito 指摘 P1 の修正版)

### 0.1 出発点 (Yuito 指摘 P1)

proposal/oral の headline「LOB censoring 81.1% vs agg 0.9%」は T を揃えていない
(agg T=50000 / LOB T=1500、33x)。per-step hazard が同一でも agg は censoring が
下がるので、生比較は microstructure friction と run-length の混成。

### 0.2 前提の訂正 (S5.7 起案時に確認済)

- **S5.5 §3.3 が matched-window 再打ち切りを既に実施**
  (`code/subsample_aggregate.py::recensor_lifetime_T1500`):
  agg を T=1500 で打ち切り直すと censoring 25.4% (C0u) / 22.4% (C0p)、
  LOB 91.0% (C2) / 73.0% (C3)。horizon 攻撃は「未処理」ではなく半分閉じている。
- **P1 の予測「揃えても agg ≈0.9% のまま」は反証済**: 0.9% → 25%。
  予測の根拠だった YH005_1 median=2 / max=484 は **round-trip horizon** であり、
  headline の 81% vs 0.9% は **agent lifetime censoring**。agg lifetime は
  median≈390 / p90≈907 なので T=1500 cap は大きく食い込む。RT と lifetime の
  混同が誤予測の原因 (本 plan で再発防止のため明記)。
- **rt_df (trial_*.parquet) は closed RT のみ**で never-closer を含まないため、
  RT horizon ベースの S(τ) は既存 log から組めない。survival gap の主張は
  agent turnover の話なので、lifetime ベースの S(τ) が正しい対象。

### 0.3 それでも S(τ) 化が正しい理由 (estimand upgrade)

S5.5 の censoring 率は **birth-time composition で汚れた estimand**:
窓の後半に生まれた agent は短い lifetime で必ず censored になるため、
率が birth 分布 (agg=高頻度 substitution / LOB=ほぼ t=0 一斉誕生) に引っ張られる。
matched τ の S(τ) はこの汚染を受けない。

Preview 計算 (pooled lifetimes、naive 推定、2026-06-07):

| τ | C0u (agg, T1500 re-censor) | C0p | C2 (LOB) | C3 (LOB) |
|---:|---:|---:|---:|---:|
| 100 | 87.1% | 79.7% | 96.3% | 80.5% |
| 500 | 27.2% | 22.8% | 91.3% | 73.2% |
| 1000 | 3.6% | 2.8% | 90.7% | 72.8% |
| 1499 | 0.5% | 0.1% | 82.5% | 48.6% |

→ matched τ で gap は **~100x オーダー** (S5.5 の censoring 率比較の 3.6x より
decisive)。「gap は hazard 起源であって run-length 起源ではない」を curve 全体で
示せる。reviewer 攻撃 → robustness 結果への変換に加え、headline の強化。

注意: 上の preview は naive (censored agent を risk set からの除去なしで扱う)。
本実装は Kaplan-Meier (右側打ち切り対応) で行う — 特に agg は birth が窓内に
分散するため、KM の risk-set 処理なしでは S(τ) が下方バイアスする。

## 1. 目的

(a) 4 条件 (C0u/C0p/C2/C3) の agent lifetime survival function S(τ) を
    **matched window T=1500** で KM 推定 (agg は S5.5 §3.3 と同じ re-censor 規約)
(b) trial-level bootstrap で S(τ) の 95% CI band
(c) 補助: cumulative hazard Λ(τ) と per-step hazard の概形比較
    (「hazard 起源」の直接 visualize)
(d) headline 差し替え: 「81.1% vs 0.9%」(raw) を retire し、
    「matched τ=1500 で S(τ): LOB 49–83% vs agg ≤0.5%」に置換
(e) README + S5.7 diff で proposal/oral 用の数字を確定

## 2. 入力

- `data/{C0u,C0p,C2,C3}/lifetimes_{1000..1099}.parquet` (列: agent_id, sample_idx,
  t_birth, t_end, lifetime, censored, cond, seed)
- agg の re-censor 規約は `subsample_aggregate.py::recensor_lifetime_T1500` を流用:
  - `t_birth >= 1500`: drop
  - `t_end <= 1500`: そのまま (元の censored 継承)
  - `t_birth < 1500 < t_end`: lifetime = 1500 − t_birth, censored=True
- LOB は既に T=1500 で censoring 済 → そのまま

## 3. 作業項目 (すべて Windows)

### 3.1 `code/survival_analysis.py` 新規 (~150 行)

1. 4 条件の lifetimes を pool (agg は re-censor 適用)
2. KM 推定: S(τ) を τ ∈ [1, 1500] で算出 (lifelines 依存を避け手実装で可、
   event/censor の risk-set 処理のみ)
3. trial-level bootstrap (trial = seed 単位の resample、n=10,000) で
   τ ∈ {100, 250, 500, 750, 1000, 1250, 1499} の S(τ) 95% CI
4. cumulative hazard Λ(τ) = −log S(τ) も併記
5. 出力:
   - `outputs/tables/tab_S5.7_survival_matched.csv` (4 cond × 7 τ × [S, CI lo/hi, Λ])
   - `outputs/figures/fig_S5.7_survival_curves.png`
     (上段: S(τ) 4 curve + CI band、下段: Λ(τ)、log-y)
   - `logs/S5.7_summary_for_diff.json`
   - `logs/runtime/{ts}_S5.7_survival.log`

### 3.2 整合チェック

- S5.5 の censoring 率 (25.4/22.4/91.0/73.0%) と本計算の入力 n / censored n が
  一致することを assertion (同じ re-censor 規約の検算)
- preview 値 (§0.3 表) と KM 値の乖離を log に明記
  (KM の risk-set 補正で agg がどれだけ上方修正されるか)

### 3.3 README 追記

`## Stage S5.7 — survival function matched-τ 比較` セクション:
- S(τ) 表 + figure
- **headline 差し替えの明記**: raw 81.1% vs 0.9% は horizon 交絡があるため retire、
  以後 matched S(τ) を引用 (proposal/oral 用)
- Limitations: LOB T=1500 での equilibration 未確認 (P3、別 stage) は残る

## 4. 完了条件

- [ ] §3.1 `survival_analysis.py` 実装 + 実行完了
- [ ] §3.2 S5.5 との n / censoring 整合 assertion PASS
- [ ] 表 1 + figure 1 + summary JSON 出力
- [ ] README §S5.7 追記 (headline 差し替え明記)
- [ ] `plans/stage_S5.7_diff.md` 提出 → Yuito レビュー

## 5. Yuito 確認事項

### 実装中の停止トリガー

- §3.2 で S5.5 の censoring 率と再現値が 0.5%pt 以上乖離 (規約の解釈ズレ)
- KM 推定の S(1499) が preview と 10x 以上乖離 (実装バグ疑い)

### 完了後レビュー

1. headline 差し替え (raw → matched S(τ)) の承認
2. τ grid {100,...,1499} で proposal/oral に十分か
3. S5.8 候補 (P2: c_ticks 再較正 + 数 seed 再走 / P3: LOB T=5000–10000 数 seed
   equilibration check — どちらも Mac sim 必要) の優先順位と S6 との並走判断

## 付記 — queue されている関連指摘 (本 stage scope 外)

- **P2 (c_ticks self-consistency)**: c_ticks≈28tick は SG 投入前の C1 mid 揺らぎで
  較正。SG 投入後 price で 1 パス再較正 → 数 seed 再走で censoring 感度を確認。
  「LOB の rare RT は friction か trigger 率低下か」の切り分け。Mac sim 必要。
- **P3 (LOB equilibration / T 依存)**: C2 censoring 91% (p25=1500=境界) は
  「turnover が遅い」と「1500 step で定常未到達」を区別できない。
  T=5000–10000 × 数 seed で censoring が落ちるか高止まりかの方向を見る。
  最低限 Limitations 明記。Mac sim 必要。

## 付記 — scheme-level lessons (P4–P6、YH006_1 完了時に docs/findings.md へ転記)

- **P4 (estimand 選択)**: primary を second-difference (C3−C2)−(C0p−C0u) に置いて
  power をかけたのは順序が逆。LOB rho の seed あたり noise に対し Phase 1 の
  single-seed interaction −0.27 は S/N 不足。single-seed → 5–10 seed で interaction
  の安定性を見てから full 2×2×100 に commit すべきだった
  (YH005_1 の「single-seed は ensemble 確認まで robust 扱い禁止」の自己違反)。
  marginal (world≫wealth) を先に確定し、interaction は refinement として後置が正。
- **P5 (trial allocation)**: agg は trial 間 SD≈0.008 で 100 trial は ~10x 過剰
  (CI 幅 0.01 なら ~10 trial)。LOB は SD≈0.087 (11x) で CI 半減には 400 必要。
  分散が乗る側に厚く振る — S6 以降は「agg 10–20 / LOB に厚く」。
- **P6 (funnel metric 冗長)**: 5 指標は同一構造の operationalization 違い。
  robustness 併記は可、headline は bin_var_slope 1 本に固定。
  「5x」「8.7x」「7.9x」など倍率引用の出所 metric/pairing を材料間で統一する
  (oral で「5倍はどこから」は飛んでくる: 5x = RT10k pooled −0.37 vs LOB
  −0.06〜−0.13 [README S5.5]、8.7x = −0.314/−0.036 [findings.md 系]、要統一)。

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | Yuito 指摘 P1 を起点に起案。ただし前提を 2 点修正: (1) S5.5 §3.3 が matched-window re-censor を既に実施済 (攻撃は半分閉じている)、(2) 「揃えても ≈0.9%」予測は RT horizon と agent lifetime の混同による誤りで、実測 matched censoring は 25.4%/22.4%。その上で S(τ) 化は birth-time composition 汚染を除く estimand upgrade として採用 — preview で matched τ gap は ~100x オーダー、S5.5 の 3.6x framing より decisive。KM 実装 + headline 差し替えを scope とし、P2/P3 は Mac sim 必要のため別 stage 候補、P4–P6 は retrospective lesson として付記。 |
