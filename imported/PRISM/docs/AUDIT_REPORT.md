# PRISM Critical Audit Report

**Date:** 2026-05-25
**Scope:** Full codebase audit — ABM implementations, scoring pipeline, calibration, simulation mechanics

---

## Executive Summary

PRISMの科学的主張（「SG/FWがZI-Cを上回る判別力を持つ」）は**複数の独立した致命的欠陥**の上に成り立っている。
ground truthの統計的無意味性、ABM実装の構造的同一性、シミュレーション手法の方法論的誤りが重なり、
現状の結果は科学的証拠として使用できない。

**問題の深刻度分類:**

| 深刻度 | 件数 | 概要 |
|--------|------|------|
| FATAL (結果が無効) | 5 | ground truth=ノイズ、avg_returnsがfat tailsを破壊、4モデルが構造的に同一、tick_sizeがSGでno-op、多重比較未補正 |
| SERIOUS (比較不能) | 3 | price_impact不統一、calibrationが1次モーメントのみ、seed固定 |
| MODERATE | 4 | LM残留密輸、CI偽オーダーブック、path間相関、無効NERにガード無し |

---

## FATAL-1: Ground Truthが統計的にゼロ

**場所:** `data/ner/jpx_2014_jp_tick.yaml`

JPX 2014 DiD表の6 facts全てのCI95が0をまたぐ:

| Fact | DiD delta | CI95 | 0をまたぐ? |
|------|-----------|------|-----------|
| volatility_clustering | -0.093 | [-0.319, +0.137] | YES |
| leverage_effect | -0.013 | [-0.112, +0.083] | YES |
| gain_loss_asymmetry | +0.373 | [-0.091, +0.868] | YES |
| fat_tails | +0.559 | [-1.718, +3.435] | YES |
| abs_autocorrelation | +0.029 | [-0.101, +0.153] | YES |
| squared_return_acf | +0.037 | [-0.094, +0.176] | YES |

**帰結:** 「正解の符号」自体がコイン投げ。sign matchスコアリングの前提が崩壊している。

**統計的検定:**
- 6回のBernoulli(0.5)試行で5/6: p = 7/64 ≈ 0.109 — 有意水準5%を満たさない
- 4 adapterで最良を選択: family-wise error ≈ 1-(1-0.109)^4 ≈ 0.37
- ZI-Cの3/6は期待値そのもの — ノイズ診断と完全に整合

**修正方針:** `score_sign()`にCI95ゼロ交差チェックを追加。交差する場合は`INCONCLUSIVE`を返す。
binomial p-valueを`CellOutput.summary()`に追加。多重比較補正（Holm法）を`run_tensor()`に追加。

---

## FATAL-2: avg_returnsがstylized factsを破壊

**場所:** 全5 adapter の `simulate()` — 例: `sg.py:127`

```python
avg_returns = np.mean(all_returns, axis=0)  # n_paths個のpathを平均
```

この平均系列に対してfat_tails（超過尖度）、volatility_clustering（GARCH alpha+beta）等を計測している。

| Fact | 平均化の影響 |
|------|-------------|
| fat_tails (超過尖度) | CLTにより0に収束 — 測定対象そのものが消滅 |
| volatility_clustering | ボラティリティスパイクが平滑化 — GARCH持続性が過小推定 |
| abs_autocorrelation | 振幅が減衰 — ACFが過小推定 |
| squared_return_acf | 同上 |
| leverage_effect | S/N比が劣化 |

**既存の正しい実装:** `pipeline.py:163` の `_compute_per_path_facts()` は各pathで個別にfact計算後に中央値。
ただしデフォルトOFF（`per_path_facts=False`）。

**修正方針:** `per_path_facts=True`をデフォルト化 or classic averaging modeを削除。

---

## FATAL-3: 4つのABMが構造的に同一モデル

**場所:** `src/prism/adapters/` の sg.py, fw.py, ci.py, lm.py

全4 adapterの`_simulate_one_path`が同じ骨格:

```
d_fund = speed * (F - P)           # fundamentalist mean-reversion
d_chart = strength * trend * P     # chartist trend-following
d_noise = N(0, sigma * P)          # noise
excess_demand = w_f*d_fund + w_c*d_chart + w_n*d_noise
dp = price_impact * excess_demand
dp = round(dp / tick_size) * tick_size
P_new = P_old + dp
```

**差異は表面的:**

| モデル | 名目上の特徴 | 実際の実装 | 原著論文との乖離 |
|--------|-------------|-----------|-----------------|
| SG (Katahira 2019) | 個別エージェント学習 | `n_agents=500`は未使用。集計fraction×softmax | 個別閾値・学習メカニズム欠落 |
| FW (Franke-Westerhoff 2012) | 構造的確率モデル | 線形遷移確率（最も原著に近い） | Kirman herdingインデックス欠落 |
| CI (Chiarella-Iori 2009) | オーダーブック+CDA | bid/askスカラー2個のみ。注文キュー無し | オーダーブック全体が欠落。エージェントタイプ固定のはずが可変 |
| LM (Lux-Marchesi 1999) | F↔C+↔C- 3状態遷移 | `frac_fund=0.4`, `frac_chart=0.6` が定数 | 定義的メカニズム（人口間遷移）が完全欠落 |

**帰結:** 4モデルの出力を「独立な証拠」として扱えない。同じ因果経路（price_impact × excess_demand）を
通るため、介入応答は構造的に相関する。

**`n_agents`の死んだパラメータ:** SG (`sg.py:33`) と CI (`ci.py:34`) で定義されているが、
シミュレーションループ内で一度も参照されない。ABMの見かけを作る装飾。

---

## FATAL-4: SGのtick_size介入はno-op

**場所:** `sg.py:186-188`

```python
dp = round(dp / p.tick_size) * p.tick_size
```

**数値分析:**
- `price_impact = 1.0`, `noise_scale ≈ 0.01`, `fundamental_value = 100.0`
- `d_noise ≈ N(0, 0.01 * 100) = N(0, 1.0)` → `dp ≈ N(0, 1.0)`
- baseline `tick_size = 0.01`: 丸め誤差 ≤ 0.005 → dpの0.5% → **完全なno-op**
- 介入後 `tick_size = 0.1` (YAML `min_tick_to`): 丸め誤差 ≤ 0.05 → dpの5% → **ほぼno-op**

**方向反転:** 実世界JPX 2014はtick sizeを10倍小さく（1.0→0.1 JPY）。
SG modelのデフォルトは0.01、YAML値0.1を直接代入すると**10倍粗く**なる。物理的効果と逆方向。

**帰結:** SGの5/6 sign matchは、介入がほぼ何もしない（≈ baseline出力そのまま）状態で、
ノイズ符号に偶然5/6当たっただけ。

---

## FATAL-5: 統計的検定が一切存在しない

**場所:** `src/prism/scoring/scorer.py`, `src/prism/pipeline.py`

| 欠落している検定 | あるべき場所 |
|-----------------|-------------|
| CI95ゼロ交差チェック | `score_sign()` |
| 二項検定 (sign match count) | `CellOutput.summary()` |
| 多重比較補正 (Holm/Bonferroni) | `run_tensor()` |
| seed安定性検定 | 新規 `stability.py` |
| ZI-C null分布 (multi-seed) | `run_tensor()` |

---

## SERIOUS-1: price_impactがadapter間で不統一

**場所:** 各adapterの`calibrate_baseline()`

| Adapter | price_impact | 出典 |
|---------|-------------|------|
| SG | 1.0 | `sg.py:67` |
| LM | 0.8 | `lm.py:78` |
| FW | 0.6 | `fw.py:71` |
| CI | 0.5 | `ci.py:76` |
| ZI | 0.5 | `zi.py:63` |

全adapterが`noise_scale = target_vol`に統一しているが、price_impactが2倍の差。
SGは同じノイズで2倍の価格変動を生む。比較が同一条件になっていない。

---

## SERIOUS-2: Calibrationが1次モーメントのみ

**場所:** 全adapterの`calibrate_baseline()`

`target_vol = np.std(pre_data.returns)` → `noise_scale = target_vol` のみ。
尖度、GARCH持続性、ACF等のstylized factsはcalibration対象外。
eligibility gateは事後チェックだが、calibrationがそれらを目標にしていないため、
「このモデルはfat tailsを再現できるか」は運次第。

---

## SERIOUS-3: 全cellがseed=42固定

**場所:** `pipeline.py:540` — `run_tensor(seed=42)`

tensor内の全20 cell (5 adapter × 4 NER) が同一seed。seed感度テストが存在しない。
`CalibrationArtifact.seed`も全adapter共通で`0`にハードコード。

---

## MODERATE-1: LMにtick_sizeを通じた残留密輸

**場所:** `lm.py:189`

```python
opinion_pressure = p.herd_strength * opinion + p.chart_trend_weight * trend * 100
```

`trend ≈ tick_size / (lag * price)` なので、`opinion_pressure`は`tick_size`に線形依存。
tick_sizeの変更がherding dynamicsの入力強度を直接スケールする。
直接的なパラメータ操作ではないが、`chart_trend_weight * tick_size / lag`という
実効的な密輸経路が`* 100`アンプリファイアを通じて存在。

---

## MODERATE-2: CIの「オーダーブック」は偽物

**場所:** `ci.py:167-168, 222`

`best_bid`と`best_ask`はスカラー2個。注文キュー、価格時間優先、マッチングエンジンは存在しない。
docstring「Agents submit limit orders to a continuous double auction」は虚偽。
実質的にSGと同じ集計需要モデル + depth分母の修飾。

---

## MODERATE-3: simulate()内のpath間相関

**場所:** 全adapterの`simulate()` — 例: `sg.py:120-126`

```python
rng = np.random.default_rng(seed)   # 1つのrng
for _ in range(n_paths):
    returns = self._simulate_one_path(rng)  # 同じrngを順次消費
```

20 pathsは独立なMC複製ではなく、単一の長い乱数列を20分割しただけ。

---

## MODERATE-4: 無効NERにバリデーションガード無し

**場所:** `pipeline.py` の `run_cell()` / `run_tensor()`

`tspp_2016_us_equity.yaml`, `french_ftt_2012_eu.yaml`, `mifid2_2018_eu_tick.yaml` は
INVALID（external_claim）だが、pipelineは警告もエラーも出さずに実行する。

---

## 修正優先順位

### Phase 1: 計測基盤の修正（これ無しに何も意味がない）

1. `per_path_facts=True`をデフォルト化（FATAL-2解消）
2. `score_sign()`にCI95ゼロ交差チェック追加（FATAL-1部分解消）
3. binomial p-value + Holm補正を`run_tensor()`に追加（FATAL-5解消）
4. seed安定性テスト追加 — 同一cellを10 seedsで実行、sign match分布を報告
5. 無効NERガード追加（MODERATE-4解消）

### Phase 2: SGのtick_size介入の修正（FATAL-4解消）

6. tick_sizeを比率で適用: `tick_ratio = min_tick_to / min_tick_from`
   → `new_tick_size = baseline_tick_size * tick_ratio`（方向反転の解消）
7. 介入がno-opかどうかの定量テスト追加（pre/post delta分布の比較）

### Phase 3: ABM実装の構造分化（FATAL-3解消）

8. CI: 実際のlimit order bookとCDAマッチングエンジンの実装
9. LM: F↔C+↔C- 3状態遷移レートの実装（`frac_fund`/`frac_chart`を動的に）
10. SG: 個別エージェントの導入、または正直にBrock-Hommesとリネーム
11. 死んだ`n_agents`パラメータの除去

### Phase 4: Calibration + Simulation修正

12. price_impact統一 or 導出の文書化（SERIOUS-1）
13. 高次モーメントcalibration追加（SERIOUS-2）
14. path独立seed化: `rng_i = default_rng(seed + i)`（MODERATE-3）
15. LM `* 100`アンプリファイア除去 or 正当化（MODERATE-1）

---

## 結論

現状のPRISMは**計測器が壊れた状態で実験結果を主張している**。
Phase 1（計測基盤修正）が完了するまで、いかなるadapter比較結果も科学的に無意味。
Phase 3（ABM構造分化）が完了するまで、「複数モデルによる検証」という主張は成立しない。

修正は Phase 1 → 2 → 3 → 4 の順で、各Phase完了時に再評価を行う。
