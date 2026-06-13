# Stage S5.6 plan v1 — MMFCN 1 パラメタ sensitivity scan: 約定 artifact 検出

| 項目 | 値 |
|---|---|
| Stage | S5.6 — LOB C3 setup で MMFCN の orderVolume を 4 設定 × 2 trial scan、artifact 疑惑切り分け |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Mac 4-8 時間 (sim) + Windows 30 分 (集計 + 判定) |
| 新規 sim | LOB 8 trial (C3 setup × MMFCN scan 4 設定 × seed=1000,1001 = 8 trial) |
| 前提 | S5 完走済 (`data/C3/` 100 trial、`tab_S5_*` で仮説 A revised が浮上)、S4 で `run_lob_trial` + `parallel.py` 動作確認済 |

本 plan は **S6 (A3 ablation) 着手前のサニティチェック**。S5.5 (aggregate sub-sample 再分析) と並走、両 stage 完了後に S6 進行 / refactor を Yuito 判定 (本 plan §5)。

---

## 0. S5.6 着手前提と Yuito 指摘 2 の整理

### 0.1 Yuito 指摘 2 (本 plan 起点)

S5 完了時点の方法論的疑念:

> Phase 2 の LOB 設定 (PAMS + MMFCN 30 agent × orderVolume 30) で、約定をしづらくさせる artifact が混入している可能性。SG agent の RT 数が trial 当たり 1,000 程度しかない / forced retirement rate が ~0.0001-0.0003 (aggregate 0.0021 の 1/10) という観測値は、MMFCN 側の liquidity 設定が SG の市場注文を吸収しきれず約定 starve させているせいかもしれない。仮説 A 単純版反証 / 仮説 A revised の浮上自体が、MMFCN 設定の副産物に起因する可能性がある。

**実測値 (S3 / S5 から抜粋)**:
- C3 (LOB Pareto): per-trial n_rt ≈ 1,080、censoring 率 72.0%、forced_retire_rate 0.0003、lifetime_median 1485.5 (T=1500 に張り付き)
- C2 (LOB Uniform): per-trial n_rt ≈ 879、censoring 率 90.1%、forced_retire_rate 0.0001、lifetime_median 1500 (T 完全張り付き)

→ SG が「ほぼ約定していない」状態は **仮説 A の中間予測 evidence** として positive 解釈されてきたが、Yuito の指摘により **MMFCN 設定の design choice (orderVolume=30, numAgents=30) に対する sensitivity 未検証** という穴が露呈。これを scan で埋める。

### 0.2 仮説 / 判定対象

S5.6 で **検証する 2 つの対立仮説**:

| 仮説 | 内容 | S5.6 が真ならどう支持される |
|---|---|---|
| **H_artifact_mmfcn** (MMFCN bottleneck artifact) | 現行 MMFCN 設定 (orderVolume=30) は SG の市場注文を fully absorb するには liquidity 不足。約定難 → 長寿命 → wealth persist という Phase 2 観察は MMFCN 不足の副産物 | orderVolume を 2x → SG per-trial RT 数が **1.8x 以上** に増える (= MMFCN が bottleneck だった) |
| **H_artifact_negated** (MMFCN は bottleneck でない) | 現行設定 で MMFCN は十分な liquidity を提供しており、SG の低 RT 数 / 長寿命は SG 内在の strategy + wealth dynamics 由来 | orderVolume を 2x にしても SG per-trial RT 数が **1.2x 以下** (= 既に liquidity 十分) |

判定境界 (本 plan §3.5):
- scan で RT 数 × 1.8 以上 (orderVolume 0.5x → 4x で大きく単調変化) → **H_artifact_mmfcn 強支持、Phase 2 結論を refactor**
- scan で RT 数 × 1.2 以下 (orderVolume 全範囲で flat) → **H_artifact_negated 強支持、S6 進行**
- 中間 (1.2x < ratio < 1.8x) → 解釈保留、Yuito 議論

### 0.3 scan パラメタの選択 — orderVolume を primary

MMFCN config (`experiments/YH006/configs/_base.py::_FCN_AGENTS`):
```python
"numAgents":    30,
"orderVolume":  30,   # B-1: 30 FCN × 30 = 900 shares/step. SG Pareto tail (q_max~240) も吸収
```

**Primary**: `orderVolume` を scan
- 直接的に「1 FCN が出す注文 size」を変える → SG 市場注文 1 件当たりの fill 効率に直結
- numAgents を増やすと price discovery / depth distribution / RNG 消費順 に二次効果が出る (より乱れた sensitivity)、orderVolume は depth と liquidity を線形にスケールするので解釈が clean

| 設定名 | orderVolume | 期待 total shares/step (FCN 側) | 想定 |
|---|---:|---:|---|
| `mmfcn_05x` | 15 | 30 × 15 = 450 | bottleneck 強化、SG RT 減 |
| `mmfcn_1x` (= C3 baseline) | 30 | 30 × 30 = 900 | S3/S5 と一致 |
| `mmfcn_2x` | 60 | 30 × 60 = 1,800 | bottleneck 緩和、SG RT 増 (H_artifact_mmfcn なら) |
| `mmfcn_4x` | 120 | 30 × 120 = 3,600 | liquidity 過剰、SG RT 飽和 (H_artifact_negated なら ~変化なし) |

**Fallback**: scan 結果が **ambiguous** (中間判定) の場合、§5 で `numAgents` scan の追加実施を Yuito に伺う。本 plan v1 では orderVolume のみ。

### 0.4 trial 数の根拠

各設定 **2 trial (seed=1000, 1001)** = 計 8 trial:
- 2 trial の理由: 1 trial では偶発の seed 依存性で判定誤りリスク、2 trial で min/max を取って range を出す
- 100 trial にしない理由: S5.6 はサニティチェックであり「強い変化が起きるかどうか」を見る粗 grain な test。S5.6 が判定不能なら numAgents scan / 設定数追加で trial 数も上げる方針
- baseline (`mmfcn_1x`, seed=1000/1001) は S3/S5 の `data/C3/trial_1000.parquet` / `trial_1001.parquet` を **flow 検証目的で再実行** (期待: bit-一致確認、Phase 1 互換 hook の non-regression)

---

## 1. S5.6 の目的

(a) **MMFCN orderVolume scan {0.5x, 1x, 2x, 4x} × 2 trial = 8 trial を Mac 上で完走**

(b) **各設定で SG agent の per-trial RT 数 / forced retirement 率 / lifetime 分布 / MMFCN 自身の order fill 率** を測定

(c) **H_artifact_mmfcn / H_artifact_negated 判定** を §0.2 基準で実施

(d) **S6 進行 / refactor の go/no-go signal** を S5.5 と並行で出す

本 stage は **MMFCN config を編集する必要がある軽量 sim stage**。新規実装は MMFCN sweep runner (~100 行) + Windows 集計 script (~80 行) のみ。

---

## 2. 入力

### 2.1 既存資源 (流用)

- `code/run_experiment.py::run_lob_trial` (S3/S4 で実装)
- `code/parallel.py::run_parallel_trials` (multiprocessing)
- `code/config.py::CONDITIONS["C3"]` (LOB Pareto setup)
- `experiments/YH006/configs/c3.py::make_config` + `_base.py::_FCN_AGENTS` (MMFCN config 起点)
- `code/analysis.py` / `code/aggregate_ensemble.py` (RT 数 / lifetime 集計 logic 流用)
- `data/C3/trial_{1000,1001}.parquet` (baseline 比較用、bit-一致 / semantic-一致 sanity check)

### 2.2 新規実装

| ファイル | 役割 | 想定 LoC |
|---|---|---|
| `code/mmfcn_sensitivity.py` | scan runner: 4 設定 × 2 trial を multiprocessing で実行、各 (setting, seed) で 4 parquet 出力 (Mac 側) | ~120 |
| `code/aggregate_mmfcn_sensitivity.py` | 集計 + 判定: RT 数 / forced_retire 率 / lifetime / MMFCN fill 率を 4 設定で比較、判定 logic 実装 (Windows 側) | ~90 |

### 2.3 MMFCN config override 経路

S4 plan §0.4 と同じ **Phase 1 後方互換拡張** ルールで対応:
- `run_lob_trial` に `mmfcn_order_volume: Optional[int] = None` kwarg を追加
- `None` の場合は `_FCN_AGENTS["orderVolume"]` (= 30) のまま (= 既存挙動と bit-一致、これで baseline `mmfcn_1x` が S3/S5 と完全一致するはず)
- 非 None の場合は `cfg["FCNAgents"]["orderVolume"] = mmfcn_order_volume` で上書き
- `parallel.py::run_parallel_trials` に同 kwarg passthrough

Phase 1 test 後方互換: `mmfcn_order_volume=None` 経路は既存挙動完全一致なので、S4 §3.1 で確認済の 27 件 test は再走しても全 pass のはず (本 plan §3.1 で確認)。

### 2.4 MMFCN fill 率 測定

PAMS の `OrderTrackingSaver` (既存) は order book event を記録している。MMFCN agent の発注 → 約定の trace から、設定ごとに **`mmfcn_fill_rate = filled_volume / submitted_volume`** を集計可能。実装は `aggregate_mmfcn_sensitivity.py` 内、`OrderTrackingSaver` の log 解釈 logic を `code/lob_ensemble.py` / S3 の既存 logic から流用 (S3 で agent_idx 別 RT 抽出を実装済 → MMFCN ID で抽出するだけ)。

---

## 3. 作業項目

### 3.1 Phase 1 後方互換 hook 追加 (Mac、または Windows でも実装のみ可)

実装手順:
1. `code/run_experiment.py::run_lob_trial_smoke` / `run_lob_trial` / `run_one_trial` に `mmfcn_order_volume: Optional[int] = None` kwarg 追加
2. `cfg["FCNAgents"]["orderVolume"] = int(mmfcn_order_volume)` の override (非 None 時)
3. `code/parallel.py::_worker_run_trial` / `run_parallel_trials` で passthrough
4. Phase 1 test 再走 (Windows で aggregate parity 27 件 / Mac で LOB tests):
   - `mmfcn_order_volume=None` 経路の bit-一致を確認
   - 失敗時は §5 stop trigger

### 3.2 baseline 一致確認 (sanity)

`run_lob_trial("C3", seed=1000, mmfcn_order_volume=None)` (= `mmfcn_1x` baseline) を実行 → 4 parquet を生成 → `data/C3/trial_1000.parquet` 系と sha256 / semantic 比較:
- **bit-一致**: PAMS の seed propagation + `mmfcn_order_volume=None` 経路で `cfg["FCNAgents"]["orderVolume"]` を一切 touch しないなら parquet bit-一致を期待
- **bit-不一致だが semantic-一致** (RT 数 / final wealth 等が一致): bit-一致まで保たれていないが意味的に同等。`stage_S5.6_diff.md` で記録、Yuito 議論
- **semantic-不一致**: hook 実装でバグ、§5 stop trigger

### 3.3 MMFCN sweep 8 trial 実行 (Mac)

```bash
cd experiments/YH006_1
git pull
python -m code.mmfcn_sensitivity \
    --cond C3 \
    --mmfcn-order-volumes 15,30,60,120 \
    --seeds 1000,1001 \
    --n-workers 8
```

各 (mmfcn_setting, seed) で:
- `data/mmfcn_sensitivity/{setting}_{seed}/trial.parquet` (rt_df)
- 同 `/agents.parquet`、`/lifetimes.parquet`、`/wealth_ts.parquet`
- runtime log to `logs/runtime/{ts}_S5.6_mmfcn_sensitivity.log`

**設定別 runtime 見積**:
| 設定 | orderVolume | 期待 runtime / trial | 8-worker 並列 計 |
|---|---:|---:|---:|
| 0.5x | 15 | ~410 秒 (S3 baseline と同水準) | 8 trial → 各 2 trial、~410 秒 (順次なら 3,280 秒 ≈ 55 min) |
| 1x | 30 | ~410 秒 | 同上 |
| 2x | 60 | ~450 秒 (約定処理増で 10% 増し見積) | |
| 4x | 120 | ~500 秒 (depth 大幅増、約定多発で 20% 増し) | |

**Mac で 8-worker 並列なら 8 trial を 1 wave で完走**、wave 全体 ~500 秒 = 約 10 分。FCN order book event 増による I/O 等で 1.5-3x スケール想定して **4-8 時間** を上限とする (本 plan の想定 runtime と一致)。

**異常時 stop**: 1 設定で runtime > 30 min/trial → §5 stop trigger。

### 3.4 集計 (Windows)

Mac → Windows 転送 (git, S3/S5 と同パターン):
1. `data/mmfcn_sensitivity/` を Mac で commit / Windows で pull
2. Windows で集計:
   ```bash
   python -m code.aggregate_mmfcn_sensitivity
   ```
3. 集計内容 (`aggregate_mmfcn_sensitivity.py`):
   - 各 setting で **n_rt mean** (2 trial の平均)、**n_rt range** (min-max)
   - **forced_retire_rate**: agent_idx 別 退場検知ロジックを S3 と同じく流用
   - **lifetime_median / p25 / censoring 率** を 4 設定で比較
   - **mmfcn_fill_rate**: §2.4 の logic で MMFCN agent ID 別の filled/submitted を集計
   - 設定間 ratio: `setting / mmfcn_1x` を per-metric で計算
   - **判定 (§3.5)**

### 3.5 判定 logic

`aggregate_mmfcn_sensitivity.py` 末尾で:

```
rt_ratio_2x = n_rt(mmfcn_2x) / n_rt(mmfcn_1x)  # 2 trial 平均
rt_ratio_4x = n_rt(mmfcn_4x) / n_rt(mmfcn_1x)
rt_ratio_05x = n_rt(mmfcn_05x) / n_rt(mmfcn_1x)

if rt_ratio_2x >= 1.8 or rt_ratio_4x >= 2.5:
    verdict = "H_artifact_mmfcn"   # MMFCN bottleneck 確定、Phase 2 結論 refactor
elif rt_ratio_2x <= 1.2 and rt_ratio_4x <= 1.5 and rt_ratio_05x >= 0.8:
    verdict = "H_artifact_negated" # MMFCN 十分、S6 進行
else:
    verdict = "ambiguous"          # 中間、Yuito 議論
```

副次判定 (verdict が ambiguous の場合の補助情報):
- forced_retire_rate が 2x / 1x で **3x 以上拡大** → bottleneck の追加 evidence (H_artifact_mmfcn 寄り)
- mmfcn_fill_rate が 1x で **0.5 未満** (= MMFCN 自身も板上で約定し切れていない) → 内的整合性問題、別途調査

### 3.6 figure + 出力

`fig_S5.6_mmfcn_scan.png` (4 設定の比較、4 サブパネル):
1. n_rt (mean ± range) vs orderVolume (log-x)
2. forced_retire_rate vs orderVolume
3. lifetime_p25 / conditional median vs orderVolume
4. mmfcn_fill_rate vs orderVolume

出力一覧:

| パス | 内容 |
|---|---|
| `code/mmfcn_sensitivity.py` | Mac sweep runner (~120 行) |
| `code/aggregate_mmfcn_sensitivity.py` | Windows 集計 + 判定 (~90 行) |
| `data/mmfcn_sensitivity/{setting}_{seed}/{trial,agents,lifetimes,wealth_ts}.parquet` × 32 (4 setting × 2 seed × 4 schema) | sweep 出力 |
| `outputs/tables/tab_S5.6_mmfcn_sensitivity.csv` | 4 設定 × {n_rt, forced_retire, lifetime, fill_rate} の数値 |
| `outputs/figures/fig_S5.6_mmfcn_scan.png` | §3.6 の 4 panel figure |
| `logs/runtime/{ts}_S5.6_mmfcn_sensitivity.log` | Mac sim 全 ログ |
| `logs/runtime/{ts}_S5.6_aggregation.log` | Windows 集計 ログ |
| `logs/S5.6_summary_for_diff.json` | 判定結果 + 各 ratio 数値 dump |
| `plans/stage_S5.6_diff.md` | 判定結果 + Yuito レビュー用 diff |
| `README.md` | `## Stage S5.6 — MMFCN sensitivity scan` 節を追記 |

### 3.7 README 追記

`## Stage S5.6 — MMFCN sensitivity scan (約定 artifact 検出)`:
- Yuito 指摘 2 と H_artifact_mmfcn / H_artifact_negated 二択
- 4 設定 × 2 trial の RT 数 / forced_retire / lifetime / fill_rate 表
- 判定結果 (H_artifact_mmfcn / H_artifact_negated / ambiguous)
- S6 進行 / refactor の signal 結論 (S5.5 と合わせて Yuito 判定)
- numAgents scan 追加の要否 (ambiguous の場合)
- Layer 2 timescale concern 言及継続

---

## 4. 完了条件

### Windows 側 (実装 + Phase 1 test)
- [ ] §3.1 hook 追加 (`mmfcn_order_volume` kwarg、`None` 経路 = 既存挙動)
- [ ] aggregate parity 27 件 PASS (Windows で再走)
- [ ] commit + push (Mac が pull できる状態)

### Mac 側
- [ ] git pull で Windows commit を取得
- [ ] LOB Phase 1 tests 全 pass (`run_lob_trial` の hook 拡張に伴う既存挙動破壊チェック)
- [ ] §3.2 baseline 一致確認 (`mmfcn_1x` seed=1000 が `data/C3/trial_1000.parquet` と bit-一致 or semantic-一致)
- [ ] §3.3 sweep 8 trial 完走 (4 設定 × 2 seed)、各 4 parquet × 8 = 32 file
- [ ] git commit + push (parquet 同梱)

### Windows 側 (Mac 後)
- [ ] git pull
- [ ] §3.4 `aggregate_mmfcn_sensitivity.py` 実行 → 表 + 4 panel figure
- [ ] §3.5 判定 (H_artifact_mmfcn / H_artifact_negated / ambiguous) 確定
- [ ] §3.6 出力 + README 追記
- [ ] `stage_S5.6_diff.md` 提出、Yuito レビュー待ち

---

## 5. Yuito 確認事項 (実装中 stop trigger + 完了後レビュー)

### 実装中の停止トリガー (発生したら停止 → Yuito 相談)

- §3.1 で aggregate parity 27 件のいずれかが fail (`mmfcn_order_volume=None` 経路で既存挙動破壊)
- §3.2 baseline 一致で **semantic-不一致** (n_rt や final wealth が S3/S5 と乖離) → hook バグ
- §3.3 sweep で runtime > 30 min/trial がいずれかの設定で発生 (orderVolume=120 で約定多発の I/O 重さ等)
- §3.4 集計で MMFCN agent ID 抽出に失敗 (OrderTrackingSaver の log schema 未把握) → §2.4 logic 再設計が必要
- §3.5 判定で `mmfcn_4x` の n_rt が `mmfcn_1x` の **0.5 未満** (= 約定が逆に減る) → 想定外、別 mechanism 疑い

### 完了後 (Yuito レビュー) 確認事項

1. §0.3 で `orderVolume` を primary に選んだ判断 (numAgents の代わりに) を承認するか、numAgents も同時 scan すべきか
2. §0.4 trial 数 2 / 設定 の小ささを承認するか、4 trial / 設定に増やすか
3. §3.5 判定 (H_artifact_mmfcn / H_artifact_negated / ambiguous) の解釈
4. ambiguous の場合の追加 scan (numAgents、設定値さらに細分化) plan の要否
5. **S6 進行 / refactor 判断 (S5.5 と統合)**:
   - S5.5 = H_micro 強支持 AND S5.6 = H_artifact_negated → **S6 (A3 ablation) 進行**
   - S5.5 = H_artifact 強支持 OR S5.6 = H_artifact_mmfcn → **Phase 2 結論 refactor、S6 scope 再定義**
   - 中間判定 → Yuito 議論
6. mmfcn_fill_rate が想定外に低い (< 0.5) 場合の解釈と追加調査の要否

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | Yuito 方法論的指摘 2 (MMFCN 約定難 artifact の可能性) への応答 stage。LOB C3 setup で MMFCN の `orderVolume` を {15, 30, 60, 120} の 4 設定 × 2 trial (seed=1000, 1001) で scan、SG per-trial RT 数 / forced_retire / lifetime / MMFCN fill 率を比較し H_artifact_mmfcn / H_artifact_negated を判定。`orderVolume` を primary 選択した理由: numAgents は depth 分布 / RNG 消費順への二次効果が大きく解釈が不明瞭、orderVolume は liquidity を線形にスケールし解釈 clean。Phase 1 後方互換 hook (`mmfcn_order_volume` kwarg、`None` 経路 = 既存挙動 bit-一致) は S4 §0.4 と同じ protocol で追加。baseline (`mmfcn_1x`) は `data/C3/trial_1000.parquet` と bit-一致を sanity check。S5.5 (aggregate sub-sample 再分析) と並走、両 stage 完了後に S6 進行 / refactor を Yuito 判定。ambiguous 判定の場合の numAgents scan は §5 で別途相談。 |
