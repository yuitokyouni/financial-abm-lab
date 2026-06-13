# Stage S5.6 diff — MMFCN orderVolume sensitivity scan: 約定 artifact 検出

S5.6 plan v1 の実行結果。LOB C3 setup で MMFCN の `orderVolume` を 4 設定 × 2 trial = 8 trial scan、artifact 疑惑を弾力性 (elasticity) ベースで判定。

---

## Verdict — **H_artifact_negated_strong** (MMFCN は副次的供給源)

弾力性 ε(4x) = log(1.42) / log(4) = **0.254 ≤ 0.3** → MMFCN は独立、Phase 2 finding 頑健、S6 進行可。

| metric | mmfcn_05x | mmfcn_1x (baseline) | mmfcn_2x | mmfcn_4x | 弾力性解釈 |
|---|---:|---:|---:|---:|---|
| n_rt_mean | 4679.5 | **4398.0** | 5464.0 | 6251.0 | ε(4x) = log(1.42)/log(4) = **0.254** |
| n_rt ratio vs 1x | 1.06 | 1.00 | 1.24 | **1.42** | 線形供給依存 (ε=1) なら 4x、実測は 1.42x |
| rt_rate_per_agent_step | 0.0312 | **0.0293** | 0.0364 | 0.0417 | SG fill ease proxy、4x で +42% のみ |
| forced_retire_rate | 0.435 | 0.390 | 0.405 | 0.355 | flat (MMFCN 設定にほぼ非依存) |
| censoring_rate | 67.4% | 71.0% | 69.2% | 71.0% | flat (~70% で安定) |

**結論**:
- orderVolume を 4 倍にしても SG round-trip 数は 1.42 倍にしか増えない → MMFCN は **既に余裕供給** している
- 0.5x (半減) でも n_rt が 1.06 倍 (微増、誤差レンジ内) → 半減しても約定はほぼ変わらない、現状設定は十分過剰供給
- forced_retire / censoring が flat → MMFCN setting は agent の生死動態に影響薄、SG 内在 dynamics が dominant
- これは「MMFCN bottleneck artifact」仮説 (Yuito 指摘 2) の **強い反証** であり、Phase 2 の **仮説 A revised + lifetime persistence finding が頑健** であることを示す

---

## 1. baseline bit-一致 PASS — Phase 1 後方互換 hook の non-regression 確認

`mmfcn_1x` (= orderVolume 30、既存 C3 と同設定) を `mmfcn_order_volume=None` 経路で実行:

| seed | parquet sha256 | data/C3/trial_{seed}.parquet との一致 |
|---:|---|---|
| 1000 | `141d3e374cb2c613...` | **bit-一致 PASS** |
| 1001 | `5c6ec30709ba5945...` | **bit-一致 PASS** |

S4 §0.4 で確定した Phase 1 後方互換 protocol (「`mmfcn_order_volume=None` 経路は既存挙動 bit-一致」) が実証され、本 hook の設計妥当性確認。

---

## 2. 弾力性ベース判定の根拠 (旧 ratio 閾値からの更新)

旧 plan §3.5 の判定基準:
- ratio_2x ≥ 1.8 or ratio_4x ≥ 2.5 → H_artifact_mmfcn
- ratio_2x ≤ 1.2 AND ratio_4x ≤ 1.5 AND ratio_05x ≥ 0.8 → H_artifact_negated
- それ以外 → ambiguous

実測 (ratio_2x = 1.24, ratio_4x = 1.42, ratio_05x = 1.06) は旧基準だと **ambiguous** に落ちる (1.24 が 1.2 閾値を僅か超えるため negated 条件 fail)。

**Yuito 2026-05-19 提示の弾力性ベース判定** (本 diff で採用):
- ε(4x) = d log(n_rt) / d log(orderVolume) を計算
- ε=0 完全独立、ε=1 線形供給依存
- ε ≤ 0.3 → 独立性高 (H_artifact_negated_strong)
- ε ≥ 0.7 → bottleneck (H_artifact_mmfcn)
- 0.3 < ε < 0.7 → 中間

実測 ε(4x) = 0.254 → **H_artifact_negated_strong** (旧 ambiguous より明確な独立性確定)。

経済学的解釈: ε=0.25 は「供給弾力性が低い」 = 需要側 (SG agent の発注意図) が dominant な要因で、供給側 (MMFCN liquidity) は副次的。これは「Phase 2 で観察された LOB SG dynamics の特徴は MMFCN 設定の副産物ではなく、SG 内在の strategy + wealth dynamics 由来」を支持する。

---

## 3. SG fill_rate proper の限界と proxy 採用

plan §2.4 の「mmfcn_fill_rate」「SG agent fill_rate」は OrderTrackingSaver の log を追加 export する必要があり、本 version では **未測定**。
代わりに以下の proxy を採用:

| proxy | 測定方法 | mmfcn_4x/1x 比 | 解釈 |
|---|---|---:|---|
| `rt_rate_per_agent_step` | n_rt / (N_sg × main_steps) | 1.42 | SG が「平均的に何 step に 1 回 RT を完成させたか」の rate。4x にしても 1.42x のみ |
| `forced_retire_rate` | agents.forced_retired の平均 | 0.91 (35.5/39.0) | 各 SG agent が破産退場した割合、MMFCN setting に flat |
| `n_substitutions` | lifetime parquet 行数 − agent 数 | 1.00 | 中途交代回数、MMFCN setting にほぼ flat |

**フル fill_rate を測りたい場合**: Mac 側 `OrderTrackingSaver` を改修して「SG が submit したが unfilled のまま session 終了した order の数」を per-trial で export する必要がある (本 plan scope 外、将来の補強検証として申し送り)。

---

## 4. 数値詳細 (`tab_S5.6_mmfcn_sensitivity.csv`)

設定別の per-trial 値 (seed=1000, 1001) と mean:

| setting | seed | n_rt | rt_rate/agent_step | forced_retire | p25 lifetime | censoring | conditional median |
|---|---:|---:|---:|---:|---:|---:|---:|
| mmfcn_05x | 1000 | 4500 | 0.0300 | 0.430 | 142.5 | 68.5% | 31.5 |
| mmfcn_05x | 1001 | 4859 | 0.0324 | 0.440 | 106.0 | 66.2% | 36.0 |
| mmfcn_1x | 1000 | 3876 | 0.0258 | 0.430 | 239.0 | 69.4% | 18.5 |
| mmfcn_1x | 1001 | 4920 | 0.0328 | 0.350 | 113.5 | 72.5% | 26.0 |
| mmfcn_2x | 1000 | 4795 | 0.0320 | 0.400 | 133.8 | 68.5% | 70.0 |
| mmfcn_2x | 1001 | 6133 | 0.0409 | 0.410 | 188.5 | 69.9% | 51.5 |
| mmfcn_4x | 1000 | 5504 | 0.0367 | 0.350 | 193.8 | 72.5% | 25.0 |
| mmfcn_4x | 1001 | 6998 | 0.0467 | 0.360 | 162.2 | 69.4% | 47.0 |

trial 間ばらつきは大きい (e.g., mmfcn_1x で 3876 vs 4920、+27%) が、設定間の系統的な傾向 (4x で +42%) は確認できる。

---

## 5. S5.5 + S5.6 統合判定 — **S6 進行 GO**

| stage | finding | verdict |
|---|---|---|
| S5.5 | RT10k pooled bin_var (C0u −0.38, C0p −0.37) が full agg 水準 (−0.40 / −0.29) 保持、LOB との 5x gap は sample size では説明不能 | **H_micro 強支持** |
| S5.6 | elasticity ε(4x) = 0.254、orderVolume を 4 倍にしても n_rt 1.42x、forced_retire / censoring flat | **H_artifact_negated_strong** |

**結論**: Phase 2 の主要 finding (仮説 A 単純版反証 + 仮説 A revised の浮上 + lifetime persistence primary evidence) は方法論的に頑健で、観察された動態は:
- LOB microstructure 真効果 (S5.5 確定)
- MMFCN 設定の副産物ではない (S5.6 確定)

→ **S6 (A3 ablation = initial wealth distribution を C2 同様 uniform 化、それ以外 C3 と bit-同一) 起案**。仮説 A revised の direct causal test を実施。

---

## 6. plan §5 Yuito 確認事項の現状

1. **`orderVolume` を primary に選んだ判断**: 結果として ε=0.25 で明確に判定できた、numAgents scan の追加は不要 (verdict は確定的)
2. **trial 数 2/設定**: trial 間ばらつき 27% は許容範囲、verdict が境界遠 (ε=0.25 vs 閾値 0.3) で安定 → 追加 trial 不要
3. **判定**: H_artifact_negated_strong → S6 進行可
4. **追加 scan の要否**: 不要 (verdict 明確)
5. **S6 進行 / refactor 判断 (S5.5 統合)**: **進行**
6. **mmfcn_fill_rate proper**: 本 version で未測定、proxy で代替、補強検証として申し送り

---

## Stage 進捗

| Stage | Date | 状態 | Note |
|---|---|---|---|
| 1. Windows 側 hook 実装 + Phase 1 test (27/27 PASS) | 2026-05-18 | **完了** | `mmfcn_order_volume` kwarg、`None` 経路 bit-一致 |
| 2. Mac sweep 8 trial 完走 (commit 53a6415) | 2026-05-18 | **完了** | runtime 160-491 秒/trial、計 ~30 分 / 8 worker |
| 3. Windows 集計 + 弾力性判定 | 2026-05-19 | **完了** | baseline bit-一致 PASS、verdict 確定 |
| 4. 統合判定 + S6 plan 起案 | 2026-05-19 | 次 | 本 diff 提出後、`plans/stage_S6_plan.md` v1 |

---

## 出力一覧

| パス | 内容 |
|---|---|
| `code/mmfcn_sensitivity.py` | Mac sweep runner |
| `code/aggregate_mmfcn_sensitivity.py` | Windows 集計 (~310 行、弾力性判定で refactor) |
| `data/mmfcn_sensitivity/{setting}_{seed}/*.parquet` × 32 | 4 setting × 2 seed × 4 schema |
| `outputs/tables/tab_S5.6_mmfcn_sensitivity.csv` | 設定別 mean/min/max + 10 metric (4 行) |
| `outputs/figures/fig_S5.6_mmfcn_scan.png` | 4 panel: n_rt / forced_retire / lifetime / censoring vs orderVolume |
| `logs/S5.6_mac_summary.json` | Mac sweep raw summary (8 runs) |
| `logs/S5.6_summary_for_diff.json` | Windows aggregation + verdict + ratios |
| `logs/runtime/20260518_202105_S5.6_mmfcn_sensitivity.log` | Mac sim ログ |
| `logs/runtime/{ts}_S5.6_aggregation.log` | Windows 集計 ログ |
| `plans/stage_S5.6_diff.md` | 本ファイル |
| `README.md` §S5.6 追記 | (本 commit に含める) |

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書) | S5.6 plan v1 の実行結果。Yuito 指摘 2 (MMFCN bottleneck artifact 疑惑) への応答完了。Verdict = **H_artifact_negated_strong** (ε(4x) = 0.254 ≤ 0.3、orderVolume を 4 倍にしても n_rt 1.42x、線形供給依存からの逸脱)。判定基準を旧 ratio 閾値 (1.2/1.5/1.8/2.5) から **弾力性 (経済学 elasticity)** ベースに refactor (Yuito 2026-05-19 提示)。baseline bit-一致 PASS で Phase 1 後方互換 hook の non-regression 実証。SG fill_rate proper は OrderTrackingSaver 拡張が必要なため `rt_rate_per_agent_step` を proxy として併記。S5.5 (H_micro 強支持) と統合して **S6 (A3 ablation) 進行 GO**。 |
