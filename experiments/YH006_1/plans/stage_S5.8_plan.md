# Stage S5.8 plan v1 — LOB equilibration check: T=10000 延長で hazard plateau の transient / 定常判別 (P3)

| 項目 | 値 |
|---|---|
| Stage | S5.8 — C2/C3 を T=10000 で数 seed 延長、S(τ) の τ > 1500 挙動で plateau を bound |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Mac ~1.5–2.5 時間 (12 trial × ~46 分 / 8 worker) + Windows ~15 分 (KM 延長) |
| 新規 sim | LOB 12 trial (C2/C3 × T=10000 × seed 1000–1005) |
| 前提 | S5.7 完走済 (hazard plateau の可視化により本攻撃の残存が明確化)。**S6 (A3) は本 stage の結果待ち** |

## 0. 位置付け — S6 の論理的前提 (Yuito review 2026-06-07 ④)

S5.7 で確定した「LOB は初期 shake-out 後 hazard ≈ 0 で凍結」は、C2 の後期区間
[1000, 1499] が event 0 件のため **T=1500 を超える timescale を bound できていない**
(suggestive 止まり)。2 つの仮説が未分離:

- **H_frozen (定常)**: LOB friction が turnover を実際に止めている。plateau は T を
  延ばしても維持され、hazard は agg の ~3e-3 より桁で低いまま
- **H_transient**: 1500 step では LOB の遷移が終わっておらず、plateau は打ち切り
  窓 artifact。T を延ばすと S(τ) は agg 方向に落ち続ける

**S6 (A3 lifetime cap) は「観測された長 lifetime が定常」を暗黙の前提にしている**。
H_transient なら A3 は artifact を cap することになり因果主張が崩れる。
→ 論理順は強制: S5.8 → S6。

## 1. 設計

### 1.1 T=10000 のみ走らせ、T=5000 は nested で読む

T は run 長であって dynamics のパラメタではないため、T=10000 run の S(τ) curve は
τ=5000 時点の情報を内包する。T=5000 を別走する必要はない (compute 半減)。
sanity として T=10000 run の S(τ ≤ 1500) が S3 (T=1500 × 100 trial) の curve と
整合することを確認する (同 seed の前半は同一挙動のはず — §3.2)。

### 1.2 規模

- C2 / C3 × seed 1000–1005 (6 seeds) = 12 trial。方向判定には十分
  (100 trial は不要 — Yuito P3 指摘どおり)、trial 間 SD が大きければ +4 seed 追加
- runtime: S3 実測 mean ~410 s/trial (T=1500) × ~6.7 (linear scaling 仮定)
  ≈ 46 分/trial。12 trial / 8 worker ≈ 1.5–2 時間。> 4 時間/trial で stop trigger

### 1.3 KPI — 延長区間の平均 hazard ΔΛ/Δτ

`tab_S5.8_hazard_extension.csv`: 区間 [1500, 3000], [3000, 5000], [5000, 10000] の
ΔΛ/Δτ を C2/C3 で算出し、参照値と比較:

| 判定 | 基準 (両 cond) | 帰結 |
|---|---|---|
| **H_frozen 確定** | 全延長区間で hazard ≤ 1e-4 (agg ~3e-3 の 1/30 未満) | plateau は bounded (「half-life ≥ 7000 step」型の bound 付き)。S6 進行 GO |
| **H_transient** | いずれかの区間で hazard ≥ 1e-3 (agg と同 order) | plateau は窓 artifact。S6 設計見直し + F1 finding の refactor を Yuito 議論 |
| ambiguous | 中間 (1e-4 < hazard < 1e-3) | Yuito 議論 (弱い transient — bound の言い方を調整) |

補助: S(10000) 点推定、wealth persistence (w_init vs 生存) が延長窓でも保持されるか。

## 2. 作業項目

### 2.1 Windows — dispatcher 拡張 (~30 分)

- `run_lob_trial` / `parallel.py` に `main_steps` override passthrough を追加
  (`run_lob_trial_smoke` は既に kwarg を持つ、`config.LOB_PARAMS["main_steps"]=1500`
  の上書き経路のみ。Phase 1 編集なし)
- `code/lob_extension_ensemble.py` 新規 (~80 行、`lob_ensemble.py` テンプレート):
  `--conds C2,C3 --seeds 1000-1005 --main-steps 10000`、出力 `data/{C2,C3}_T10k/`
- commit + push

### 2.2 Mac — sim (~1.5–2 時間)

```bash
cd experiments/YH006_1 && git pull
python -m code.lob_extension_ensemble --determinism-only   # smoke (seed=1000 × 2、T=3000 短縮版で guard)
python -m code.lob_extension_ensemble                      # 12 trial
git add data/ logs/ && git commit && git push
```

### 2.3 Windows — KM 延長 + 判定 (~15 分)

- `survival_analysis.py` を window パラメタ化して再利用 (`T_WINDOW=10000`、
  対象 cond = C2_T10k/C3_T10k、agg 参照線は S5.7 値を流用)
- §3.2 sanity: T10k run の S(τ≤1500) vs S3 curve の重なり確認 (乖離 → seed 依存 or
  RNG 消費順問題、stop trigger)
- 出力: `tab_S5.8_hazard_extension.csv` / `fig_S5.8_survival_extension.png`
  (S5.7 figure に延長 curve を重ねる) / `S5.8_summary_for_diff.json` / README §S5.8 /
  `stage_S5.8_diff.md`

## 3. 完了条件

- [ ] dispatcher `main_steps` passthrough (Phase 1 非編集) + 新規 script
- [ ] Mac determinism smoke PASS + 12 trial 完走
- [ ] §3.2 sanity (S(τ≤1500) vs S3) PASS
- [ ] KPI 判定表 + figure + README §S5.8 + diff
- [ ] **S6 go/no-go の Yuito 判定** (H_frozen → S6 GO / H_transient → S6 再設計)

## 4. 停止トリガー

- determinism guard fail (main_steps override が RNG 消費順を変える)
- runtime > 4 時間/trial (T=10000 が superlinear に爆発 — LOB板が深くなり matching コスト増の可能性)
- §3.2 sanity fail (T10k 前半 1500 step が S3 と不一致)
- 12 trial 中の trial 間で hazard 判定が割れる (6 seeds で足りない → +4 seed 追加して再判定)

## 付記 — 後置した項目

- **P2 (c_ticks self-consistency)**: S5.9 / robustness 一括へ。censoring は
  fill/matching 律速 (両側 MARKET 不約定 + zero-fill open ~30%) で trigger 律速では
  ないため、c_ticks ズレは gap の解釈に効くが大きさには効かない (Yuito review ③)
- **S1-secondary**: 優先度は S5.8 / S6 の後、Yuito 判断のまま

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | Yuito review 2026-06-07 ③④ を受けて起案。P3 を S6 の論理的前提として強制順序化 (A3 は「長 lifetime が定常」を暗黙仮定)。T=10000 のみ 6 seed × C2/C3 (T=5000 は nested 読み)、KPI は延長区間 ΔΛ/Δτ の 1e-4 / 1e-3 閾値で H_frozen / H_transient 判別。 |
