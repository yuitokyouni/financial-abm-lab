# Stage S1 完了報告

| 項目 | 値 |
|---|---|
| Stage | S1 (tentative) — Phase 1 データ再分析 |
| Status | 完了、Yuito レビュー待ち |
| 実装日 | 2026-04-27 |
| 主参照 plan | `plans/stage_S1_plan.md` v2.0 |

---

## 実装サマリ

### 主要ファイル

| パス | 役割 | 行数 |
|---|---|---:|
| `code/__init__.py` | (空) | 0 |
| `code/analysis.py` | 5 主指標 + plan B 先取り指標の計算 | ~165 |
| `code/stats.py` | bootstrap / MW-U の骨格 (S1 では未使用、S3+ で call) | ~75 |
| `code/reanalyze_phase1.py` | S1 主スクリプト (Step 1-6 全段) | ~525 |

### 入力 / 出力

| カテゴリ | パス | 内容 |
|---|---|---|
| 入力 | `data/_phase1_imported/c0u_result.pkl` | C0u Phase 1 raw (49 MB) |
| 入力 | `data/_phase1_imported/c0p_result.pkl` | C0p Phase 1 raw (49 MB) |
| 入力 | `data/_phase1_imported/C2_result.pkl` | C2 Phase 1 raw (220 KB、Mac 転送) |
| 入力 | `data/_phase1_imported/C3_result.pkl` | C3 Phase 1 raw (228 KB、Mac 転送) |
| 出力 | `data/phase1_reanalysis_round_trips.parquet` | 4 条件 merge RT 単位 (24.2 MB) |
| 出力 | `data/phase1_reanalysis_agents.parquet` | 4 条件 merge agent 単位 (10 KB) |
| 出力 | `outputs/tables/tab_S1_phase1_reanalysis.csv` | 5 主 + plan B + timescale + interaction |
| 出力 | `outputs/figures/fig_S1_indicator_comparison.png` | 5×4 bar + interaction sub-panel |
| 出力 | `README.md` | tentative S1 結果サマリ |
| 出力 | `logs/runtime/{ts}_S1_reanalyze_phase1.log` | INFO レベル全 step ログ |

### 完了 trial 数

| 条件 | trial | データ source |
|---|---:|---|
| C0u | 1 | seed=777, Windows 生成済 |
| C0p | 1 | seed=777, Windows 生成済 |
| C2  | 1 | seed=777, Mac → Windows 転送済 |
| C3  | 1 | seed=777, Mac → Windows 転送済 |

### Runtime 実測値 (Windows, Python 3.13.1)

| 項目 | 時間 |
|---|---:|
| Step 1 整合性チェック | 0.05 s |
| Step 2 schema アダプタ (4 条件) | 0.5 s |
| parquet 出力 | 1.5 s |
| Step 3 主指標 (主に quantile regression が支配) | ~17 s |
| Step 4 timescale split | ~13 s |
| Step 5 interaction 計算 | < 0.01 s |
| Step 6 csv + figure + README 出力 | 1.5 s |
| **total** | **~ 35 s** |

---

## Plan からの逸脱

### 逸脱 1: figure / README の defensive 分岐の clean up を ガード節撤去と同時実施

**何を**: `plot_indicator_comparison` 内の `if interactions: ... else: 'gated until C2/C3 transferred' placeholder` 分岐と、`write_readme` 内の `if not full_run: ... '注意: C2/C3 pkl 転送待ち'` 分岐を削除。

**なぜ**: plan v2 §1 注意点 1 では `integrity_check` の skip 経路と `main` の `len(loaded) < 4` 分岐の撤去が指示されていたが、figure / README にも同じ「gated」文言が残っており、最終出力にこの placeholder が描画されると Yuito 混乱の元。clean up 一括で実施。

**影響**: なし (より readable な最終出力)。最終 figure の interaction panel タイトルが `"Interaction (4 conditions required; gated until C2/C3 transferred)"` から `"Interaction = (C3 − C2) − (C0p − C0u)  (point estimates; CI is S1-secondary scope)"` に変更され、informative になった。

### 逸脱なし (plan 通り)

- 6 点 prerequisites report は plan v2 §0 の通り
- 5 主指標 + plan B 先取り指標の計算は plan v2 §3.2 の通り
- timescale 切り基準は RT count median split (plan v2 §0.2 / Yuito 指示 v2 #2)
- w_init は agent-level / RT-level 別 column (plan v2 §3.2 / Yuito 指示 v2 #4)
- LOB w_init reconstruction は PAMS 不在で None 返し (plan v2 §0.1 既記載の制約)
- 出力 parquet 2 種 (RT 単位 + agent 単位) は plan v2 §3.3 の通り

---

## 数値結果サマリ

### Step 1 整合性チェック (plan v2 §0.7)

| 条件 | file size | RT 数 | rel_err | α_hill (obs / exp) | 判定 |
|---|---:|---:|---:|---|---|
| C0u | 48.76 MB | 1,041,712 / 1,041,712 | 0.00000 | 3.910 / 3.910 | OK |
| C0p | 49.10 MB | 1,049,903 / 1,049,903 | 0.00000 | 4.068 / 4.068 | OK |
| C2  | 0.22 MB  | 879 / 879             | 0.00000 | 1.985 / 1.980 | OK (rel_err 0.0024) |
| C3  | 0.23 MB  | 1,080 / 1,080         | 0.00000 | 1.913 / 1.910 | OK (rel_err 0.0013) |

全 4 条件 pass、Phase 1 README の数値と完全整合。

### Step 3 主指標 (4 条件 × 5 指標、点推定)

| cond | n_rt | Pearson | Spearman | Kendall | binVar slope | qreg slope diff |
|---|---:|---:|---:|---:|---:|---:|
| C0u | 1,041,712 | +0.3535 | +0.1944 | +0.1561 | −0.2033 | +0.5833 |
| C0p | 1,049,903 | +0.3471 | +0.1923 | +0.1545 | −0.2308 | +0.5965 |
| C2  | 879       | +0.6091 | +0.4221 | +0.3416 | −0.1758 | +1.8182 |
| C3  | 1,080     | +0.3329 | +0.2816 | +0.2216 | −0.1727 | +0.9444 |

**Phase 1 README の Pearson 値 (C0u 0.353 / C0p 0.347 / C2 0.61 / C3 0.33) と完全一致** → schema アダプタの正しさが確認された (sanity check (b) pass)。

### Step 4 timescale split (RT count median)

| cond | half | n_rt | Pearson | Spearman | binVar slope | qreg slope diff |
|---|---|---:|---:|---:|---:|---:|
| C0u | first | 520,856 | +0.357 | +0.198 | −0.126 | +0.596 |
| C0u | second | 520,856 | +0.350 | +0.191 | −0.350 | +0.583 |
| C0p | first | 524,951 | +0.340 | +0.186 | −0.486 | +0.583 |
| C0p | second | 524,952 | +0.355 | +0.199 | −0.220 | +0.606 |
| C2  | first | 439 | +0.639 | +0.333 | +0.250 | +1.363 |
| C2  | second | 440 | +0.589 | +0.503 | −0.382 | +2.077 |
| C3  | first | 540 | +0.404 | +0.259 | −0.236 | +0.844 |
| C3  | second | 540 | +0.277 | +0.290 | +0.030 | +0.900 |

aggregate (C0u/C0p) の主指標は前半/後半で安定。LOB (C2/C3) は sample size が小さく (n=440-540)、特に bin variance slope の前半/後半ブレが大きい。

### Step 5 interaction = (C3 − C2) − (C0p − C0u)

| indicator | full | first half | second half |
|---|---:|---:|---:|
| **rho_pearson** | **−0.2699** | −0.2178 | −0.3161 |
| rho_spearman | −0.1384 | −0.0610 | −0.2214 |
| tau_kendall | −0.1184 | −0.0589 | −0.1862 |
| bin_var_slope | **+0.0305** | −0.1270 | +0.2823 |
| qreg_slope_diff | **−0.8869** | −0.5049 | −1.1997 |

**Pearson interaction = −0.2699** が **Phase 1 README の F1 "−0.27" と完全一致** → sanity check (c) 桁感 pass。

### Step 3 plan B 先取り指標

| cond | corr(w_init, h) | skew(high − low) | Hill α (\|ΔG\|) |
|---|---:|---:|---:|
| C0u | −0.0006 | −0.13 | 1.92 |
| C0p | −0.0027 | −0.10 | 1.97 |
| C2  | NaN     | −0.68 | 3.17 |
| C3  | NaN     | −0.04 | 2.94 |

`corr(w_init, h)`:
- aggregate (C0u/C0p) ≈ 0 → SPEC §1.4 「Pareto 初期分布が aggregate で流される」と整合
- LOB (C2/C3) は **NaN** (PAMS 不在で w_init reconstruction 不可、Phase 2 100 trial 段階で SG agent に明示 logging 追加で解消予定)

### SPEC §6 KPI level に照らした暫定判定

**tentative S1 は KPI 判定の場ではない** (plan v2 §0.3 / §1)。点推定のみで CI なし、L1/L2/L3/L4 判定は S1-secondary に移譲。本 stage の役割は (a)(b)(c) の 3 点 sanity check のみ:

| 役割 | 完了状況 |
|---|---|
| (a) 5 主指標実装 sanity check | ✅ NaN なし (LOB の corr_w_init,h は計画通り skip)、Phase 1 既知数値と一致 |
| (b) Phase 1 → Phase 2 schema アダプタ確定 | ✅ parquet 2 種出力 (RT 単位 24 MB / agent 単位 10 KB)、aggregate w_init RNG 再構成成功 |
| (c) 桁感の事前確認 | ✅ Pearson interaction が Phase 1 既知の −0.27 と完全一致、5 指標が桁スパン 0.03〜0.89 で読める |

---

## 次 Stage への申し送り

### S2 開始前に Yuito レビューが必要な事項

1. **(a)(b)(c) sanity check 3 点 pass の最終承認** (本 diff.md の数値結果サマリを Yuito が読んだ上で OK 判断)。
2. 桁感の暫定値が予想内かの確認:
   - **Pearson interaction −0.27** は Phase 1 と一致、これは sanity check 動作の証拠でもあり、F1 が schema アダプタを通っても保存される証拠でもある
   - **Spearman / Kendall interaction も同符号 (−0.14 / −0.12)、桁は Pearson の半分** ← 重尾分布の順位相関で typical (Pearson が tail に引っ張られる、順位相関は中央傾向のみ捉える)
   - **bin_var_slope interaction は +0.03 (ほぼゼロ、しかも符号反転)** ← 単 trial では robust ではない signature。100 trial で平均すれば signal が出るかは S1-secondary で確定
   - **qreg_slope_diff interaction = −0.89 (同符号、桁大)** ← funnel 開口の interaction として最強の signal
3. 上記の暫定値が「予想外」(例: Pearson 符号反転、5 指標の桁が完全にバラバラ) ならば緊急相談、それ以外は **S2 続行**。

### 見つかった issue / 懸念

#### Issue 1: LOB w_init が PAMS 不在環境で再構成不可 (既知制約、Phase 2 で解消)

C2/C3 の `corr(w_init, h)` が NaN。PAMS の `random.Random` ベース prng split を Pure Python で完全再現するのが困難。

**解消策** (Phase 2 への申し送り):
- 100 trial ensemble 段階で SG agent (`speculation_agent.py` の subclass) に **明示的に w_init logging を追加** することで本問題を回避
- これは Phase 2 §3.1 で `code/sg_agent.py` を実装する際の要件として申し送り
- 本 S1 の tentative scope では LOB の corr_w_init は NaN のままで OK (sanity check の (b) (c) には影響しない)

#### Issue 2: bin_variance_slope の LOB sample size 不足

C2/C3 は n=879/1,080 RT、timescale split で n=440/540 まで落ちる。bin variance slope (K=15 bin) の各 bin に平均 ~30 sample しか入らないため、LOB の点推定は不安定 (full +0.03 / first −0.13 / second +0.28)。

**観察**:
- 100 trial pooled (S3 完了時) で n が 100x になれば bin あたり ~3000 sample、安定するはず
- bin_var_slope を主指標に使うかは S1-secondary 段階の bootstrap CI で「LOB 100 trial pooled で SE が出るか」を見て確定

#### Issue 3: timescale 後半で Pearson interaction がやや強化 (−0.218 → −0.316)

aggregate 側は前半/後半で安定だが、LOB 側では C2 (Pearson 0.639 → 0.589 で減衰) と C3 (Pearson 0.404 → 0.277 で減衰) ともに後半で減衰、ただし減衰率が違うため interaction は強化される方向。

**plan v2 シナリオ δ (timescale で消失) の signature ではない** (= 後半で消えるどころか強化)。LOB 環境では substitute dynamics の収束が遅い signature の可能性、もしくは LOB の T=1500 自体が短すぎて transient phase を切り出している可能性。これは Layer 2 timescale concern (Phase 2 scope 外、proposal Limitations 節記述予定) と整合。

#### Issue 4: SPEC §6 KPI L1 (「F1 が Spearman/Kendall/bin variance のうち少なくとも 2 つで符号と桁が一致」) の暫定確認

| 指標 | full interaction | 符号 | F1 (Pearson −0.27) と桁が一致? |
|---|---:|---|---|
| Spearman | −0.14 | 同 (−) | 半分の桁、L1 の「桁一致」基準には微妙 |
| Kendall | −0.12 | 同 (−) | 半分の桁、同上 |
| bin variance | +0.03 | **逆** (+) | **不一致** |

L1 を厳格 (= Pearson と同桁) で判定すると **2 / 3 で同符号、1 / 3 (bin variance) で符号反転**。
L1 を緩く (= 同符号で十分) 判定すると **2 / 3 pass**。

これは tentative S1 の暫定値、S1-secondary (100 trial bootstrap CI) で確定する。**特に bin variance の +0.03 は単 trial の sample 不足 artifact である可能性が高く**、100 trial で signal が現れるかが本筋。

### 当面の S2 着手前提

S2 は **本 tentative S1 結果に関わらず実行** (plan v2 §0.3 / Yuito 指示 v2 #1)。本 diff の暫定値は Yuito が読んで「予想外でない」と判断すれば S2 進行可。S2 plan は別ファイル (`plans/stage_S2_plan.md`) で作成、Yuito 承認後に S2 実装に着手する。

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書) | Stage S1 完了報告、Brief §7 format、4 条件 完走、ガード節撤去後の最終実装 |
