# Stage S2 plan v2 — aggregate baseline 100 trial ensemble + S3 LOB w_init 準備

| 項目 | 値 |
|---|---|
| Stage | S2 — aggregate ensemble (C0u/C0p × 100 trial) + LOB SG subclass 準備 |
| Status | **承認済 (Yuito 承認 v2 反映、実装着手可)** |
| 想定 runtime | 1〜2 時間 (multiprocessing 想定) |
| 新規 sim | aggregate 200 trial + LOB smoke 1 trial |

本 plan は Stage S2 のみを扱い、S3 以降の話は **意図的に混ぜていない** (Brief §0 two-step workflow)。S2 中で行う「LOB SG agent subclass の実装」は S3 への準備という位置づけで含むが、LOB 100 trial 実行は S3 の作業。

---

## v2 改訂サマリ (v1 → v2)

Yuito 承認時の 5 点修正 + 1 sub-checkpoint 追加を反映:

1. **修正 1 (§0.4.1)**: aggregate_sim の wealth_ts logging を **Phase 1 fork (Option A) 却下、Phase 1 への後方互換拡張 (Option C) 採用**。`simulate_aggregate(..., snapshot_callback: Optional[Callable] = None, log_substitutes: bool = False)` を 2 引数追加。default で既存呼び出しと bit-一致。Phase 1 test (parity test 含む) 再走全 pass を必須、結果を `stage_S2_diff.md` に記録。**Phase 2 全体で「後方互換拡張は許容、動作変更は禁止」を統一ルール化** (S5/S6 ablation でも同じ — Phase 1 にフックを追加して subclass で hook という進化余地を残す)。
2. **修正 2 (§5)**: 確認事項 #1 (Option A 承認) は moot で削除。
3. **修正 3 (lifetime 定義)**: 「初期 draw から最初の bankruptcy substitute までの step 数」CC 案は却下。両世界統一で **「agent identity がリセットされてから次のリセットまでの step 数 = 1 lifetime sample」**。1 trial で 1 agent が複数 sample を生む。**主指標は median と 90 percentile、mean は使わない** (右端 censoring の影響)。sim 終了時生存 agent は censored sample として扱う、median > T/2 なら censoring 重大 flag。
4. **修正 4 (§3.5)**: LOB smoke の完了条件を補強。RT 0 件でも smoke 完了とせず、**agent parquet に N=100 SG 全員の w_init 列が non-NaN で書き出されているか assertion で確認**。fail なら smoke 失敗、`stage_S2_diff.md` で報告。
5. **修正 5 (§3.7 wealth_ts schema)**: `is_active` 列は両世界で **恒常 True (hardcoded)**。aggregate での substitute イベント検出ロジック等は実装しない。コメントで「将来 SOSG (YH007) での agent inflow/outflow 用 reservation、Phase 2 では恒常 True」を明記。

加えて **sub-checkpoint (Yuito 追加要件、`stage_S2_diff.md` で必須 flag)**:

- `q90_q10_slope_diff` の trial 間 SD を C0u 100 trial / C0p 100 trial それぞれで計算
- **SD > 0.3 なら警告フラグ** (S1-secondary で interaction 計算が機能しない可能性)、別 funnel 直接指標 (例: `Var(log|ΔG|)` を h 中央値で 2 分した差) への切り替えを Yuito 相談
- **SD ≤ 0.3 なら通常完了**
- S2 では計算と flag のみ、**切り替え判断は S3 完了後**

その他承認:
- worker 数: `min(os.cpu_count(), 8)` 採用
- 実装中相談トリガー (Phase 1 拡張で parity fail / 200 trial > 4 hours / Pearson SD > 0.5): すべて承認

---

## 0. Brief §6 prerequisites の S2 残部 + Yuito 指示反映

S1 で resolved な点 (Phase 1 schema, T 値, MMFCN 設定, q_i 計算箇所, forced liquidation) は省略。S2 で新たに前提確認すべき点。

### 0.1 bin variance の pooled 計算方式 (Yuito 指示 #1)

**実装**: `code/analysis.py` に `bin_variance_slope_pooled(rt_df_concat, K=15)` を追加。100 trial 分の RT を **先に concat してから** 1 回 bin slicing + Var(log\|ΔG\|) 計算 + Spearman ρ を計算。trial-level の `bin_variance_slope` (= 既存の関数を 1 trial に対し計算) は補助で `ensemble_summary.parquet` に保存、**主指標は pooled 値**。

**S2 での出番**: aggregate 100 trial pooled で動作確認、bin あたり sample 数の桁感を記録。LOB との interaction は S3 後。

### 0.2 timescale interaction diff の sub-KPI 明文化 (Yuito 指示 #2)

**定義**: `interaction_second_half − interaction_first_half`。tentative S1 では Pearson で +0.10 (= −0.316 − (−0.218)) の **後半強化** 観察、100 trial で残るかを S1-secondary で確定、シナリオ δ (後半縮小) と区別する基準値。

**S2 での出番**: aggregate のみ → interaction 自体は計算不可。trial-level の前半/後半 5 主指標を計算し、`ensemble_summary.parquet` に `rho_p_first_half`, `rho_p_second_half`, `rho_s_first_half`, `rho_s_second_half` などを保存 (Brief §2.4 schema)。

### 0.3 LOB SG agent subclass による w_init logging 実装 (Yuito 指示 #3)

**実装**: `code/sg_agent.py` に `WInitLoggingSpeculationAgent(SpeculationAgent)` を新規 subclass。

```python
from speculation_agent import SpeculationAgent  # YH006/ から import (read-only 流用)

class WInitLoggingSpeculationAgent(SpeculationAgent):
    """w_init (sg_wealth at setup completion) を agent attribute に永続化。"""

    def setup(self, settings, accessible_markets_ids, *args, **kwargs):
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        self.w_init: int = int(self.sg_wealth)
```

**S2 での出番**: subclass 実装 + `code/adapter.py` で agent-level parquet に w_init 列を書く経路。LOB smoke 1 trial で wiring 確認 (修正 4: agent parquet に 100 SG 全員の w_init 列 non-NaN を assertion)。LOB 100 trial 本番は S3。

### 0.4 修正 1 — Phase 1 aggregate_sim.py の後方互換拡張 (Option C)

**変更箇所**: `experiments/YH006/aggregate_sim.py::simulate_aggregate()` のシグネチャに 2 引数追加。

```python
def simulate_aggregate(
    N, M, S, T,
    B=9, C=3.0, seed=42, p0=100.0,
    history_mode="endogenous",
    decision_mode="strategy",
    random_open_prob=0.5,
    order_size_buckets=(50, 100),
    wealth_mode="uniform",
    pareto_alpha=1.5,
    pareto_xmin=9,
    # ↓ 修正 1 で追加 (Phase 2 用、default は既存挙動と bit-一致)
    snapshot_callback: Optional[Callable[[int, np.ndarray], None]] = None,
    log_substitutes: bool = False,
) -> dict:
```

**動作仕様**:
- `snapshot_callback`: `None` (default) → 何もしない。Phase 2 から渡す場合は `(t, w_array)` を受けて caller が wealth_snapshots に追記。simulate ループ内で `if snapshot_callback is not None and t % (T // 10) == 0: snapshot_callback(t, w.copy())` を実行。**default 経路は invariant**。
- `log_substitutes`: `False` (default) → 何もしない。`True` の場合、bankruptcy substitute 発生時に `(t, agent_idx, dead_w, new_w)` を返り dict の `substitute_events` キーに追記。default では返り dict に `substitute_events` キーは出ない (= 既存テストの dict キーチェックは無変更で pass)。
- 既存の RNG 消費順は **完全に保存**: callback / logging は副作用のみで RNG state を消費しない。

**§4.4 統一ルール**: Phase 2 全体で「Phase 1 への後方互換拡張は許容、動作変更は禁止」。S5/S6 で ablation 実装時にも同じルールに従う (= ablation 用フックを Phase 1 に追加して subclass で hook 等)。

**必須検証**:
1. Phase 1 既存 test (`experiments/YH005/tests/test_parity.py`、`experiments/YH006/tests/test_aggregate_parity.py`、その他 YH006 内 test) を全部再走 → 全 pass を確認
2. 結果を `stage_S2_diff.md` に記録 (どの test を何件走らせて何件 pass したか、所要時間)
3. fail があれば実装停止 → Yuito 相談

### 0.5 並列化と再現性 (Brief §3 S2 並列化注意 + §4.2 reproducibility)

trial 単位 multiprocessing。**worker 数 default は `min(os.cpu_count(), 8)`** (Yuito 承認 #2)、`--n-workers` で上書き可。各 worker は独立 process で `numpy.random.Generator(seed)` を seed のみで構築 → bit-一致再現。Python `random` は使わない (§4.2)。

**Determinism guard** (§4.2): C0u seed=1000 を 2 回独立に実行 (2 worker)、両 ensemble_summary 行が完全一致 (np.array_equal per indicator) することを CI チェック、`logs/runtime/{ts}_S2_determinism_guard.log` に記録。

### 0.6 ストレージ見積もり

| 出力種類 | 単位 | 100 trial × 2 条件 |
|---|---:|---:|
| RT parquet (Brief §2.1) | ~ 24 MB / trial | 4.8 GB |
| agent parquet (§2.2) | ~ 10 KB / trial | 2 MB |
| wealth_ts parquet (§2.3) | ~ 30 KB / trial (T/10 = 10 snapshot × N=100) | 6 MB |
| ensemble_summary (§2.4) | 1 行 / trial | < 100 KB |

**全体 ~ 4.8 GB**、`data/C0u/` `data/C0p/` 配下に gitignore 必須。

### 0.7 修正 3 — Lifetime 定義 (両世界統一)

**定義**: 「agent identity がリセットされてから次のリセットまでの step 数 = 1 lifetime sample」。

- 1 trial で 1 agent が **複数 lifetime sample** を生む (substitute されるたびに新 sample)
- aggregate: agent ID i の `substitute_events` (本 plan で Phase 1 拡張で取れる) から `(t_birth, t_next_subst)` のペアを sample。`t_birth = 0` for initial、それ以降は前 substitute の t。
- LOB: 同じ。`SpeculationAgent.substitute_events` (既存) から取れる。
- **sim 終了時生存 agent は censored sample** として記録 (lifetime = T − t_last_birth、separate flag)
- **集計**: `lifetime_median`, `lifetime_p90` を主指標、**`lifetime_mean` は使わない** (右端 censoring の影響)
- **censoring 重大 flag**: `lifetime_median > T / 2` ならば diff.md で warn (Phase 2 主目的では Kaplan-Meier 等 survival analysis は実施しない、median が信頼できなければ補助 KPI として扱う)

### 0.8 修正 5 — `is_active` schema 取扱い

`wealth_ts` parquet の `is_active` 列 (Brief §2.3) は **両世界で hardcoded `True`**。aggregate での substitute イベント検出ロジック等は実装しない (無駄な複雑さを避ける)。schema には残す、コメントで以下を記載:

```python
# is_active: 将来 SOSG (YH007) での agent inflow/outflow 用 reservation 列。
# Phase 2 では恒常 True (substitute は同 agent_id を継続使用するため、
# wealth_ts の time-series 内では agent identity の出入りが発生しない)。
```

---

## 1. S2 の目的

(a) **aggregate baseline (C0u/C0p) の 100 trial ensemble を確定**: seed = 1000..1099 で各条件 100 trial 実行、`ensemble_summary.parquet` に集約。aggregate side の seed 安定性 + tentative S1 の単 trial 値が ensemble 平均に近いか確認。

(b) **S3 への前準備**: LOB SG agent subclass (`WInitLoggingSpeculationAgent`) を実装、smoke 1 trial で w_init logging wiring を assertion 付きで動作確認。LOB 100 trial 本番は S3。

(c) **共通 infrastructure 整備**: `config.py` で全 7 条件の spec 化、`run_experiment.py` で `--cond {C0u|C0p|...}` `--seed {int}` `--out {path}` の単 trial CLI、`parallel.py` で trial 単位 multiprocessing wrapper、`adapter.py` で Phase 2 schema への変換。

(d) **Phase 1 後方互換拡張 (修正 1)**: aggregate_sim.py に snapshot_callback と log_substitutes 引数追加、Phase 1 test 全 pass で動作不変を保証。

S2 のみで Stage 完了。S3 (LOB ensemble) は別 plan で Yuito 承認後。

---

## 2. 入力

### 2.1 既存資源 (流用)

- `experiments/YH006/aggregate_sim.py`: 修正 1 で 2 引数追加 (本 S2 で Phase 1 を編集する **唯一の箇所**)
- `experiments/YH006/speculation_agent.py`: `WInitLoggingSpeculationAgent` の親クラス (read-only)
- `experiments/YH006/configs/_base.py`: MMFCN + Market 設定 (S2 では LOB smoke のみで使用、read-only)
- `experiments/YH006/yh006_to_yh005_adapter.py`: Phase 2 adapter の参考 (read-only)
- `experiments/YH006_1/code/analysis.py`: S1 で実装済の指標群 (S2 で `bin_variance_slope_pooled` を追加)
- `experiments/YH006_1/code/stats.py`: S1 で骨格実装済、S2 で実 call 開始

### 2.2 パラメタ (Phase 1 と完全一致、SPEC §3)

aggregate (C0u/C0p):
- `N=100, M=5, S=2, T=50000, B=9, C=3.0, p0=100.0`
- `wealth_mode`: C0u → uniform、C0p → pareto (α=1.5, xmin=9)
- seed: 1000, 1001, ..., 1099

LOB (C2/C3、smoke のみ):
- Phase 1 と同じ MMFCN + SG block (但し SG class を `WInitLoggingSpeculationAgent` に差し替え)
- seed: 9001 (smoke、warmup=200, main=200 短縮)

---

## 3. 作業項目

### 3.1 新規 / 編集ファイル

| パス | 役割 | 推定行数 |
|---|---|---:|
| `experiments/YH006/aggregate_sim.py` (**Phase 1 編集**、修正 1) | snapshot_callback + log_substitutes 引数追加 | +約 30 |
| `code/config.py` | 全 7 条件の condition spec dict | ~120 |
| `code/sg_agent.py` | `WInitLoggingSpeculationAgent(SpeculationAgent)` subclass | ~25 |
| `code/adapter.py` | aggregate / LOB sim 結果 → Phase 2 §2.1/§2.2/§2.3 parquet schema | ~280 |
| `code/run_experiment.py` | 主 runner: `--cond` `--seed` `--out` で 1 trial 実行 + 3 種 parquet 出力 | ~200 |
| `code/parallel.py` | trial 単位 multiprocessing wrapper、`--n-workers` 引数 | ~100 |
| `code/aggregate_ensemble.py` | S2 主スクリプト: C0u/C0p × seed 1000..1099 を並列実行 → ensemble_summary 生成 | ~250 |
| `code/analysis.py` (既存編集) | `bin_variance_slope_pooled` 関数追加 | +約 25 |

### 3.2 Phase 1 拡張 (修正 1) → 全 test 再走

実装手順 (順次):

1. `experiments/YH006/aggregate_sim.py` に snapshot_callback / log_substitutes を追加 (default 経路は完全に既存挙動)
2. 既存 test 再走:
   - `experiments/YH005/tests/test_parity.py` (run_reference vs simulate の bit-parity)
   - `experiments/YH006/tests/test_aggregate_parity.py` (uniform mode YH005 simulate との bit-parity 4 seeds + Pareto determinism + uniform-Pareto divergence)
   - `experiments/YH006/tests/test_parity.py` (LOB seed 同一決定論)
   - `experiments/YH006/tests/test_roundtrip_invariants.py`
   - `experiments/YH006/tests/test_wealth_conservation.py`
3. **全 test pass を確認**、pass 件数 + 所要時間を `stage_S2_diff.md` に記録
4. fail があれば実装停止 → Yuito 相談

### 3.3 100 trial 実行 (aggregate のみ)

| 条件 | seed range | n_trials | 単 trial runtime (S1 実測) |
|---|---|---:|---:|
| C0u | 1000..1099 | 100 | ~30 s |
| C0p | 1000..1099 | 100 | ~30 s |

並列化: `min(os.cpu_count(), 8)` worker (Windows env では 8 想定)、想定 30s × 200 / 8 ≈ 750 s ≈ 12.5 min (ideal)。実測は 1.5-2x 想定 = 20-25 min。

各 trial で 3 種 parquet:
- `data/C0u/trial_{seed:04d}.parquet` (RT 単位、§2.1)
- `data/C0u/agents_{seed:04d}.parquet` (agent 単位、§2.2)
- `data/C0u/wealth_ts_{seed:04d}.parquet` (wealth time-series、§2.3、`is_active` は hardcoded True)

同形で C0p。

### 3.4 ensemble_summary 計算

各 (cond, seed) trial に対し Brief §2.4 schema の 1 行を計算、`data/ensemble_summary.parquet` に append。aggregate trial で計算可能な列:

| 列 | aggregate で計算 |
|---|---|
| cond, seed | ✓ |
| n_round_trips | ✓ |
| rho_pearson, rho_spearman, tau_kendall | ✓ (S1 既存) |
| rho_p_first_half/second_half, rho_s_first_half/second_half | ✓ (S1 既存、Yuito 指示 #2 対応) |
| bin_var_slope (trial-level、補助) | ✓ |
| q90_q10_slope_diff | ✓ (S1 既存) |
| corr_w_init_h | ✓ (修正 1 で w_init available) |
| skew_high_minus_low | ✓ (S1 既存) |
| hill_alpha | ✓ (S1 既存、ΔG 分布の Hill α) |
| **lifetime_median, lifetime_p90** (修正 3) | ✓ (substitute_events から計算、censored sample 含む) |
| wealth_persistence_rho | ✓ (corr(w_init, w_final) Spearman) |
| forced_retire_rate | ✓ (= num_substitutions / (N × T)) |
| corr_winit_wt_T1, ..., T10 | ✓ (wealth_ts から計算) |
| n_lifetime_capped | aggregate では 0 (τ_max 無し、A3 ablation でのみ非ゼロ) |

**lifetime_mean は使わない** (修正 3、右端 censoring の影響)。代わりに `lifetime_median` と `lifetime_p90` を採用。

### 3.5 LOB SG agent subclass smoke (修正 4 で補強)

`WInitLoggingSpeculationAgent` を実装後、C3 setup × seed=9001 × warmup=200 / main=200 で 1 trial 実行。

**完了条件 (修正 4)**:
- assertion: agent parquet に N=100 SG agent 全員の `w_init` 列が **non-NaN** で書き出されている
- assertion fail なら smoke 失敗、`stage_S2_diff.md` で報告 + 実装停止
- RT 0 件は容認 (smoke の sim 長で round-trip がほぼ生まれない可能性、しかし w_init logging が動けば smoke 完了)

実装場所: `code/_lob_smoke.py` (or `code/sg_agent_smoke.py`) に独立 script として、または `aggregate_ensemble.py` の最後に smoke step として組み込む。

**runtime**: ~5 s (短縮 smoke)。

### 3.6 pooled bin variance の S2 動作確認 (Yuito 指示 #1)

`code/analysis.py` に `bin_variance_slope_pooled(rt_df_pooled: pd.DataFrame, K: int = 15) -> float` を追加。S2 で aggregate 100 trial の RT を pool して 1 値を出し、tentative S1 (1 trial) の点推定 −0.20 〜 −0.23 と桁が同じか確認 (LOB との interaction は S3 後)。

`outputs/tables/tab_S2_aggregate_summary.csv` に pooled 値と 100 trial の trial-level mean ± 95% CI を併記。

### 3.7 Determinism guard (§4.2)

S2 完了直前に C0u seed=1000 を **2 回独立に** 実行 (2 つの worker が独立 process で同 seed)、両方の `ensemble_summary` 行が完全一致 (`np.array_equal` per indicator) することを CI 的にチェック。結果を `logs/runtime/{ts}_S2_determinism_guard.log` に記録。

### 3.8 Sub-checkpoint (Yuito 追加要件)

`stage_S2_diff.md` で以下を必ず flag:

- `q90_q10_slope_diff` の trial 間 SD を C0u 100 trial / C0p 100 trial それぞれで計算
- **SD > 0.3** → 警告フラグ。S1-secondary で interaction 計算が機能しない可能性、別 funnel 直接指標 (例: `Var(log|ΔG|)` を h 中央値で 2 分した差) への切替を Yuito 相談、と diff.md に記載
- **SD ≤ 0.3** → 通常完了
- **本 S2 では計算と flag のみ、切り替え判断は S3 完了後**

### 3.9 出力

| パス | 内容 |
|---|---|
| `data/C0u/trial_*.parquet` × 100 | RT 単位 (~ 24 MB / trial) |
| `data/C0u/agents_*.parquet` × 100 | agent 単位 (~ 10 KB / trial) |
| `data/C0u/wealth_ts_*.parquet` × 100 | wealth time-series (~ 30 KB / trial) |
| `data/C0p/...` × 100 | 同上 |
| `data/ensemble_summary.parquet` | 200 行 (C0u 100 + C0p 100) |
| `outputs/tables/tab_S2_aggregate_summary.csv` | 条件 × 指標の mean ± 95% CI + pooled 値 |
| `outputs/figures/fig_S2_aggregate_distributions.png` | 各指標の trial-level violin plot (条件別) |
| `logs/runtime/{ts}_S2_*.log` | 各 trial の runtime / 統計ログ |
| `logs/runtime/{ts}_S2_determinism_guard.log` | C0u seed=1000 × 2 回完全一致確認 |
| `data/_smoke/lob_w_init_smoke_agents.parquet` | LOB smoke 1 trial の agent parquet (w_init logging 動作確認用) |

### 3.10 README 追記

`README.md` に S2 結果サマリを追記:
- 200 trial completion 状況
- ensemble mean ± 95% CI for 5 主指標 + plan B 先取り (aggregate 側のみ)
- pooled bin variance の桁感
- timescale 前半/後半の aggregate 側 mean (interaction 計算は S3 後)
- LOB SG subclass smoke 結果 (w_init logging assertion pass)
- lifetime_median / lifetime_p90 + censoring flag 有無
- Sub-checkpoint: q90_q10_slope_diff SD と警告 flag
- Layer 2 timescale concern の言及継続

---

## 4. 完了条件

- [ ] 修正 1: Phase 1 `experiments/YH006/aggregate_sim.py` への 2 引数追加完了、Phase 1 既存 test 全 pass、結果を `stage_S2_diff.md` 記録
- [ ] `code/config.py` 完成、7 条件全て (C0u/C0p/C2/C3/C2_A1/C3_A1/C3_A3) の spec が dict で定義 (S2 で active なのは C0u/C0p のみ、他は placeholder OK)
- [ ] `code/sg_agent.py::WInitLoggingSpeculationAgent` 完成、smoke で w_init non-NaN assertion pass (修正 4)
- [ ] `code/adapter.py` 完成、aggregate / LOB の両 sim 結果から Brief §2.1/§2.2/§2.3 parquet schema を produce
- [ ] `code/run_experiment.py` 完成、CLI で `--cond C0u --seed 1000 --out path` で単 trial 実行
- [ ] `code/parallel.py` 完成、`min(os.cpu_count(), 8)` 自動 + `--n-workers` 上書き
- [ ] `code/aggregate_ensemble.py` で C0u 100 trial 完走、`data/C0u/{trial,agents,wealth_ts}_*.parquet` × 100 が出力
- [ ] 同 C0p 100 trial 完走
- [ ] `data/ensemble_summary.parquet` に 200 行 (C0u 100 + C0p 100) 存在、Brief §2.4 schema (修正 3 の lifetime_median / lifetime_p90 含む)
- [ ] `outputs/tables/tab_S2_aggregate_summary.csv` に 5 主 + plan B 指標の mean ± 95% CI + pooled bin variance が出ている
- [ ] LOB smoke 1 trial 完走、`data/_smoke/lob_w_init_smoke_agents.parquet` に N=100 SG 全員の w_init non-NaN (修正 4 assertion)
- [ ] Determinism guard 1 件 pass (C0u seed=1000 × 2 回完全一致)
- [ ] Sub-checkpoint: q90_q10_slope_diff SD を C0u/C0p で計算、SD ≤ 0.3 / > 0.3 を `stage_S2_diff.md` で flag
- [ ] `README.md` に S2 結果サマリ追記
- [ ] `plans/stage_S2_diff.md` を提出、Yuito レビュー待ち状態

---

## 5. Yuito 確認事項 (実装中の停止トリガーのみ)

v1 の確認事項 5 点は v2 で全 resolve (修正 1-5 と worker 数承認)。本 plan では **実装着手後の停止トリガー** のみ列挙:

実装中の Yuito 相談トリガー (発生したら停止して相談):
- 修正 1 の Phase 1 拡張で **既存 test fail** (parity test 含む)
- 200 trial 完走中に **runtime > 4 hours** (見積もりの 8 倍超)
- ensemble_summary の **Pearson trial 間 SD > 0.5** (主指標分散異常)

それ以外は独断で実装完走、`stage_S2_diff.md` で報告。

実装後 (Yuito レビュー) 確認事項:
1. q90_q10_slope_diff SD の警告 flag 有無 (sub-checkpoint)
2. lifetime_median の censoring 重大 flag (修正 3)
3. ensemble values の桁感が tentative S1 単 trial 値と整合しているか
4. S3 plan 着手の go/no-go

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 | Stage S2 plan 初版、Yuito 3 点指示 (bin variance pooled / timescale diff sub-KPI / LOB w_init logging) を §0 で組み込み、aggregate 100 trial × 2 conditions、新規 7 ファイル、要 Yuito 確認 5 点 |
| v2.0 (本書、承認版) | Yuito 5 点修正 + 1 sub-checkpoint 反映: (1) Phase 1 fork 却下、後方互換拡張 Option C 採用 + Phase 2 全体ルール化 / (2) 確認事項 #1 削除 / (3) lifetime 定義を「agent identity reset 間隔 = 1 sample」両世界統一、median + p90 主指標、mean 不採用、censored sample 扱い / (4) LOB smoke 完了条件を assertion 補強 / (5) is_active 列を hardcoded True、SOSG reservation コメント / (sub-checkpoint) q90_q10_slope_diff SD 警告 flag。worker 数 `min(os.cpu_count(), 8)` 承認、3 停止トリガー承認。 |
