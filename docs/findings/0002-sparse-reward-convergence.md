# Finding 0002 — 疎事象市場では Calvano 型「政策収束」が成立しない（収束概念の再設計と認定可能 regime）

**Status**: 機構は検証済（2026-06-11、本番 t_max の pilot ＋ SNR 算術）。coarse 地図と
density spoke の数値は本文末尾（実行ログから追記）。

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

## 数値結果（coarse 72 セル・density spoke — 実行後に追記）

- coarse 地図: `results/coarse.csv`（ledger: `results/budget.json`）
- density spoke: `results/density.csv`
- （本セクションは run 完了後に要約を追記）

## 関連

- 設計: `specs/002-exp-b-collusion-harness/research.md` D-B6（v2）/ D-B9
- 実装: `src/microstructure/qlearn.py::_greedy_cycle_signature`、`designmap.density_spoke`
- 検証: 全 suite 緑のまま（軌道 bit 同一、96 passed）
