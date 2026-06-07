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

### 1.3 KPI — 延長区間の segment 別 hazard ΔΛ/Δτ (v1.1 で Katahira scale に anchor)

`tab_S5.8_hazard_extension.csv`: 区間 [1500, 3000], [3000, 6000], [6000, 10000] の
ΔΛ/Δτ を C2/C3 で **segment 別に** 算出 (単一平均は slow leak を隠すため禁止 —
h→0 (真の凍結) と h=const>0 (slow leak) を分離する)。

**閾値の anchor (v1.1)**: 判定対象は「52x gap が Katahira T=50000 で生き残るか」
なので、閾値は延長窓 8500 step ではなく T=50000 外挿に対して切る:
- h=1e-4 → ΔΛ=0.85 で延長窓内に S 半減、T=50000 外挿で exp(−4.85) → gap 消滅。
  1e-4 は「frozen」ではなく「遅く解ける transient」(旧 v1.0 閾値は ~5x 緩かった)
- h=2e-5 → T=50000 外挿で exp(−0.97)≈0.38、C2 91%→~34% で gap 残存
- anchor は自由な絶対値でなく **S5.7 C2 late-window hazard (~1e-5 オーダー、
  `tab_S5.7_hazard_segments.csv`)**: frozen ⟺ plateau がそのまま継続

| 判定 | 基準 (両 cond、全 segment) | 帰結 |
|---|---|---|
| **H_frozen** | hazard ≤ **2e-5** (S5.7 late-window の継続) | 凍結は定常、T=50000 外挿で gap 残存。S6 進行 GO、Layer-2-timescale 留保が消える |
| **H_transient** | いずれかの segment で hazard ≥ 1e-3 (agg steady へ climb) | **rescope であって否定ではない** (§1.4)。S6 設計は要調整、Yuito 議論 |
| **H_partial_freeze** (dead zone 2e-5–1e-3、**pre-registered**) | slow leak | S6 GO だが A3 解釈を「partial freeze の解除」に限定、headline を「T < X で凍結」に qualify (X = 外挿で gap 半減する T)。6 seed では hazard 値の解像不足 — 値そのものは headline しない |

補助: 最終 segment hazard で T=50000 へ外挿した S(50000) と gap 残存率、
segment trend (decaying→0 / constant)、S(10000) 点推定。
agg は full T=50000 データで hazard constancy を extinction まで確認
(外挿妥当性の裏付け、post-processing only)。

### 1.4 判定後の構え (P3) — どちらも proposal の勝ち筋

本 stage は proposal Limitations の Layer-2-timescale 留保 (LOB T=1500 = Katahira/33)
を直接 test している:
- **H_frozen** → 「凍結は定常、有限 T artifact ではない」を実証 = 留保が 1 つ消える
- **H_transient** → 52x finding は死なない。T=1500 (≒ Katahira/33) での測定値として
  真のまま、「friction-induced transient freeze が τ~X で解ける」へ rescope =
  留保が測定済みの result に格上げ
- → H_transient を panic 扱いしない。どちらに転んでも hand-wave が数字に変わる
  **no-lose 診断** として oral で位置づける

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
python -m code.lob_extension_ensemble --determinism-only   # S3 等価チェック + guard
python -m code.lob_extension_ensemble                      # 12 trial
git add data/ logs/ && git commit && git push
```

**S3 等価チェック (v1.1 P1、fail-fast)**: 12 trial の前に C3 seed=1000 を
`main_steps=1500` override で 1 回走らせ (~7 分)、archived S3 出力 (`data/C3/`) と
semantic 一致 (rt_df 全列 + lifetimes (t_birth, t_end, censored) 集合) を確認。
determinism guard (T=3000) は override 機構と worker の決定性を見るが S3 参照を
持たない — 「override=1500 == S3 default」(run 長が前半 [0,1500] に漏れる経路の
不在) はこのチェックだけが経験的に確定する。fail なら 12 trial (2h) を走らせずに
停止。

**T 不変性の事前確認 (P5、確認済 2026-06-07)**: SG は MARKET_ORDER + self-cancel +
opposing-liquidity guard で全て per-step reactive。MMFCN の limit order は
`ttl = timeWindowSize ∈ [100, 200]` (config 定数、T の関数ではない) で期限切れ —
T=10000 でも stale order の book 堆積 / O(N²) 再燃の経路なし。periodic reset 類も
なし。4h/trial trigger は保険として維持。

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
| v1.0 (Draft) | Yuito review 2026-06-07 ③④ を受けて起案。P3 を S6 の論理的前提として強制順序化 (A3 は「長 lifetime が定常」を暗黙仮定)。T=10000 のみ 6 seed × C2/C3 (T=5000 は nested 読み)、KPI は延長区間 ΔΛ/Δτ の 1e-4 / 1e-3 閾値で H_frozen / H_transient 判別。 |
| v1.1 (本書) | Yuito 2nd review 反映: (P1) S3 等価チェック (override=1500 == archived S3) を Mac 12 trial の**前**に fail-fast で前倒し。(P2) H_frozen 閾値を 1e-4 → **2e-5** に締め直し (旧値は T=50000 外挿で gap が消える「遅い transient」を frozen と誤判定、~5x 緩かった)、anchor は S5.7 C2 late-window hazard。segment を [1500,3000]/[3000,6000]/[6000,10000] に分割し h→0 / h=const (slow leak) を分離、dead zone (2e-5–1e-3) の処理を pre-register (= H_partial_freeze: S6 GO + A3 解釈限定 + headline qualify)。T=50000 外挿 + agg full-window constancy check (P5) を追加。(P3) H_transient = rescope であって否定ではない、を判定 message と plan に明記。(P5) liquidity guard の T 不変性を事前確認済 (MMFCN ttl ≤ 200 = 定数、SG は per-step reactive)。6 seed は binary gate には十分だが hazard 点推定は headline しない。 |
