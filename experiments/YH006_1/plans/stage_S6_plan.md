# Stage S6 plan v1 — Ablation A3: lifetime cap τ_max + C3_A3 100 trial + KPI L3 判定

| 項目 | 値 |
|---|---|
| Stage | S6 — Ablation A3 (`lifetime_cap=True`、`C3_A3` × 100 trial) |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Win 5 分 (calibration) + Mac 1.5-3 時間 (smoke + determinism + 100 trial) + Win 30 分 (aggregation) |
| 新規 sim | LOB 100 trial (C3_A3、Mac で実行) |
| 前提 | S5 完走済 (`data/ensemble_summary.parquet` 600 行)、S5.5/S5.6 統合判定で S6 進行 GO ([[stage-s5p5-diff]] [[stage-s5p6-diff]])。**追加 gate (Yuito review 2026-06-07 ④): S5.8 (LOB equilibration check) の H_frozen 判定が先行必須** — A3 lifetime cap は「観測された長 lifetime が定常」を暗黙仮定しており、S5.8 で H_transient なら本 plan は再設計 |

本 plan は仮説 A revised (「LOB Pareto 条件下では initial wealth distribution の persistence が dominant 因子」) の **direct causal test**。S4-S5 (A1 ablation) と同じ Phase 1 後方互換 protocol で実装、C3_A3 が L3 KPI を pass すれば「Pareto wealth persistence chain が F1 機構の中核」を確定。

---

## 0. S6 着手前提と仮説 A revised の整理

### 0.1 S5.5/S5.6 統合判定 (S6 GO の根拠)

- **S5.5 = H_micro 強支持** (RT10k pooled bin_var が full agg 水準保持、LOB との 5x gap は sample size では説明不能)
- **S5.6 = H_artifact_negated_strong** (orderVolume 弾力性 ε(4x) = 0.254、MMFCN は副次的供給源)
- → Phase 2 主要 finding (仮説 A 単純版反証 + 仮説 A revised + lifetime persistence primary evidence) は方法論的に頑健、S6 進行可

### 0.2 仮説 A revised (S5 で浮上、本 S6 の test 対象)

S5 pooled bin_var_slope 6 条件:

| 条件 | pooled bin_var_slope | 意味 |
|---|---:|---|
| C0u | −0.4036 | aggregate uniform baseline |
| C0p | −0.2879 | aggregate Pareto baseline |
| C2 | −0.0593 | LOB uniform |
| C3 | −0.1264 | LOB Pareto (funnel 弱、F1) |
| C2_A1 | −0.3071 | LOB uniform + q固定 → **C0u 側に大きくシフト** |
| C3_A1 | −0.0901 | LOB Pareto + q固定 → **C3 側のままほぼ動かず** (q を切っても funnel structure 動かない) |

**仮説 A revised**: 「Pareto LOB (C3) では agent が長寿命なので、初期 Pareto wealth distribution が refresh されずに persist し、その wealth-tail structure が funnel attenuate (= LOB Pareto で bin_var が浅くなる) の dominant 因子になっている」。q ablation (A1) では切れない経路。

### 0.3 GLOSSARY の A3 定義 + S5_diff の S6 描写との整合 (重要)

**GLOSSARY** (`experiments/YH006_1/GLOSSARY.md` §Ablation):
- **A3**: agent が `τ_max` ステップ生存したら強制交代 (寿命上限)
- 検証対象: 「LOBでの長寿命・wealth persistence が F1 に必要か」
- 較正: `τ_max` = C3 の agent lifetime 中央値 `L_50` × 0.5

**S5_diff (`stage_S5_diff.md`) の S6 描写**:
> design point は **C3 の initial wealth distribution を C2 と同じ uniform に置換** (q dynamics は C3 のまま残す)

→ これは GLOSSARY の A3 (lifetime cap) とは別物。なお「C3 を uniform wealth init で再走する」のは **すでに C2 と同等** (`data/C2/` 100 trial 完走済) であり、新規 sim 不要。S5_diff の当該記述は「A3」ラベル誤用 + 既存 data 軽視の誤り。

**本 S6 plan の方針**: **GLOSSARY の A3 定義 (lifetime cap τ_max) を採用**、これが仮説 A revised の「persistence dominant」claim に対する最も適切な direct test:
- C3 → C3_A3: 強制的に agent を `τ_max` step で交代させ、wealth persistence の timeline を破壊
- もし C3_A3 の pooled bin_var が C0u/C2_A1 側 (≈ −0.31〜−0.40) にシフトするなら → persistence が F1 機構の中核 = **仮説 A revised 確定**
- もし C3_A3 が C3 のまま動かない (≈ −0.13) なら → persistence は中核でない、別 mechanism (e.g., Pareto wealth distribution そのものの static effect) が dominant

### 0.4 KPI L3 (GLOSSARY 既定義) の本 stage 操作化

GLOSSARY L3:
> A3 ablation でも部分縮小 (≥30%) + lifetime・wealth persistence 中間予測が仮説 A と整合 → chain 全体の検証

本 plan での具体判定:
- **shrinkage ratio** = |A3_interaction| / |S3_interaction| ≤ 0.7 (= 30% 以上縮小)
- **shrinkage CI** (`S3_interaction − A3_interaction` の bootstrap CI) が 0 を含まない
- 5 主指標で PASS 件数を集計
- **補助 (中間予測整合性)**: A3 で `wealth_persistence_rho` (S3 で C3 = −0.011) が変化するか、`forced_retire_rate` が C3 (0.0003) から大きく上昇するか (lifetime cap は強制退場を増やすはず)

**成功条件の限定 (Yuito review 2026-06-07 P4)**: lifetime 分布の変化 (`forced_retire_rate`↑、`p25 lifetime`↓ 等) は **manipulation check であって成功条件ではない** — cap したら lifetime が cap されるのはトートロジー。claim できる因果は「**凍結 tail を除くと funnel が戻る** (bin_var_slope が agg 水準へ寄る) = 凍結 tail が funnel を弱める原因」のみ。また τ_max (p25 ベース 121) が S5.7 shake-out 帯 [0,250] と重なるのは「同じ C3 lifetime 分布の下位 tail 特徴量どうし」で construction 上相関しているだけ — 独立な機構の alignment として売らない (examiner は独立性を突く)。

S6 で interaction が **部分縮小** で十分 (L2 は 50% 縮小要求だった、L3 は 30% で OK) — chain validation は完全因果特定より緩い基準。

### 0.5 Phase 1 後方互換拡張 (S4 §0.4 同 protocol 継承)

S2/S4 で確定済の Phase 2 全体ルール:
> Phase 1 への後方互換拡張は許容、動作変更は禁止

本 S6 で同 protocol で 1 箇所追加 (S4 と類似):
- `experiments/YH006/speculation_agent.py::SpeculationAgent` に **method `_should_force_retire(self) -> bool` を新規追加**
  ```python
  def _should_force_retire(self) -> bool:
      return False   # default: 既存挙動 (lifetime cap なし)
  ```
- 既存 `step()` ループ内の breaking 条件に `if self._should_force_retire(): self._force_retire(); return` を追加
- default 経路は完全に既存挙動と bit-一致
- 既存 Phase 1 test 全 pass を §3.1 で確認

A3 subclass `LifetimeCapSpeculationAgent` は `_should_force_retire` を override:
```python
def _should_force_retire(self) -> bool:
    return (self.current_step - self.birth_step) >= self.tau_max
```

baseline (`C3` を `lifetime_cap=False` で再走) は既存挙動と bit-一致するはず (`data/C3/trial_1000.parquet` と sha256 一致を sanity check)。

---

## 1. S6 の目的

(a) **A3 ablation の wiring 確定**: `_should_force_retire` hook (Phase 1) + `LifetimeCapSpeculationAgent` subclass + dispatcher (run_experiment.py / run_lob_trial / parallel.py) を組み、smoke + determinism guard で動作保証

(b) **τ_max 較正**: C3 の agent lifetime 中央値 `L_50` × 0.5 を確定。具体 candidate と選択は §3.3

(c) **C3_A3 × 100 trial 完走**: Mac 側で 100 LOB trial、parquet × 400 ファイルを生成

(d) **L3 判定**: 5 主指標 × A3 vs S3 baseline の shrinkage を bootstrap CI 付きで報告、PASS 件数を出す。pooled bin_var_slope の C3_A3 値が C0u/C2_A1 側にシフトするか確認 (仮説 A revised 直接 test)

(e) **lifetime / wealth persistence 中間予測の整合**: A3 で `forced_retire_rate`↑、`wealth_persistence_rho` 変化、`p25 lifetime` ↓ などが起きるかを確認 (chain validation 補強)

---

## 2. 入力

### 2.1 既存資源 (流用、新規実装は最小限)

- `experiments/YH006/speculation_agent.py`: `_should_force_retire` hook を追加 (§0.5、本 stage で Phase 1 を編集する唯一の箇所)
- `code/sg_agent.py::WInitLoggingSpeculationAgent` (S2 で実装、A3 subclass の親)
- `code/sg_agent.py::QConstSpeculationAgent` (S4 で実装、A3 と直交、参照のみ)
- `code/run_experiment.py::run_lob_trial` (S3/S4/S5.6 で実装、`tau_max` kwarg 追加)
- `code/parallel.py::run_parallel_trials` (S2/S4/S5.6 で実装、`tau_max` kwarg 追加)
- `code/aggregate_ensemble.py::aggregate_ensemble_summaries` (流用)
- `code/analysis.py::bin_variance_slope_pooled` (流用)
- `code/stats.py::bootstrap_ci` (流用)
- `data/ensemble_summary.parquet` (600 行、本 stage で 700 行に拡張)
- `outputs/tables/tab_S3_interaction.csv` / `tab_S5_*.csv` (L3 判定の baseline)

### 2.2 パラメタ (Phase 1 と同一 + 新規 tau_max)

`config.py::CONDITIONS["C3_A3"]` (S2 で placeholder 定義済):
- `world="lob"`, `q_rule="wealth"`, `lifetime_cap=True`
- `wealth_mode`: pareto

LOB session params は `LOB_PARAMS` (S3/S5/S5.6 と同一)。

**新規**: `tauMax = <calibrated>` を `cfg["SGAgents"]["tauMax"]` に注入、`LifetimeCapSpeculationAgent.setup` で読む。

### 2.3 τ_max 較正の方針 (§3.3)

GLOSSARY: `τ_max = L_50 × 0.5` (C3 の agent lifetime 中央値の半分)。

S3 lifetime stats (C3, T=1500):
- `lifetime_median_mean` = 1485.5 (T=1500 にほぼ張り付き、censoring 72%)
- `conditional_median` = 39 (uncensored sample のみ median、退場 agent の典型 lifetime)
- `p25 lifetime` = 241 (全 sample の 25 percentile)
- `agent_lifetime_mean` (S5.6 集計より) ≈ 950 step

「L_50」をどう取るかで τ_max が大きく変わる:

| L_50 解釈 | L_50 値 | τ_max = L_50 × 0.5 | 想定 effect |
|---|---:|---:|---|
| (a) trial-level lifetime_median (T 張り付き) | 1485.5 | 743 | 弱 cap、agent の半数程度しか強制退場対象にならない |
| (b) conditional median (uncensored 退場 agent の median) | 39 | 20 | 超強 cap、毎 trial ~75 世代の agent 入れ替わり |
| (c) p25 (生存分布の 25 percentile) | 241 | 121 | 中強 cap、agent の ~大多数を ~120 step で強制交代 |
| (d) agent_lifetime_mean (全 agent の生涯平均) | ~950 | ~475 | 弱 cap、cap 影響受けない agent が多数 |

**Primary 採用候補**: **(c) p25 ベース、τ_max = 121** (本 plan v1 提案)。理由:
- 「L_50」は agent の **生死動態を代表する尺度** であるべきで、T 張り付き trial-level median (a) は不適 (censoring artifact)
- conditional median (b) は退場した少数 agent の動態で、生存している majority の動態は反映しない
- p25 は「全 agent の 4 分の 1 がいつまでに退場するか」の指標 = 生存分布全体の特性に対応
- p25 × 0.5 = 121 step は C3 退場 agent の typical lifetime に近く、persistence break として強すぎず弱すぎない

**Sanity**: `t_max` を (a) (b) (d) でも計算し `logs/S6_tau_max_calibration.json` に並記、Yuito 確認後 (c) を採用 / 別値選択を確定。

---

## 3. 作業項目

### 3.1 Phase 1 hook 追加 + Phase 1 test 再走 (S6、Windows)

実装手順:
1. `experiments/YH006/speculation_agent.py`: `_should_force_retire` method 追加 + `step()` ループに hook 呼び出し (§0.5)
2. Phase 1 test 全再走:
   - Windows: `cd experiments/YH005 && python -m pytest tests/test_parity.py -x` + `cd experiments/YH006 && python -m pytest tests/test_aggregate_parity.py -x` (aggregate parity)
   - Mac: LOB tests (§3.4)
3. 全 pass 確認 → `stage_S6_diff.md` に記録

実装後の期待: hook が False (default) を返す経路で既存挙動と bit-一致 (S5.6 §3.2 で実証済の hook protocol を踏襲)。

### 3.2 `LifetimeCapSpeculationAgent` 実装 (S6、Windows)

`code/sg_agent.py` に追加:

```python
class LifetimeCapSpeculationAgent(WInitLoggingSpeculationAgent):
    def setup(self, settings, accessible_markets_ids, *args, **kwargs):
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        tau_max = int(settings.get("tauMax", 0))
        if tau_max < 1:
            raise ValueError(
                f"LifetimeCapSpeculationAgent requires tauMax >= 1 in settings"
            )
        self.tau_max: int = tau_max

    def _should_force_retire(self) -> bool:
        # current_step は親クラスが PAMS の step ループから set する想定
        return (self.current_step - self.birth_step) >= self.tau_max
```

dispatcher 更新 (`run_experiment.py`):
- `run_lob_trial_smoke` / `run_lob_trial` / `run_one_trial` に `tau_max: Optional[int] = None` kwarg を追加
- `is_ablation_a3 = cond.lifetime_cap` で分岐、register に `LifetimeCapSpeculationAgent` を追加
- `cond.lifetime_cap=True` AND `tau_max is None` の場合は ValueError
- `parallel.py::_worker_run_trial` / `run_parallel_trials` も `tau_max` passthrough

注意: A3 と A1 は **直交** (`q_rule` × `lifetime_cap`)。本 plan では C3_A3 のみ実行 (A1 + A3 の combine は scope 外、必要なら S7 で別途検討)。

### 3.3 τ_max 較正 (S6、Windows、~5 分)

`code/tau_max_calibration.py` を新規実装:
1. C3 の `data/C3/lifetimes_*.parquet` × 100 を pool
2. 4 種類の L_50 candidate ((a)-(d)) を計算、× 0.5 で τ_max を出す
3. 結果を `logs/S6_tau_max_calibration.json` に永続化
4. Primary: (c) p25 ベース τ_max = 121 を確定値として書き出す

```bash
$ python -m code.tau_max_calibration
[L_50] candidates:
  (a) trial-level lifetime_median: 1485.5 → tau_max = 743
  (b) conditional median:            39.0 → tau_max =  20
  (c) p25:                          241.0 → tau_max = 121
  (d) agent lifetime mean:          950.5 → tau_max = 475
→ Primary: tau_max = 121 (基準: p25 × 0.5)
```

### 3.4 A3 smoke (S6、Mac)

Mac 側で:
```bash
cd experiments/YH006_1
git pull
# LOB Phase 1 tests を念のため再走 (S4 §3.4 と同)
python -m pytest experiments/YH006/tests/test_parity.py experiments/YH006/tests/test_roundtrip_invariants.py experiments/YH006/tests/test_wealth_conservation.py -x
# A3 smoke
python -m code.ablation_a3_ensemble --determinism-only  # smoke + guard + 終了
```

`ablation_a3_ensemble.py` の smoke で assertion:
- `len(agents_df) >= 100` (force-retire で agent 数が増える、最終的に >= 100、原典 N_sg と同期)
- 各 agent の lifetime が `tau_max + warmup_steps` 以下 (cap が効いている)
- `lifetime_capped` 列が True を持つ row が多数 (S6 では半数以上の agent が cap 退場)

assertion fail → §5 stop trigger。

### 3.5 Determinism guard (S6、Mac)

S3/S5 と同 pattern:
- C3_A3 seed=1000 を 2 回独立 run、4 parquet sha256 比較 + rt_df semantic 比較
- bit-一致 or semantic-一致 で PASS

subclass の `tau_max` 注入が PAMS 内部の RNG 消費順を変えていないか確認 (S4 で同 protocol で実証済)。

**重要**: A3 で agent が早期退場 (~τ_max 後) → 新規 agent が substitute される。S2 で実装済の substitute 経路が cap-induced retirement でも動作することを smoke + determinism で確認。

### 3.6 A3 ensemble 100 trial (S6、Mac)

```bash
cd experiments/YH006_1
python -m code.ablation_a3_ensemble
# (default: --conds C3_A3 --n-trials 100、tau_max は JSON から auto)
```

新規 script `code/ablation_a3_ensemble.py` (~120 行、`ablation_ensemble.py` をテンプレートに):
- `ACTIVE_CONDS = ["C3_A3"]`
- `tau_max` を `logs/S6_tau_max_calibration.json` から auto-load
- A1 と同 schema の 4 parquet を `data/C3_A3/` に出力

**runtime 見積**:
- S3 LOB 1 trial = 145-600 秒 (mean ~410 秒)
- A3 は agent 入れ替えが頻発 → PAMS substitute hook が多発、~1.5-2x の overhead 想定 = mean 600-800 秒/trial
- 100 trial × 8 worker 並列 = ~2-3 時間

データサイズ: S3 LOB は C3 ~7.8 MB / cond、A3 も同程度。git 直 commit (S3/S5 と同パターン)。

### 3.7 Windows aggregation + L3 判定 (S6)

Mac → Windows 転送後:
```bash
cd experiments/YH006_1
git pull
python -m code.aggregate_ablation_a3_summary
```

`aggregate_ablation_a3_summary.py` の処理:
1. integrity check (C3_A3 400 parquet、sample で lifetime ≤ tau_max を assertion)
2. ensemble_summary.parquet を **600 → 700 行** に拡張 (C0u/C0p/C2/C3/C2_A1/C3_A1/C3_A3)
3. Pooled bin_var_slope を 7 条件すべて計算、特に C3_A3 と C2/C2_A1/C0u の比較
4. A3 interaction = `(C3_A3 − C2) − (C0p − C0u)` を 5 metrics × trial-level で bootstrap CI 計算
5. **Shrinkage** = `S3_interaction − A3_interaction` を trial-level で算出、bootstrap CI
6. **L3 判定** per metric:
   - shrinkage ratio ≤ 0.7 (= 30% 以上縮小)
   - shrinkage CI が 0 を含まない
   - 両 satisfy で `L3_pass=True`
7. **中間予測整合性チェック**:
   - `forced_retire_rate` C3_A3 vs C3 が **5x 以上上昇** (cap で強制退場が支配的になるはず)
   - `wealth_persistence_rho` の方向性 (uniform-like に近づくか)
   - `p25 lifetime` C3_A3 が **τ_max 付近** に集中 (cap effect 視覚的確認)
8. **仮説 A revised 直接 test**:
   - C3_A3 の pooled bin_var_slope が:
     - C2_A1 ≈ −0.31 / C0u ≈ −0.40 側にシフト → 仮説 A revised **確定** (persistence chain が F1 機構)
     - C3 ≈ −0.13 のまま → 仮説 A revised **fail**、別 mechanism 探索
9. 出力:
   - `tab_S6_ablation_interaction.csv` (A3 5 metrics × interaction CI)
   - `tab_S6_shrinkage.csv` (5 metrics × shrinkage + L3 判定)
   - `tab_S6_pooled_bin_var_7cond.csv` (7 条件 + 仮説 A revised judgment)
   - `tab_S6_intermediate_predictions.csv` (forced_retire / wealth_persistence / p25 lifetime)
   - `fig_S6_pooled_bin_var_7cond.png` (7 条件 bar、C3_A3 シフト先 visualize)
   - `fig_S6_ablation_shrinkage.png` (S3 vs A1 vs A3 比較)
   - `S6_summary_for_diff.json`
   - `README.md` 追記 (S6 セクション)

### 3.8 出力

| パス | 内容 |
|---|---|
| `data/C3_A3/*.parquet` × 400 | C3_A3 100 trial × 4 schema |
| `data/ensemble_summary.parquet` | 700 行 (S5 版上書き、7 condition × 100) |
| `code/tau_max_calibration.py` / `code/sg_agent.py` (LifetimeCapSG) / `code/ablation_a3_ensemble.py` / `code/aggregate_ablation_a3_summary.py` | 新規 / 拡張 script |
| `experiments/YH006/speculation_agent.py` | `_should_force_retire` hook 1 method 追加 |
| `code/run_experiment.py` / `code/parallel.py` | `tau_max` kwarg passthrough |
| `logs/S6_tau_max_calibration.json` | 較正結果 |
| `logs/runtime/{ts}_S6_*.log` | 全 ログ (Win calibration + Mac sim + Win aggregation) |
| `logs/S6_mac_summary.json` | Mac 完走サマリ |
| `logs/S6_summary_for_diff.json` | Windows aggregation key 数値 dump |
| `outputs/tables/tab_S6_*.csv` | 4 表 (§3.7) |
| `outputs/figures/fig_S6_*.png` | 2 figure (§3.7) |
| `README.md` | "Stage S6" セクション追記 |
| `plans/stage_S6_diff.md` | 提出用 diff |

### 3.9 README 追記

`## Stage S6 — A3 ablation (C3_A3) + 仮説 A revised direct test + KPI L3 判定` セクション:
- C3_A3 100 trial 完走、τ_max = (calibrated) 確定
- Pooled bin_var_slope 7 条件表 (C3_A3 のシフト先で 仮説 A revised 判定)
- A3 interaction + shrinkage + L3 判定 (PASS 件数 / 5)
- 中間予測整合性チェック結果 (forced_retire / wealth_persistence / p25 lifetime)
- 仮説 A revised の最終判定 (確定 / fail / 部分支持)
- Layer 2 timescale concern 言及継続

---

## 4. 完了条件

### Windows 側 (実装 + calibration)
- [ ] §0.5 Phase 1 hook (`_should_force_retire`) 追加
- [ ] §3.1 aggregate parity 27 件 PASS 確認 (S4/S5.6 と同 protocol)
- [ ] §3.2 `LifetimeCapSpeculationAgent` 実装 + dispatcher 更新
- [ ] §3.3 τ_max 較正完了 (= 121 候補、Yuito 承認後確定)
- [ ] commit + push (Mac が pull 可能な状態)

### Mac 側
- [ ] git pull
- [ ] §3.1 LOB Phase 1 tests 全 pass
- [ ] §3.4 A3 smoke PASS (lifetime ≤ tau_max + lifetime_capped True row 多数)
- [ ] §3.5 Determinism guard PASS (C3_A3 seed=1000 × 2)
- [ ] §3.6 A3 100 trial 完走 (400 parquet)
- [ ] git commit + push

### Windows 側 (Mac 後)
- [ ] git pull
- [ ] `aggregate_ablation_a3_summary.py` 実行 → 700 行 ensemble_summary、4 表 + 2 figure
- [ ] §3.7 L3 判定 + 仮説 A revised 判定を `stage_S6_diff.md` で報告
- [ ] README §S6 追記
- [ ] Yuito レビュー待ち

---

## 5. Yuito 確認事項 (実装中 stop trigger + 完了後レビュー)

### 実装中の停止トリガー (発生したら停止 → Yuito 相談)

- §3.1 で aggregate parity / LOB Phase 1 tests のいずれかが fail (`_should_force_retire=False` default が既存挙動破壊)
- §3.3 τ_max 較正で候補 (a)-(d) 間で 50x 以上の乖離 → L_50 解釈の根本見直し
- §3.4 smoke で `lifetime_capped` row が 0 件 (hook が動いていない)
- §3.5 Determinism guard fail (subclass 副作用)
- §3.6 A3 100 trial で runtime > 6 hours / 条件 (S3 の 2x 超)
- §3.7 で C3_A3 pooled bin_var が **+0.5 以上** or **−2.0 以下** (理論的にあり得ない値 = 実装バグ疑い)

### 完了後 (Yuito レビュー) 確認事項

1. §0.3 で GLOSSARY の A3 (lifetime cap) を採用、S5_diff の「uniform wealth 置換」描写を誤りと判定した本 plan の判断を承認するか
2. §3.3 τ_max = 121 (p25 ベース) の選択を承認するか、(b) τ_max = 20 (より aggressive な persistence break) や (a) τ_max = 743 (弱 cap) を試すか
3. §3.7 L3 判定結果 (5 metrics 中 PASS 件数)
4. **仮説 A revised の最終判定**:
   - C3_A3 pooled bin_var が C0u/C2_A1 側 (≈ −0.31〜−0.40) → 仮説 A revised **確定**
   - C3 のまま (≈ −0.13) → 仮説 A revised **fail**、別 mechanism 探索 (S7 で別 ablation 検討、e.g., wealth distribution の static effect)
   - 中間 → 部分支持、解釈は Yuito 議論
5. 中間予測整合性 (forced_retire / wealth_persistence / p25 lifetime) が仮説 A revised の chain と一貫しているか
6. S7 (Phase 2 完了 + proposal 素材) 着手の go/no-go (S6 完了後、別 plan)
7. S1-secondary (4 条件 100 trial bootstrap CI で plan A/B 分岐判定) の優先度 (本 S6 と並走可能だが Phase 2 Limitations を厚くする stage、Yuito 判断)

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | S6 plan 初版。S5.5/S5.6 統合判定 (H_micro 強支持 + H_artifact_negated_strong) を起点に仮説 A revised の direct causal test を起案。**GLOSSARY の A3 定義 (lifetime cap τ_max forced retirement) を採用**、S5_diff の「C3 → uniform wealth 置換」描写は (1) GLOSSARY と矛盾、(2) 既存 C2 data で代替可能で新規 sim 不要、の 2 点で誤りと判定 (§0.3)。Phase 1 後方互換 protocol で `_should_force_retire` hook を SpeculationAgent に追加、`LifetimeCapSpeculationAgent` subclass で override。τ_max 較正は C3 p25 = 241 ベースで **τ_max = 121** を primary 候補、(a)-(d) の代替値も並記して Yuito 承認後確定。L3 判定 (shrinkage ratio ≤ 0.7、CI 0 跨ぎなし、5 metrics 集計) + 仮説 A revised 直接 test (C3_A3 pooled bin_var のシフト先) を §3.7 で一体実装。S7 (Phase 2 完了) と S1-secondary は本 plan scope 外、別 plan で。 |
