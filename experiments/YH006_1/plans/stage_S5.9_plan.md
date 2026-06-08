# Stage S5.9 plan v1 — c_ticks self-consistency (P2): SG 投入後 1 パス再較正 + 数 seed robustness

| 項目 | 値 |
|---|---|
| Stage | S5.9 — c_ticks 再較正 (P2 解消) + trigger 率 robustness |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Win 数分 (再較正 + 集計) + Mac 30-60 分 (数 seed × 2-3 cond 再走) |
| 新規 sim | LOB 少数 seed (C2/C3 × seed 5-6 本、c_ticks' で再走) |
| 前提 | S5.8 = H_frozen 確定済。S6 とは**並走可能** (互いの data に依存しない)。dossier §9-1 (最大の残存 live issue) の処理 |

本 plan は dossier §9 limitation #1 / findings P2 の解消。**主張は「c_ticks のズレは gap の
*大きさ* には効かない (censoring は fill/matching 律速) が、*解釈* と trigger 率には効きうる」**
の検証であって、Phase 2 の主要 finding を覆す stage ではない。同時に**軸2 (執行層) の go/no-go
判断材料**: 凍結の原因が fill 側 (執行) か trigger 側 (認知閾値) かを切り分ける
([[refs_execution_algorithms]] §9.3)。

---

## 0. 背景と P2 の正確な定義

### 0.1 現状の c_ticks 較正 (Phase 1)

- `c_ticks = 3 × median|Δmid|`、**C1 (SG 投入前、MMFCN のみの 5000 step) の mid 揺らぎ**で較正
  → 確定値 **28 tick** (`config.py::LOB_PARAMS["c_ticks"]=28.0`、GLOSSARY §c_ticks)。
- c_ticks は SG agent の価格認知閾値: |Δprice| が c_ticks を超えると state 遷移 → 取引 trigger。

### 0.2 P2 (self-consistency 違反) の中身

SG を投入すると volatility regime が変わる (SG の注文が板を動かす)。28 tick は**投入前**の
揺らぎで測った値なので、投入後の |Δmid| 分布に対して self-consistent でない。

- c_ticks が**過大** (post-SG vol が pre-SG より大) なら、実効的に trigger が**鈍る** → RT が
  rare になる一因 → 凍結に**寄与**しうる。
- c_ticks が**過小**なら逆に over-trigger。
- どちらに何 tick ズレているかは**未測定**。これが本 stage で埋める穴。

### 0.3 主張に対する射程 (pre-statement、数字を見る前)

dossier の既定方針 (Yuito review ③): **censoring (生存 gap) は fill/matching 律速であり
trigger 律速ではない**ため、c_ticks ズレは **gap の大きさを脅かさない**。本 stage はこれを
**反証可能な形で test** する: c_ticks' で再走して RT 率が大きく動いても funnel/survival の
gap が保たれるなら主張は補強され、gap が崩れるなら主張は修正が必要。

---

## 1. 目的

(a) **再較正**: SG 投入後 (C1→SG 投入済の main 区間 mid price) から `c_ticks' = 3 × median|Δmid|_{post-SG}`
   を 1 パスで算出。C2 と C3 で別々に測る (Pareto/uniform で vol regime が違いうる)。

(b) **ズレの定量化**: `c_ticks'(C2)`, `c_ticks'(C3)` vs 28 を比較。何 tick・何倍ズレているか。

(c) **robustness 再走**: c_ticks' を注入して C2/C3 を**少数 seed** (5-6 本、S3 と同 seed 部分集合)
   再走。以下の robustness を確認:
   - **trigger 率** = RT rate (rt/agent/step、S3 で 0.209) がどれだけ動くか
   - **survival** (matched S(1499)) が C2 91% / C3 73% から動くか
   - **funnel** (pooled bin_var_slope) が C2 −0.059 / C3 −0.126 から動くか

(d) **軸2 切り分けへの寄与**: c_ticks' 再走で trigger 率が回復 (RT rate ↑、survival ↓) するなら
   凍結の一因は trigger 側 = 認知閾値較正 → 軸2 (執行層 slicing) は fill 側だけ埋めるので
   不十分。trigger 率がほぼ不変なら凍結は fill 側律速 → 軸2 が筋、と判断材料を出す。

---

## 2. 入力 / 流用資源

- `code/run_experiment.py::run_lob_trial` (`c_ticks` kwarg は既存、line 187)
- `config.py::lob_settings(cond, c_ticks=...)` (override 経路は既存、line 132-137)
- `code/survival_analysis.py` (RT 統計 / KM S(τ) 流用)
- `code/analysis.py::bin_variance_slope_pooled` (funnel 流用)
- `data/C2/`, `data/C3/` (baseline、既存 100 trial — seed 部分集合の対照)
- `data/_phase1_imported/c_ticks_calibration.json` (Phase 1 較正の原典、参照)

**新規実装は最小**:
- `code/recalibrate_c_ticks.py` (~60 行): 既存 C2/C3 main 区間の mid 系列から
  `3 × median|Δmid|` を再計算。既存 parquet に mid price 系列があれば**新規 sim 不要で
  再較正のみ完結**するか先に確認 (§3.1)。無ければ C1+SG 投入の 1 seed を mid ロギング付きで再走。
- `code/cticks_robustness_ensemble.py` (~80 行、`lob_ensemble.py` テンプレ): c_ticks' で
  C2/C3 を少数 seed 再走、`data/C2_cticks/`, `data/C3_cticks/` に出力。

---

## 3. 作業項目

### 3.1 mid 系列の所在確認 (Win、最初に必ず)
既存 `data/C2|C3/*.parquet` に main 区間の mid price (step 別) が記録されているか確認:
- **記録あり** → 新規 sim ゼロで再較正完結 (§3.2 へ)。最良ケース。
- **記録なし** → mid ロギング付きで C2/C3 各 1 seed を Mac で再走して mid 系列を得る
  (§3.3 と統合、~10 分)。

### 3.2 再較正 (Win、数分)
`recalibrate_c_ticks.py`:
1. C2 と C3 の main 区間 (warmup 後 [200,1500]) の mid 系列を pool。
2. `c_ticks'_{cond} = 3 × median|Δmid|_{main, cond}` を算出。
3. `logs/S5.9_cticks_recalibration.json` に `{c_ticks_phase1: 28, c_ticks_C2: x, c_ticks_C3: y, ratio}` を永続化。
4. **採否方針**: C2/C3 で別値なら、robustness 再走は各 cond 自身の c_ticks' を使う。
   2 値の乖離が小 (< 20%) なら pool した単一値も併記。

### 3.3 robustness 再走 (Mac、30-60 分)
`cticks_robustness_ensemble.py`:
- C2/C3 を **seed 1000-1005 (6 本)** で c_ticks' 注入再走 (S3/S5.8 と同 seed で対照可能)。
- determinism guard (seed 固定 2 run 一致) は 1 seed で確認。
- 出力 schema は S3 LOB と同一 (rt_df / agents_df / metrics)。

### 3.4 集計 + 判定 (Win)
`aggregate_cticks_robustness.py`:
1. c_ticks' 再走の RT rate / matched S(1499) / pooled bin_var_slope を baseline (28 tick、同 seed)
   と paired で比較。
2. **pre-registered 判定** (§4)。
3. 出力: `tab_S5.9_cticks_robustness.csv`, `fig_S5.9_cticks_comparison.png`, `S5.9_summary_for_diff.json`,
   README §S5.9 追記。

---

## 4. Pre-registered 判定基準 (数字を見る前に確定)

| 量 | baseline (28t, 同 seed) | 判定 |
|---|---|---|
| **funnel** pooled bin_var_slope | C2 ≈ −0.06 / C3 ≈ −0.13 | **主張維持** = c_ticks' でも \|Δ\| ≤ 0.05 (gap は trigger 律速でない)。\|Δ\| > 0.10 なら主張修正 (P2 が大きさに効いていた) |
| **trigger** RT rate | 0.209 rt/agent/step | 解釈用。≥ 2x 変化なら trigger 律速の寄与あり = 軸2 だけでは不十分のシグナル |
| **survival** matched S(1499) | C2 91% / C3 73% | 解釈用。c_ticks' で大きく低下 (退場が戻る) なら凍結に trigger 寄与 |

- **主たる成功条件は funnel gap の維持** (Phase 2 主張の robustness)。trigger/survival の変化は
  **軸2 go/no-go の診断**であって S5.9 の pass/fail 条件ではない。
- c_ticks' が 28 とほぼ同じ (\|ratio−1\| < 0.1) なら「P2 はそもそも小さい問題だった」が結論で、
  これも valid な完了形。

---

## 5. 完了条件

### Windows
- [ ] §3.1 mid 系列所在確認
- [ ] §3.2 再較正 → `c_ticks'` 確定、JSON 永続化
- [ ] (Mac 後) §3.4 集計 + pre-registered 判定 + README §S5.9 + `stage_S5.9_diff.md`

### Mac
- [ ] git pull
- [ ] (§3.1 で必要なら) mid ロギング再走
- [ ] §3.3 c_ticks' robustness 再走 (C2/C3 × seed 1000-1005) + determinism guard
- [ ] git commit + push

---

## 6. Stop triggers / Yuito 確認事項

### 実装中 stop trigger
- §3.1 で mid 系列が parquet に無く、再走しても mid を取れない設計上の穴がある場合 → 停止相談
- §3.2 で `c_ticks'` が 28 から **5x 以上**乖離 → regime shift が想定外に大きい、設計見直し相談
- determinism guard fail

### 完了後レビュー
1. §3.2 再較正方針 (C2/C3 別値 vs pool 単一値) の採否
2. §4 funnel gap 維持判定 — Phase 2 主張の robustness 確認
3. **軸2 go/no-go の診断結果**: trigger 律速の寄与があるか ([[refs_execution_algorithms]] §9.3)。
   trigger 寄与が大 → c_ticks 自己組織化 (YH007 系) が先。fill 律速確定 → 軸2 (執行層) を spec 化
4. S5.9 を Phase 2 Limitations 節にどう書き込むか (残存 → 解消 / 縮小)

---

## 改訂履歴
| Version | 内容 |
|---|---|
| v1.0 (Draft) | S5.9 初版。P2 (c_ticks self-consistency) を SG 投入後 1 パス再較正 + 少数 seed robustness で解消。主成功条件は funnel gap 維持 (Phase 2 主張 robustness)、副次に trigger/survival 変化を軸2 go/no-go 診断に使う。sim は Mac、再較正・集計は Win。S6 と並走可能。 |
