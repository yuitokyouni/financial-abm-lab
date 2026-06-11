# Finding 0002 — 疎事象市場では Calvano 型「政策収束」が成立しない（収束概念の再設計と認定可能 regime）

**Status**: 機構は検証済（2026-06-11、本番 t_max の pilot ＋ SNR 算術）。coarse 地図は
完了（2026-06-11、本文末尾）。density spoke は OSF 事前登録
（`specs/002-exp-b-collusion-harness/prereg-density-spoke.md`）の完了待ちで未実行。

## 発見

baseline 事象密度（noise fill 確率 pn = ν·dt = 0.01/期、jump 確率 q = 0.05/期）では、
tabular Q-learning の**政策は——どの合理的な意味でも——収束しない**。一方で**行動の
時間平均は安定**し、markup は seed 横断で再現する（supra-Nash 水準、SE タイト）。

1. **全状態 policy 安定（D-B6 v1、Calvano 基準）は構造的に到達不能**。tail（ε≈10⁻⁴）でも
   2×10⁶ 期に数百回の探索 blip があり、off-path 状態の Q 行はノイズで argmax が容易に
   flip → 「全 updated 状態の argmax が 10⁵ 期不変」の streak は常にリセットされる。
2. **on-path の greedy limit-cycle 安定（v2）も baseline では到達不能**。on-path の
   (s,a) は毎期更新されるが報酬が疎×高分散なので、Q の定常ノイズ
   sd_Q ≈ √(lr/(2−lr))·sd_r ≈ 0.28×0.082 ≈ 0.023 に対し、隣接 arm 間の利得ギャップは
   tie-share vs undercut で ≈ pn·h/2 ≈ 0.003。**ギャップ/ノイズ ≈ 1/8** —— argmax は
   近傍 arm 間をランダムウォークし、観測 spread は「分布として」だけ定常になる。
3. **Calvano (2020) で政策収束が機能したのは報酬が毎期・決定論的だったから**（logit 需要
   は action profile 所与で確定利得）。市場 making は本質的に**疎報酬**（fill は稀・
   sniping は更に稀）であり、この差は Calvano パラダイムを orderbook に移植する際の
   一級の障害である。これは「先行研究の手順を踏めば再現する」類の問題ではない。

## 帰結（harness 設計への反映・実施済み）

- **収束基準 v2**（research 002 D-B6 v2）: 収束対象を「全状態の policy 表」から
  「**観測される行動**＝greedy limit-cycle（10⁴ 期ごとに決定論 probe、連続 10 回不変）」
  へ変更。off-path ノイズに頑健で、学習軌道は bit 不変（probe は表読みのみ）。
  それでも baseline 疎度では非収束＝**ラベルは正直に非収束のまま**（基準を結論が出る
  まで緩める criterion-shopping は constitution III の confirmation risk であり、やらない）。
- **認定可能 regime の同定 = dense tier の事象密度スポーク**（`designmap.density_spoke`）:
  ν ∈ {10, 30}（pn ∈ {0.1, 0.3}）× lr ∈ {0.02, 0.15}。SNR ∝ √pn / √lr なので
  (ν=30, lr=0.02) で ギャップ/ノイズ ≈ 2.7 となり cycle 収束が物理的に可能になる
  （memory=0 sanity では同種の設定で 6/6 seed 収束を確認済み）。(ν=30, lr=0.15) は
  lr の寄与を分離する対照。
- **解釈上の注意（経済 vs 統計の切り分け）**: 「疎報酬が collusion 学習を妨げる」は
  (i) 学習統計の問題（lr を下げ平均化すれば patient な learner は学べる）と
  (ii) 経済的な力（逸脱検知のシグナルが疎なら懲罰の条件づけが本質的に難しい
  ——Green-Porter の不完全監視そのもの）の**両方を含む**。(i) は lr 軸で外せるが
  (ii) は本物の市場 making 固有の摩擦でありうる。density spoke ＋ lr 対照が
  この二つを部分的に分離する。

## baseline 疎度 regime の観測（pilot、本番 t_max=2×10⁶、2 seed、全て非収束ラベル）

| 条件 | markup | 抽出 rate |
|---|---|---|
| cont-committed | 0.829 ± 0.024 | 0.0166 |
| batch5-committed | 1.319 ± 0.091 | 0.0303 |
| batch20-committed | 1.485 ± 0.114 | 0.0928 |
| cont-revisable | 2.216 ± 0.921 | 0 |

非収束ゆえ**認定はゼロ**（gate は設計どおり閉じている）。それでも方向は示唆的：
- batch は committed 下で markup を上げる（Green-Porter 整合の向き）。
- **revisable（sniping 切断）で markup が跳ねる**——arbitrageur predation が広い spread
  を規律している絵。committed vs revisable の対比が predation チャネルの ablation として
  機能している（finding 0001 の設計どおり）。
- ただしこれらは「分布として定常な遊走行動」の時間平均であり、認定済み collusion では
  ない。確定的な主張は density spoke（認定可能 regime）の結果でのみ行う。

## 数値結果 — coarse 72 セル（2026-06-11 完了、`results/coarse.csv`）

72/72 セル × 5 seed、**認定ゼロ**（gate は設計どおり閉。finding の予測どおり）。
予算: coarse 739,236,803 期 ≤ cap 1×10⁹（ledger: `results/budget.json`。crash 精算は
research.md D-B9 注記）。再実行は crash した run と bit 同一（D-B12 の本番スケール確認）。

条件別の markup 平均（12 パラメータセル横断、非収束の分布的時間平均）:

| 条件 | markup | 抽出 rate | 退出 frac |
|---|---|---|---|
| cont-committed | 0.586 | 0.078 | 0 |
| batch5-committed | 0.888 | 0.205 | 0.02 |
| batch20-committed | 1.075 | 0.361 | 0.12 |
| cont-revisable | 0.931 | 0 | 0 |
| batch5-revisable | 0.873 | 0 | 0 |
| batch20-revisable | 1.133 | 0 | 0 |

方向の観測（認定なし＝確定主張はしない）:

1. **committed 下で batch は markup を一様に上げる**: batch20 − cont の markup 差は
   **12/12 パラメータセルで正**（+0.16 〜 +1.08）。Green-Porter 整合の向きが
   vol・fee・memory・n 横断で再現。
2. **revisable で cont の markup が跳ねる**（0.586 → 0.931）——arbitrageur predation が
   連続市場の広い spread を規律している絵（pilot と同方向、12 セルで再確認）。
3. **部分収束（conv 1/5 seed）は 3 セルのみ、全て batch20-committed × memory=2, n=2**。
   これは SNR 機構の独立確認になっている: batch interval N は清算あたりの noise fill
   確率を N 倍にする（pn_eff = N·pn = 20×0.01 = 0.2）ので、batch20 は事象密度の意味で
   density spoke の ν=10–30 regime に最も近い条件であり、収束の兆候がそこに**だけ**
   出るのは「疎報酬が収束を壊す」という本 finding の機構予測そのもの。
   （ただし 1/5 seed・3/72 セルであり、認定水準ではない。）

## 数値結果 — density spoke（2026-06-11 完了、`results/density.csv`）

実行順序: git 凍結 `3cad65f` → **OSF 公開登録 https://osf.io/63pj2/** → 結果生成。
判定は事前登録規則（`prereg-density-spoke.md`）の機械適用。18 セル × 5 seed。

**規則 2 の判定: 認定可能 regime は存在する**——18 セル中 1 セルが認定。
**規則 3 の headline: `batch5-revisable @ (ν=30, lr=0.15)`**（唯一の認定セル）。
収束 5/5 seed、markup 61.7 ± 5.5、impulse-response gate 通過。
**本プログラム初の認定済み collusion。**

| (ν, lr) | 条件 | markup | conv | cert |
|---|---|---|---|---|
| (10, 0.02) | committed 3 条件 | 4.4–4.9 | 0.2–0.6 | — |
| (10, 0.02) | revisable 3 条件 | 15.5–15.8 | 0–0.4 | — |
| (30, 0.02) | committed 3 条件 | 5.1–6.3 | 0–0.2 | — |
| (30, 0.02) | revisable 3 条件 | 43.8–44.9 | 0.2 | — |
| (30, 0.15) | committed 3 条件 | 8.3–9.7 | 0.6–0.8 | —（exit 0.4 が 2 セル） |
| (30, 0.15) | revisable 3 条件 | 53.7–61.7 | 0.6–**1.0** | **batch5 ✓** |

観測（事前固定した解釈と、事後ラベル付きの注記を区別する）:

1. **lr 対照の帰結は事前固定した 2 分岐のどちらでもなく「逆向き」**だった——
   (30, 0.15) が認定し (30, 0.02) は非認定。事前登録は「(0.02)のみ認定→統計障害」
   「両方認定→密度支配」の 2 枝しか固定していなかったので、以下は**事後解釈**として
   明示する: lr=0.02 は SNR こそ良いが t_max=2×10⁶ 内に limit-cycle へ到達する
   **学習速度が足りない**（conv 0–0.2）。dense regime では利得ギャップ自体が pn に
   比例して育つため、高 lr の Q ノイズ増を許容しても速度が勝つ。収束の律速は
   SNR ではなく適応速度だった。
2. **認定が出たのは sniping を切った世界（revisable）**。committed 側は同 (ν,lr) で
   markup が 1/6 に規律され（53–62 → 8–10）、認定ゼロ、参入不能どころか退出が出る
   （exit 0.4 が 2 セル）。**arbitrageur predation が認定水準の collusion を抑止している**
   という finding 0001 以来の機構像の、認定 gate 水準での初の確認。チャネル帰属の
   定量（Δ_GP / Δ_pred、規則 4）は per-seed 再計算（`scripts/run_attribution.py`、
   決定論再計算）で別途算出。
3. **markup の絶対値（44–62）は解釈しない**（D-B11 の ceiling 注意: dense regime では
   competitive spread（分母）が潰れるため水準は grid 依存。主張は認定の有無と
   同一 grid 内の条件間比較に限定する——事前登録どおり）。

P2 目標文への帰結: 主張 (ii) は肯定枝で立つ——「認定可能 regime は存在するが、
(ν=30, lr=0.15) という**現実の市場 making から遠い高密度・高学習率の隅**にあり、
かつ sniping 規律を切った（revisable）世界でのみ認定される」。BCS 較正点が
この空間のどこに落ちるか（US4）が監査結論の現実接地になる。

## 関連

- 設計: `specs/002-exp-b-collusion-harness/research.md` D-B6（v2）/ D-B9
- 実装: `src/microstructure/qlearn.py::_greedy_cycle_signature`、`designmap.density_spoke`
- 検証: 全 suite 緑のまま（軌道 bit 同一、96 passed）
