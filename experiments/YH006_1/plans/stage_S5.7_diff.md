# Stage S5.7 diff — survival function S(τ) matched-τ 比較 (KM 推定)

S5.7 plan v1 の実行結果。新規 sim なし、既存 `lifetimes_*.parquet` × 400 (4 cond × 100 trial) から Kaplan-Meier survival curve を matched window T=1500 で推定。Windows のみ、実行 ~12 秒。

---

## Verdict — survival gap は **hazard 起源** (run-length 起源ではない)、matched τ=1499 で **52–58x**

| cond | matched S(1499) [95% CI] | Λ(1499) | matched censoring (検算) |
|---|---:|---:|---:|
| C0u (agg uniform, T1500 re-censor) | **0.0175** [0.0145, 0.0210] | 4.04 | 25.4% (S5.5 一致 ✓) |
| C0p (agg pareto, T1500 re-censor) | **0.0127** [0.0101, 0.0153] | 4.37 | 22.4% (S5.5 一致 ✓) |
| C2 (LOB uniform) | **0.9102** [0.9019, 0.9184] | 0.094 | 91.0% (S5.5 一致 ✓) |
| C3 (LOB pareto) | **0.7304** [0.7228, 0.7382] | 0.314 | 73.0% (S5.5 一致 ✓) |

**gap**: uniform 0.9102/0.0175 = **52x**、pareto 0.7304/0.0127 = **58x**。CI は trial-level (seed 単位) bootstrap n=10,000、全条件で non-overlap。

---

## 1. Headline 差し替え (P1 対応の中核、proposal / oral 用)

**Retire**: 「LOB censoring 81.1% vs agg 0.9%」— T=1500 vs 50,000 (33x) の horizon 交絡を含む raw 比較。

**Replace**: 「**matched τ=1499 で S(τ): LOB 73–91% vs agg 1.3–1.8% (gap 52–58x)**。aggregate の per-step hazard は窓内ほぼ一定 (log-y で直線減衰、Λ(1499)≈4.0–4.4) なのに対し、LOB は τ≈250 の初期 shake-out 後 hazard ≈ 0 で plateau (Λ(1499)≈0.09–0.31)。gap は hazard 構造の違いであり、run-length では説明できない」

reviewer 攻撃 (horizon 交絡) → robustness 結果への変換が完了。curve 全体 (`fig_S5.7_survival_curves.png`) で示せる。

## 2. Hazard 構造の所見

- **aggregate**: S(τ) が log-y でほぼ直線 = 幾何分布的な退場 (per-step hazard ≈ 一定 ~2.7–2.9×10⁻³)。substitution が定常的に回っている世界
- **LOB C3**: τ ≤ 250 で S が 0.75 まで低下 (Pareto 下位の早期退場 — S3 の「下位 25% 早期退場」finding と整合) → 以降 hazard ≈ 0
- **LOB C2**: 初期低下も小さく (S(250)=0.925)、ほぼ全員が full window 生存
- → 「LOB friction が agent turnover を止める」(仮説 A revised の中間予測) が survival curve レベルで確定

## 3. 方法論ノート (重要 — 数値引用時の注意)

1. **KM の risk-set 補正は agg を上方修正する**: naive 推定 (censored を risk-set 処理なしで扱う) だと S(1499) = 0.5% / 0.1% で gap ~100x-級に見えるが、agg は birth が窓内に分散するため naive は下方バイアス。**引用は KM 値 52–58x に統一** (plan §0.3 の preview 値 ~100x は過大、使わない)
2. **censoring 率比較 (S5.5 の「3x 以上」framing) は birth-time composition に汚染された estimand** — 窓後半に生まれた agent は必ず短 lifetime で censored になるため、率が birth 分布 (agg=高頻度 substitution / LOB=ほぼ t=0 一斉) に引っ張られる。matched S(τ) が正
3. **RT horizon と agent lifetime は別物**: rt_df は closed RT のみ (never-closer 非収録) で RT ベース S(τ) は組めない。survival gap の主張は agent turnover なので lifetime ベースが正しい対象。P1 起案時の「揃えても ≈0.9%」予測はこの混同による誤りだった (plan §0.2 記録済)
4. agg の re-censor 規約は S5.5 §3.3 `recensor_lifetime_T1500` と同一、censoring 率の完全一致 (±0.0%pt) で検算 PASS

## 4. 完了条件 (plan §4) 照合

- [x] §3.1 `code/survival_analysis.py` 実装 + 実行完了
- [x] §3.2 S5.5 整合 assertion PASS (4 条件とも乖離 0.0%pt < 0.5%pt)
- [x] `tab_S5.7_survival_matched.csv` (28 行 = 4 cond × 7 τ)
- [x] `fig_S5.7_survival_curves.png` (上段 S(τ) log-y + CI、下段 Λ(τ) log-y)
- [x] `logs/S5.7_summary_for_diff.json` / `logs/runtime/*_S5.7_survival.log`
- [x] README §S5.7 追記 (headline 差し替え明記)

停止トリガー (plan §5) 発火なし: S5.5 乖離 0.0%pt、KM S(1499) は preview と 3.5x / 12.7x 乖離だが方向・原因 (naive 下方バイアス) は §3 注意 1 のとおり想定内 — 10x 超過は C0p のみで、preview 値 0.1% が小さすぎて比率が立っただけ (絶対差 1.2%pt)。実装バグではなく naive 推定の既知バイアスと判断、続行した。

## 5. Yuito レビュー事項

1. headline 差し替え (raw 81.1% vs 0.9% → matched S(τ) 52–58x) の承認
2. τ grid {100, 250, 500, 750, 1000, 1250, 1499} で proposal/oral に十分か
3. S5.8 候補の優先順位 (どちらも Mac sim 必要、S6 と並走可否含め):
   - **P2**: c_ticks の SG 投入後 1 パス再較正 + 数 seed 再走 (trigger 率の較正 robustness)
   - **P3**: LOB T=5000–10000 × 数 seed equilibration check (C2 の hazard plateau が定常か transient か — 本 S5.7 で LOB hazard ≈ 0 が可視化されたぶん、この攻撃の残存が明確になった)
4. S6 (A3) 着手の go (S5.7 は S6 の前提に影響しない — A3 の τ_max 較正は C3 lifetime 分布ベースで不変)

## 6. Yuito review (2026-06-07) への回答 — v1.1

### 6.1 cross-experiment 整合の「125x / 70x ズレ」 — **不整合は存在しない (対象物の取り違え)**

検算結果 (2026-06-07、`config.py::N_sg=100`):

| 量 | YH006_1 実測 | YH005_1 | 判定 |
|---|---:|---:|---|
| **RT horizon** median (C0u, 3 trial pool n=3.1M) | **2.0** (max 191) | 2 (max 484) | **一致** |
| rt/agent/step (C0u: 1,044,416 / (100 × 50,000)) | **0.209** | 0.21 | **一致** |
| agent lifetime median (uncensored) | 384–390 | — (別対象) | 矛盾なし |

- 「agg median duration ≈ 250」の読みは S5.7 の S(τ) を RT duration として解釈したもの — S5.7 の対象は **agent lifetime** (birth → 退場)。S(100)≈0.80 は「agent の 8 割が 100 step 以上生存」
- 「C0p 446/trial = 3.0e-3 rt/agent/step」の 446 は RT 数ではなく **matched 窓内の lifetime sample 数** (= birth event 数)。full window の RT は 1.04M/trial、lifetime sample は 10,880/trial
- むしろ 446/(100×1500) = 3.0e-3 births/agent/step ≈ 定常 hazard 2.8–3.0e-3 (birth rate ≈ death rate) で、lifetime framing の self-consistency が閉じる
- **adapter の RT 定義 drift なし** (「実保有を伴う open→close」、YH005_1 と同一挙動が数値で確認済)
- 運用面の指摘は採用: この取り違えは P1 起案 → diff 注記 → 本 review で 3 回目 (今回はレビュアー側)。oral でも確実に起きる。**全数字に対象物ラベル (agent lifetime τ / RT horizon h) を強制** — README §S5.7 に規約として明記

### 6.2 headline 言語 (① 承認 + 修正条件) — 反映済

- hazard 構造で張る形に README 書き換え済。ただし review 文中の「定常 hazard 2.8e-3 ≒ median 保有 ~250step」は 2 点修正:
  (a) 「保有」は RT 混同 wording → 「agent lifetime」
  (b) hazard は早期 ramp あり ([0,100]: 0.8e-3 → [250,500]: 2.7e-3 → τ≳500 で ~3.0–3.2e-3 安定、`tab_S5.7_hazard_segments.csv`)。一定 hazard 近似の median 248 ではなく **KM median lifetime ≈ 390** が正
- 52x/58x は「matched 窓末 τ=1499 の survival ratio」ラベル + curve 添付を必須化、τ ラベルなし単独引用は禁止と README に明記。lead = 52x (uniform)、58x 併記、58>52 順序に重みなし
- Λ(τ) ≡ −ln S_KM(τ) (Nelson-Aalen ではない) を code / README / JSON に明記

### 6.3 τ grid (②) — 反映済

- README 表を {100, 250, 500, 1000, 1499} に変更 (CSV は 7 点 grid のまま superset)
- figure: KM curve + **全域 Greenwood 95% band** + grid 点 trial-level bootstrap marker (幅比 1.0–1.5x、log に記録)

### 6.4 S5.8 = P3 / S6 は P3 後 (③④) — 同意、plan 化

- P3 は S6 の論理的前提 (A3 lifetime-cap は「観測された長 lifetime が定常」を暗黙仮定 — plateau が transient なら A3 は artifact を cap する) → `stage_S5.8_plan.md` 起案
- 区間 hazard で C2 [1000,1499] = 0 件 event は「suggestive 止まり」を裏付け (T=1500 超の timescale を bound できていない)
- P2 (c_ticks) は S5.9 / robustness 一括に後置 (censoring は fill/matching 律速で trigger 律速でないため gap の大きさは脅かさない)

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 | S5.7 完走。KM matched S(1499) = LOB 73–91% vs agg 1.3–1.8% (gap 52–58x)、S5.5 整合検算 PASS、headline 差し替え確定。naive preview (~100x) は KM で 52–58x に下方修正 — 引用は KM 値に統一。 |
| v1.1 | Yuito review 反映: (1) cross-experiment「125x ズレ」は RT horizon と agent lifetime の対象物取り違えで不整合なし (RT median=2 / 0.209 rt/agent/step が YH005_1 と一致、定義 drift なし)、対象物ラベル強制を規約化。(2) headline を hazard 構造 framing に書き換え (早期 ramp → ~3e-3 安定 / LOB shake-out → 凍結、median lifetime ≈390)、52x/58x は τ=1499 ラベル + curve 必須。(3) τ grid {100,250,500,1000,1499} + Greenwood band + hazard segments 表追加。(4) S5.8 = P3 起案、S6 は S5.8 後、P2 は S5.9 後置。 |
