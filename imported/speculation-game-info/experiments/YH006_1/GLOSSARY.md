# YH006_1 用語索引 (GLOSSARY)

YH006_1 の文書群（README.md, SPECv2.0.md, docs/findings.md）に登場する略語・記号・固有名詞をカテゴリ別にまとめた索引。

---

## 実験条件 (C0u / C0p / C2 / C3 …)

| 記号 | 正式名 | 内容 |
|---|---|---|
| **C0u** | Aggregate + Uniform | 集計需要型世界・初期wealth均一分布。aggregate world のベースライン。 |
| **C0p** | Aggregate + Pareto | 集計需要型世界・初期wealthをPareto分布（α=1.5）で与えたもの。 |
| **C2** | LOB + Uniform | PAMS注文板世界・初期wealth均一。LOBベースライン。 |
| **C3** | LOB + Pareto | PAMS注文板世界・初期wealth Pareto。主な観察対象条件。 |
| **C2_A1** | LOB + Uniform + q固定 | C2にablation A1を適用。q=q_constで全agent同一注文サイズ。 |
| **C3_A1** | LOB + Pareto + q固定 | C3にablation A1を適用。**因果検証の主役条件**。 |
| **C3_A3** | LOB + Pareto + 寿命上限 | C3にablation A3を適用。agent をτ_maxステップで強制交代。 |

> **読み方のコツ**: 先頭の「C」は Condition、数字は世界軸 (0=aggregate, 2/3=LOB)、アルファベット末尾が初期wealth分布 (u=uniform, p=pareto)。`_A1`/`_A3`はablation変形。

---

## ステージ (S1 〜 S7, S1-secondary)

実験をシミュレーション負荷の小さい順に段階分けしたもの。

| 記号 | 内容 | 新規シミュレーション |
|---|---|---|
| **S1** | Phase 1の既存データ（1 trial）を追加指標で再分析 | 不要（数分で完了） |
| **S1-secondary** | S3完了後に改めてS1相当の分析を100 trial CIで再実施、plan A/B 分岐を確定 | 不要 |
| **S2** | aggregate条件（C0u/C0p）の100 trial ensemble実行 | 必要 |
| **S3** | LOB条件（C2/C3）の100 trial ensemble + 4条件 interaction算出 | 必要 |
| **S4** | A1 ablation の試験実装とq_const較正（pilot 数 trial） | pilotのみ |
| **S5** | C2_A1/C3_A1 の100 trial ensemble | 必要 |
| **S6** | A3 ablation 実装・τ_max較正・C3_A3の100 trial ensemble | 必要 |
| **S7** | 全指標集計、図表生成、README/proposal素材の完成 | 不要 |

> **現状（2026-05）**: S1/S2/S3 完了。S4以降（ablation）は未実施。

---

## 成功基準 (L1 〜 L4)

論文・proposalとしての価値がどの水準に達したかを表す。

| 記号 | 内容 |
|---|---|
| **L1** | F1（ファネル交互作用）が Spearman・Kendall・bin variance のうち2つ以上で同じ方向 → 「Pearsonの外れ値artifact」でないことの確認 |
| **L2** | A1 ablation でinteractionが50%以上縮小 + bootstrap 95% CIが0を含まない → 因果経路（q）の特定 |
| **L3** | A3 ablation でも部分縮小（≥30%）+ lifetime・wealth persistence 中間予測が仮説Aと整合 → chain全体の検証 |
| **L4** | L1+L2+L3 + funnel直接指標（bin variance）+ timescale解析で interaction が長期的に消えない → proposal級の証拠 |

> **現状**: L1は達成見込み（S1/S3の指標が同方向）。L2以降はablation未実施のため判定不能。

---

## 仮説 (仮説A / 仮説B / 仮説C)

F1（ファネル交互作用）がなぜ生じるかの候補説明。

| 記号 | 名称 | 機構の説明 |
|---|---|---|
| **仮説A** | q-pollution仮説 | LOBでは約定率が低くagentが長生きするため、初期Pareto wealthが「流れずに残る」。残ったwealthが q=⌊w/B⌋ 経路で注文サイズに伝播し、ファネル構造を汚染（pollute）する |
| **仮説B** | 戦略選択仮説 | wealthが高いagentが選択的に長/短horizonのround-tripを取る（wealth ↔ 戦略テーブルの相関）。q経路とは独立 |
| **仮説C** | fill非対称仮説 | q の大きい注文ほどLOBで約定しにくく、wealth依存的に約定パターンが変わる |

> A1 ablationで交互作用が消えれば → 仮説A支持。消えなければ → 仮説B/Cを疑う。

---

## Ablation (A1 / A3)

モデルの一部を「切り取って」因果関係を特定する操作実験。

| 記号 | 操作内容 | 検証対象 |
|---|---|---|
| **A1** | 全agentのq（注文サイズ）を定数 `q_const` に固定（wealth依存性を除去） | wealth→注文サイズの伝播経路（仮説Aの核心）を遮断できるか |
| **A3** | agent が `τ_max` ステップ生存したら強制交代（寿命上限） | LOBでの長寿命・wealth persistence が F1 に必要か |

> **注**: A2 という ablation はこの研究に存在しない（A1とA3のみ）。条件番号（C2, C3）と混同しないよう注意。

**較正パラメータ**:
- `q_const`: C3のpilot 5 trial から `median(q_i(t))` を取り、5 trial の中央値として決定
- `τ_max`: C3のagent lifetime中央値 `L_50` × 0.5 を初期値として決定

---

## 主要指標・統計量

### ファネル構造の計測

| 記号 | 読み方 | 意味 |
|---|---|---|
| **F1** | エフワン | "Funnel 1" — LOBで観察されたファネル交互作用そのもの。「LOB環境ではPareto初期分布がfunnel構造を弱める（C0pではほぼ弱まらない）」という効果 |
| **ΔG** | デルタG | round-trip一往復の損益（利益：正、損失：負） |
| **\|ΔG\|** | 絶対値デルタG | ΔGの絶対値。損益の「大きさ」 |
| **h** | エイチ / horizon | round-tripのステップ数（= 開始から終了までの時間） |
| **corr(\|ΔG\|, h)** | — | \|ΔG\|とhの相関。これがファネル構造の強さを表す主指標 |
| **Interaction** | — | 差の差：`(C3−C2)−(C0p−C0u)` = LOBでのPareto効果がaggregateでのPareto効果からどれだけズレるか |

### 相関係数の種類

| 記号 | 正式名 | 特徴 |
|---|---|---|
| **ρ_P / rho_pearson** | Pearson相関係数 | 線形相関。外れ値（重尾分布）に弱い。Phase 1互換のため計算するが主指標ではない |
| **ρ_S / rho_spearman** | Spearman順位相関 | **主指標**。順位ベースで外れ値に頑健 |
| **τ_K / tau_kendall** | Kendall τ | 一致ペアの割合。3指標中最も外れ値に頑健 |

### ファネル直接計測

| 記号 | 内容 |
|---|---|
| **bin_var_slope** | h をlog等間隔15ビンに分け、各ビン内で `Var(log\|ΔG\|)` を計算。hが大きいほどbinVarが大きければファネル本体の証拠 |
| **q90_q10_slope_diff / qreg_slope_diff** | h → ΔGのquantile回帰を τ={0.10, 0.50, 0.90} で実施。`slope_0.90 − slope_0.10` でファネルの「開き幅」を定量化 |

### その他の指標

| 記号 | 内容 |
|---|---|
| **Hill α / hill_alpha** | \|ΔG\| の分布の冪指数（tail index）。小さいほど重尾。Hill (1975) の推定量 |
| **lifetime** / **lifetime_median** | 各agentが市場に滞在したステップ数 |
| **censoring 率** | sim終了時点でまだ退場していないagentの割合（LOBでは agent が長生きするため高くなる） |
| **wealth_persistence_rho** | agent単位で `corr(w_init, w_final)` を計算。LOB + Pareto条件で高い → 初期格差が最後まで残る |
| **forced_retire_rate** | `wealth < B` で強制退場したagentの単位時間あたり件数 |
| **corr(w_init, h)** | 初期wealthとround-trip horizonの相関。仮説B（strategy selection）の検出用 |

---

## 統計設計

| 記号 | 内容 |
|---|---|
| **CI** | Confidence Interval（信頼区間）。本研究では 95% percentile bootstrap（10,000 resample）を使用。Fisher-z変換は重尾分布で不適なため不採用 |
| **bootstrap** | 100 trial 分のρ値を10,000回リサンプリングして経験的CI を構成する手法 |
| **bootstrap 10,000 resample** | 100 trial の標本を（復元抽出で）10,000回繰り返し、第2.5/97.5パーセンタイルをCIの上下限とする |
| **Mann-Whitney U test** | 2条件間の分布差の検定。ノンパラメトリックで正規性不要。ablation効果の有意性判定に使用 |
| **Bonferroni補正** | 多重比較の補正。4系統の主検定に対し有意水準を α = 0.05/4 = 0.0125 に調整 |

---

## Plan B シナリオ (α〜ε)

S1の結果によってF1の解釈が変わる場合の分岐。

| 記号 | Pearson | Spearman | bin variance | 解釈 |
|---|---|---|---|---|
| **α** | 動く | 動く | 動く | F1は本物。ablation継続 |
| **β** | 動く | 動かない | 動かない | Pearsonの外れ値artifact。F1そのものが虚偽 |
| **γ** | 動く | 動かない | 動く | 分散構造だけ変質。主指標をbin varianceに置換して継続 |
| **δ** | 動く | 動く | 動く（後半消失） | LOBの時間スケールが遅いだけ。「半減期の差」を主結果に |
| **ε** | 動く | 動く | 動く | A1で消えない。仮説Aではなく仮説B/未知の機構 |

---

## 環境・モデル

| 記号 | 内容 |
|---|---|
| **SG** | Speculation Game（Katahira & Chen 2019）。agent の注文サイズが口座残高 w に連動する ABM |
| **LOB** | Limit Order Book（指値注文板）。現実の取引所の構造を模したシミュレーション環境 |
| **aggregate** | 集計需要型の価格更新（`Δp = D/N`）。LOBなし、約定即成立 |
| **PAMS** | Platform for Agent-based Market Simulation（Hirano & Izumi 2023）。本研究のLOB環境 |
| **MMFCN** | Market Making FCN agent。PAMS上で流動性（指値注文）を供給する外部agent（30体）。これがいないとSG agentの注文が約定しない |
| **FCN** | Fundamental / Chart / Noise trader を統合したエージェント型 |
| **round-trip** | あるagentが「open（買/売）→ close（反対売買）」を完了させた1往復取引 |

### モデルパラメータ

| 記号 | 値 | 意味 |
|---|---|---|
| **N** | 100 | SG agent数 |
| **M** | 5 | 認知履歴のビット長（`2^M = 32` 種の市場状態を識別） |
| **S** | 2 | 各agentが持つ戦略テーブル数 |
| **B** | 9 | 注文サイズ基準値（q = ⌊w/B⌋ の分母） |
| **C** | 3.0 | 認知閾値（価格変動をシグナルとして認識する最低幅） |
| **T** | 50000 (agg) / 1500 (LOB) | シミュレーション長（ステップ数） |
| **q** | = ⌊w/B⌋ | 各agentの注文サイズ（wealthをBで割った切り捨て整数） |
| **w** | — | 各agentの口座残高（SG内部の「認知的wealth」） |
| **q_const** | pilot較正値 | A1 ablation用の固定注文サイズ |
| **τ_max** | ≈ 0.5 × L_50 | A3 ablation用の最大寿命ステップ数 |
| **L_50** | — | C3条件でのagent lifetime中央値 |
| **warmup** | 200 steps | LOB計測前の「助走」期間 |
| **c_ticks** | ≈28 tick | SG認知閾値Cのtick単位換算値（= 3 × median\|Δmid\|） |

---

## 系譜・文書上の位置付け

| 記号 | 指す実験 |
|---|---|
| **Phase 1** | YH006（1 trial の単発実験、F1を初発見） |
| **Phase 2** | YH006_1（本実験。100 trial ensembleとablation） |
| **YH006_2** | Phase 2以降の後継（LOBで論文1+2の完全再現、LIMIT_ORDER拡張など） |
| **YH007** | Self-organized SG on LOB（認知閾値Cを内生化） |
| **論文1** | Katahira et al. (2019) Physica A 524（Fig.11/12/13を含む） |
| **論文2** | Katahira & Chen (2019) arXiv:1909.03185 |
| **Layer 2** | dynamic-wealth layer — 口座残高のヘテロ性が注文サイズに伝播する機構層 |
