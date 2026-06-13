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

## markup の定義と単位（監査、2026-06-11——本文の全表に適用）

定義（一次ソース = `verdict.measure`）: **markup = (realized − nash) / nash**。
realized = 測定窓（ε=0・学習停止・K=10⁴ 期・burn-in 100 期）の**期ごとの勝者
half-spread の平均**——quote ベースで fill 非依存であり、**事象密度に機械的に
スケールする集計量ではない**。nash = **同条件（mechanism × staleness × 較正）の
myopic-Nash spread**（`benchmarks.myopic_nash_spread`）。certify の floor 0.05 は
「自条件の競争水準 +5%」という無次元量で、ν 横断・条件横断で同一の量を測る。

表間でスケールが桁で違うのは**分母の経済**である（測定量の不統一ではない）:

| 条件 | nash（ν=1 baseline） | ν=30 | BCS |
|---|---|---|---|
| committed（cont/batch 共通） | 0.664 | 0.165 | 0.137 |
| revisable（全機構） | 0.300 = grid 下限 | 0.0238 = grid 下限 | 0.0625 = grid 下限 |

committed の競争水準は GM break-even（dense では逆選択/quote が薄まり崩落）、
revisable は sniping 切断で逆選択ゼロ → Bertrand undercut の不動点 = **grid 下限**。
検算: headline（batch5-revisable ν=30）markup 62.05 → realized h = 0.0238 × 63.05 ≈
**1.50**（grid [0.0238, 2] 内、整合）。committed の Nash は機構不変（cont/batch5/batch20
とも同値）なので、**同 staleness 内の Δ 比較（規則 4 の帰属）は分母を共有する**。

**条件間比較の正直な注意**: markup の条件間比較は「自分の競争水準への超過」の比較で
あって絶対 spread の比較ではない。US4 cont の絶対 realized h は committed
{0.133–0.180} vs revisable {0.154–0.219} で**重なる**——完全分離するのは markup
（自条件超過）の方。collusion 関連量は markup が正しい（「自分の競争均衡より上に
留まれているか」が協調の定義）だが、絶対水準の重なりは本注記をもって明示する。

**revisable ベンチマークの grid 依存性**: revisable の Nash = grid 下限は離散 grid の
解像度を継承する（ν=30 で 0.0238、BCS で 0.0625）。よって **revisable markup の
絶対倍率（1.90 等）は grid 不変ではない**。定性的主張（自条件床より上に滞留）は
grid 不変、magnitude の引用には本注記を添える。

**batch 軸の対応関係**: 設計マップ（coarse / spoke / Tier-3）の batch 軸は D-B9 標準の
**N ∈ {5, 20}**、US4 較正セルは venue 写像由来の **N ∈ {10, 100}**（BCS の FBA 提案
0.1–1 s を dt = 0.01 s で換算、D-B10 / calibration.md）。両グリッドは文脈別の正準で
あり混用しない。committed Nash の機構不変は両軸で機械検証済み（ν=30 の {1,5,20} と
BCS の {1,10,100} でいずれも一致）。

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

## 数値結果 — US4 BCS 較正セル（2026-06-11 完了、`results/bcs.csv`）

解釈規則は実行前凍結（`prereg-us4-bcs.md`、commit `bf62434`）。判定: **非認定（予測どおり）**。

- **位置づけ（算術）**: BCS 較正の事象密度 pn = ν·dt = 0.0219/s × 0.01s = **2.19×10⁻⁴/期**。
  認定 headline セル（pn = 0.3）に対し **約 1.4×10³ 倍疎**——現実の ES–SPY は認定可能
  regime から 3 桁強、疎側に位置する。
- **較正セル本番 run**（cont / batch10 / batch100 × committed / revisable、5 seed、
  t_max=2×10⁶）: **6/6 非収束・認定ゼロ**。
- **証拠としての性格（正直に）**: pn × t_max ≈ **438 報酬イベント**であり、baseline
  密度ですらギャップ/ノイズ ≈ 1/8 だった以上、非収束は走る前から算術的に確定していた。
  よってこの run は独立な検証ではなく**プロトコル遵守の実演**（算術との整合確認）。
  本 run が持つ新しい情報は方向パターンの方（下記）。
- **dt 写像の感度**: 位置づけはモデル 1 期 ↔ 実時間の換算（dt=0.01s）に依存するが、
  換算が 1 桁ずれても隔たりは 2 桁残る（137×–13,700×）——疎側の結論は写像誤差に頑健。
- **方向パターン（n=5/セル、非認定・分布レンズの観測）**:
  committed-cont は markup **0.12 ± 0.06** とほぼ競争水準に規律され、batch で
  0.80 ± 0.22 / 0.95 ± 0.12 へ、revisable で **1.51 ± 0.12 / 1.57 ± 0.20 / 1.90 ± 0.18**
  へ——設計マップと同じ二力の向きが実較正点でも再現。
- **cont の committed vs revisable 差の検定（per-seed 決定論再計算、
  `results/bcs_cont_seeds.csv`）**: 設計は**対応あり**（D-B12: master seed の spawn は
  config 非依存 → 同一 seed は条件横断で同一の price/arrival/noise ストリームを共有
  = CRN）。報告順は対応あり設計に従う:
  1. **生データ（n=5 では最強の証拠）**: per-seed markup、committed
     {−0.03, −0.00, 0.14, 0.18, 0.32} vs revisable {1.46, 1.67, 1.78, 2.10, 2.50}。
     ペア差ベクトル = **{+2.18, +1.53, +1.60, +2.13, +1.46}、5/5 全て正**。
  2. **主検定 = 片側 exact 符号検定 p = 1/32 ≈ 0.031**。方向（revisable > committed、
     predation 規律の除去で markup 上昇）は US4 実行**前**の公開 commit で固定済み:
     pilot（`46f5c8c`「revisable で markup が跳ねる」）、density spoke
     （`62bac8f`、認定は revisable のみ）、research-design §9.1（`122ddee`）。
  3. **参考 = paired t = 11.4**（df=4。CRN で共通ノイズが相殺され Welch ≈ 9.2 より
     強い。ペア相関 r = 0.55——CRN が実際に効いている診断）。
  4. 脚注: 標本は完全分離（max committed < min revisable）であり、独立設計なら
     exact Mann-Whitney 両側 p = 2/252 ≈ 0.008——本設計は対応ありのため主検定に
     しない。
  （旧記述「非対の比較で約 9SE」は CRN 構造の見落としで、本記述で置換。）
- **二レンズの読み（writeup に固定する構成）**: 認定ゲートのレンズでは現実密度で
  何も見えない（認定ゼロ）が、**分布のレンズでは同じ較正点の revisable 世界で
  markup 1.5–1.9 が滞留している**（＝実現 spread が自条件競争水準（grid 下限）の
  2.5–2.9 倍。単位は冒頭の監査注記、絶対 spread は committed と重なる点も同所）。
  つまり「収束した政策としての
  共謀は現実密度で出現しない」と「非収束の遊走行動の時間平均は超競争水準に
  滞留しうる」は同じデータの両面であり、後者こそ監視単位を『収束した政策』でなく
  『行動分布』に置くべき理由になる。**認定ゲート単体は監視標準にならない**——
  ゲートは監査の道具（笛が鳴ることの証明）、監視の道具は分布統計。この二レンズ
  構成を対象別の文（JPX/日銀）で分割せず、同一の文章構造として書く。
  **監視レンズのベンチマーク依存性（明示必須）**: ここで「行動分布」と呼ぶものは
  正確には**モデルベースの競争ベンチマークに対する相対分布（markup 分布）**である。
  現実的密度では**生のスプレッド分布は committed と revisable で重なり**（上記
  絶対値注記）、分離するのは自条件 Nash への超過だけ——そしてベンチマーク推定には
  staleness・逆選択構造の知識が要る。「生のスプレッド分布を見ればよい」は本データに
  反する誤読であり、**ベンチマーク込みの監査装置が要ること自体が本 harness の
  必要性の論拠**になる（監視側の文はこの一文を必ず伴う）。
- 予算: 総消費 996M 期（coarse 739M / dense 197M / robustness 60M、各 tier cap 内）。

### 規則 4（従の主張: Δ 帰属、per-seed 決定論再計算、`results/attribution_seeds.*`）

認定 (ν=30, lr=0.15) 上の batch 変調は **n=5 で全分類「無影響」**（±2SE 規則）:
Δ_total(N=5) = −0.91 ± 1.16、Δ_GP(N=5) = +8.00 ± 15.36、Δ_pred(N=5) = −8.92 ± 15.15
（N=20 も同様に null）。revisable 世界の seed 間分散が巨大で、5 seed では方向を
主張できない——**従の主張はここで正直に縮む**（事前登録の縮退規則どおり、
変調の確定主張はしない）。符号は Δ_GP 正・Δ_pred 負と二力の予測と整合する向きだが、
有意性なし。注記: batch5-revisable が認定し cont-revisable が非認定だった差は
markup 水準差（+8.0 ± 15.4、無意味）ではなく**収束 frac の差**（1.0 vs 0.6）に由来。
変調の検出力を上げる正当な経路は D-B9 Tier-3（headline ≥20 seed）のみ。

## 数値結果 — Tier-3 robustness（2026-06-11 完了、`results/tier3.csv`）

解釈規則は実行前凍結＋未読 clarification 2 本（`prereg-tier3.md`、commits `1c73364`/
`990eddc`/`fbc1b01`）。判定は凍結規則の機械適用。

**規則 1（維持判定）: 降格。** center（q-learning、n=20 プール）は certified=False。
失敗成分は**収束全数条項**——収束 frac 0.90（18/20）で、markup 成分はプールで
余裕を持って通過（62.05 ± 2.41、mean − 2SE ≫ floor）。§2.5 の事前算術が指定した
とおり、p̂ = 0.90 は「維持確率 p²⁰ ≈ 0.12、降格がモーダル」の p 域であり、
**この降格は事前注記した解釈に従って「厳格プール基準の非生存」であって
「regime の不在」ではない**（conv 0.90 は遊走ではなく「ほぼ常に収束するが全数には
届かない」を意味する）。headline は事前規定どおり
**「n=5 では認定、n=20 プール基準では非生存（収束 18/20）」へ降格**して報告する。

**規則 2（SARSA ×20）**: certified=False（収束 frac 0.60）。markup 帯域は同水準
（50.5 ± 3.1）。ラベル: プール認定はアルゴ横断で非生存だが、supra-competitive
帯域への滞留はアルゴ横断で再現。

**規則 3（HP 感度一覧、n=5・確定主張なし・headline 判定に不使用）**:

| 変種 | markup | conv | cert | exit |
|---|---|---|---|---|
| tie=rotate | 67.9 ± 5.6 | 0.8 | False | 0.2 |
| lr ×0.5 (0.075) | 60.1 ± 7.3 | 0.6 | False | 0.2 |
| lr ×2 (0.30) | 73.5 ± 4.0 | **1.0** | True | 0.2 |
| eps_beta ×2 | 57.5 ± 5.1 | 1.0 | False | 0 |
| eps_beta ×0.5 | 59.7 ± 8.6 | 0.2 | False | 0.2 |
| γ = 0.90 | 55.4 ± 5.7 | 0.4 | False | 0 |
| γ = 0.99 | 56.9 ± 2.6 | 0.6 | False | 0 |

観測（一覧として）: 収束 frac は lr に単調（0.075→0.6、0.15→0.9、0.3→1.0）、
探索減衰の速さにも単調（eps_beta ×0.5→0.2、×2→1.0）——「律速は適応速度」という
spoke の事後解釈と整合する向き。lr=0.3 セルは certify=True を返すが、規則 3 の
firewall により n=5 の個別セル確定主張はせず、headline にも昇格させない
（追加検証の候補としてのみ記録。やるなら新規事前登録で——**その際、収束条項を
all-n で再建しない**: p²⁰ 算術から逆算した k-of-n（例: p=0.95 で維持確率 ≥ 0.8 を
与える k=18/20）を検出力計算つきで選び、今回の脆さを構造として再生産しない）。

**規則 4（Δ 帰属の n=20 再判定、`results/attribution_seeds20.*`）**: **全分類「無影響」の
まま**——事前規定（「分類が動いた場合のみ従の主張を更新」）により従の主張は更新しない。
Δ_total(N=5) = −0.17 ± 0.56、Δ_GP(N=5) = +5.13 ± 4.68、Δ_pred(N=5) = −5.30 ± 4.61
（N=20 も同様に null）。**MDE 併記（±2SE 規則の検出限界、棄却失敗 ≠ ゼロ）**:
Δ_total の MDE ≈ 1.1、Δ_GP ≈ 8.4–9.4、Δ_pred ≈ 8.1–9.2（markup 単位）。つまり
total は MDE ≈ 1.1 まで絞れた上での null だが、**チャネル分解（GP/pred）は
検出限界 ≈ 8 の低検出力**であり、「無影響」は「検出限界以下」としてのみ主張する。
GP と pred の点推定が逆符号で並ぶ見た目を「チャネルが相殺」とは書かない（相殺は
両効果の存在を含意する——正しくは「いずれも検出限界以下」）。確定文:
「認定 regime 上の batch 変調は、total では MDE ≈ 1.1 の下で、チャネル分解では
MDE ≈ 8 の下で、いずれも検出されない」。

**最終予算（並行書き込み incident 後の artifacts 再構成値、0002b 参照）**:
coarse 739.2M / dense 410.4M / robustness 191.0M——全 tier cap 1×10⁹ 内。
dense の attr20 未収束情報分は planned 上限で計上（残予算を過小評価する安全側）。

P2 主張 (ii) の最終形（降格枝、§2.5 の非対称どおり）:
「認定可能な regime は (ν=30, lr=0.15) 近傍の revisable 世界に** n=5 プール水準で**
存在するが、n=20 の厳格プール基準は生き残らない——**非生存の成分は収束全数条項のみ
（18/20）であり、markup プールは余裕で通過した（62.1 ± 2.4、mean − 2SE ≫ floor）**。
supra-competitive 帯域への滞留（markup 50–74、SE 2.4–8.6）は seed・アルゴ・HP
横断で再現する」——降格の中身が「価格水準は維持・収束だけ全数に欠けた」である
ことは二レンズ構成の核心情報であり、認定ゲートのレンズと分布のレンズの乖離は
ここでも US4 と同じ構造で現れている。

## Limitations（writeup 最終化前に固定した文言、2026-06-11）

1. **表形式スコープ**: 本研究の主語は「Calvano 忠実移植の表形式 Q/SARSA、この予算」で
   ある。現実の HFT MM は関数近似・永続メモリ・桁違いのデータで学習しており、表形式の
   サンプル非効率は現実の制約ではない。よって対外的な一文には必ず
   **「本パラダイム（表形式学習）の枠内では」**を入れ、「現実市場で共謀リスクが低い」
   と読まれる書き方を避ける。本研究は **Calvano パラダイムの移植可能性についての主張**
   であり、現実市場の共謀リスク評価ではない。関数近似アームは本 feature に存在しない
   （将来 feature の領分）。
2. **事象密度は束である**: ν 軸は報酬の疎さ・監視シグナルの疎さ（Green-Porter 的な
   逸脱検知の困難）・学習統計（サンプル数）を**束ねて**動かす。lr 対照は学習統計を
   部分的に分離するが、「報酬は密・観測だけ疎」の分離軸は LearnConfig に存在しない。
   よって claim (i) は「**事象密度（報酬・監視・学習統計を束ねた）が Calvano 移植の
   一級障害**」という束の主張として書き、成分分離は主張しない（分離アームは
   将来 feature）。
3. **D-B11（弾力需要）descope**: baseline は inelastic noise であり、stage-game の
   collusive ceiling は action grid 上限で外生的に決まる。留保 spread R の robustness
   軸は本 feature では未実行。「Bertrand 特殊性への依存」を主張する以上ここは聞かれる
   ——descope を明記し、markup の主張を認定の有無と同一 grid 内比較に限定する
   （本文の各所で適用済み）。
4. **価格発見**: 外生 true price の harness であり、collusion の価格発見への害は
   scope 外（research-design §2.6 のとおり）。

## 関連

- 設計: `specs/002-exp-b-collusion-harness/research.md` D-B6（v2）/ D-B9
- 実装: `src/microstructure/qlearn.py::_greedy_cycle_signature`、`designmap.density_spoke`
- 検証: 全 suite 緑のまま（軌道 bit 同一、96 passed）
