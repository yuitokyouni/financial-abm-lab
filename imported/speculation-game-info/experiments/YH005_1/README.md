# YH005-1 Phase 1: Speculation Game の 3 層機構 — 機構実証 figure 集

YH005 Lite (Speculation Game の最小実装 + 3 モデル比較) が「SG は stylized facts を再現する」を示した上で、本 YH005-1 は一歩踏み込んで **SG の 3 層機構** — (i) cognitive world (quantized history H(t) / cognitive price P(t))、(ii) round-trip 制約 (wealth 凍結)、(iii) dynamic wealth (破産置換による turnover) — が **数値的にどう現れるか** を 5 枚の figure で可視化する。

本 Phase 1 は **論文2 (Katahira & Chen 2019 arXiv:1909.03185) の機構分析 Fig. 2/4/7/8/10 の再現**に相当する。parameter scan や 100 trial 平均は Phase 2 以降に送る。

---

## Phase 1 の 5 figure と主張

| 図 | ファイル | 対応する論文2 Fig. | 主張 |
|---|---|---|---|
| 1 | `results_wealth_pareto.png` | Fig. 4 | wealth が **Pareto 分布** に発達する (破産置換のある dynamic wealth 層が産み出すテール) |
| 2 | `results_horizon_distribution.png` | Fig. 8 | round-trip 長が **冪的分布** を持つ (認知価格 P の反転タイミングが multi-scale) |
| 3 | `results_deltaG_vs_horizon.png` | Fig. 7 | 長い round-trip ほど ΔG (認知 P&L) のばらつきが **漏斗状に拡大** する |
| 4 | `results_hold_ratio.png` | Fig. 10 | **active_hold / passive_hold が有意な割合** を占める (round-trip 制約がポジション滞留を強制) |
| 5 | `results_order_size_time_series.png` | Fig. 2 | **large order の burst 期が r(t) の高 volatility 期と同期** (wealth 不均一 → 大口注文がスパイク時に集中) |

この 5 枚が揃うことで「SG の volatility clustering + heavy tail は 3 層機構の相互作用から生まれる」という主張が数値的に裏打ちされる。

---

## 実行

```bash
cd experiments/YH005_1
python phase1_mechanism_figures.py
```

- 実行時間: 約 100 秒 (Apple Silicon, T=50000, N=1000, S=2, M=5)
- 出力: 5 PNG + `outputs/phase1_metrics.json`

YH005-1 は YH005/ をそのまま import する (`sys.path.insert` で `experiments/YH005/`)。YH005/ 自体は凍結。

## パラメータ (Phase 1 固定)

```
N = 1000, M = 5, S = 2, T = 50000
B = 9,    C = 3.0,  seed = 777,  p0 = 100.0
history_mode = 'endogenous',  decision_mode = 'strategy'
order_size_buckets = (50, 100)   # small <= 50 < medium <= 100 < large
```

Phase 2 以降で parameter scan を導入するときに CLI 引数化する。

---

## 観測された数値 (seed=777, 1 trial)

Hill 推定は `xmin = 90th percentile` で固定 (Phase 1 では論文の poweRlaw ではなく単純な方式を採用)。

| 図 | 指標 | 実測 | 期待 / 論文値 |
|---|---|---|---|
| 1 Pareto | α (Hill, xmin=p90) | **2.54** | 論文2 Fig. 4 の α ≈ **1.94** と同じ桁、tail は我々がやや軽い |
| 1 Pareto | median wealth | 41.0 | — |
| 1 Pareto | max wealth | 998 | — |
| 2 Horizon | # round trips K | **10,419,681** | — |
| 2 Horizon | median / mean | **2 / 3.3** steps | 論文2 Fig. 8 と定性一致 (右下がり log-log) |
| 2 Horizon | p90 / max | 8 / 484 | — |
| 3 ΔG vs h | corr(|ΔG|, τ) | **+0.416** | 論文2 Fig. 7 の「漏斗」形に対応 |
| 4 Hold ratio | passive_hold | **0.251** | > 0.20 ✓ |
| 4 Hold ratio | active_hold | 0.237 | 論文2 Fig. 10 (M=5) と同水準 |
| 4 Hold ratio | buy / sell | 0.212 / 0.212 | 対称 ✓ |
| 4 Hold ratio | idle | 0.088 | — |
| 5 Order size | mean(small/med/large) | 415.9 / 0.8 / 0.1 | small が支配 (Fig. 2 と定性一致) |
| 5 Order size | peak(large) | 12 agents/step | burst 期と visual 相関 (目視で確認) |

`n(p ≤ 0)` = 0 (シミュレーション全期間で p は [92.00, 107.13] に収まる、extreme state 不発)。このため (5) の return パネルは論文通り r(t) = ln p(t) − ln p(t-1) をそのまま使っている。

**単一 trial 揺らぎ**: 論文2 は α ≈ 1.94 だが本実装は 2.54。これは seed=777 単体の finite-sample 揺らぎ + §4 の設計ホール (tie-break, H(0) 初期化など) の違いによる。Phase 2 の 100 trial 平均で論文値に近づくか検証する。

---

## simulate/model の拡張 (YH005 Lite への追加)

Phase 1 のために YH005/model.py (run_reference) と YH005/simulate.py に以下を追加した。**RNG 消費順は不変** — 既存 14 + 新規 4 = 18 parity/invariant テストが全通過することで bit-parity を保証。

返り値 dict の追加キー:

- `round_trips`: close イベント毎の 1 レコード (dict of 6 arrays):
  - `agent_idx (K,)` `open_t (K,)` `close_t (K,)`
  - `entry_action (K,)` `entry_quantity (K,)` `delta_G (K,)`
- `num_orders_by_size (T, 3)`, `num_orders_by_size_buy (T, 3)`, `num_orders_by_size_sell (T, 3)`: 各 step の注文量 bucket 件数 (small/medium/large)

新しい state:

- Agent に `entry_step` を追加 (open 時に `t` を記録、close/substitute でクリア)。
- 新引数 `order_size_buckets=(50, 100)`。

新テスト (`YH005/tests/test_parity.py`):

- 既存 14 ケース全てで round_trips 6 配列 + num_orders_by_size 3 配列を含む parity チェック
- `test_roundtrip_invariants` (seed=1, 42): close_t > open_t / 非減少 / entry_action ∈ ±1 / entry_quantity ≥ 1
- `test_order_size_bucket_invariants` (seed=1, 42): bucket 合算と num_buy/num_sell の一致 (要素単位)

---

## Phase 1 スコープ外 (Phase 2 以降に送る)

- **parameter scan**: M-B phase diagram、kurtosis vs S / vs C、Gini vs B
- **100 trial 平均**: 単一 trial 揺らぎの除去、論文値への収束確認
- **論文1 Fig. 11/12/13**: asymmetry in time scales / leverage effect / gain-loss asymmetry
- **MGDC 実装** (Challet-Chessa-Marsili-Zhang 2001): SG vs MGDC の直接比較
- **Self-organized SG** (Physica A 2021): 派生モデル
- **Pareto MLE 精密版** (Clauset-Shalizi-Newman 型): 本 Phase は Hill α のみ
- **論文2 Fig. 10 の M-sweep**: 本 Phase は M=5 単体の 1 本棒

上記は Phase 2 以降のタスクとして明確化されている。本 Phase で "ついで" に実装しない。

---

## ディレクトリ構成

```
experiments/YH005_1/
├── __init__.py
├── phase1_mechanism_figures.py              # メインスクリプト
├── results_wealth_pareto.png                # Fig 4 相当
├── results_horizon_distribution.png         # Fig 8 相当
├── results_deltaG_vs_horizon.png            # Fig 7 相当
├── results_hold_ratio.png                   # Fig 10 相当
├── results_order_size_time_series.png       # Fig 2 相当
├── outputs/
│   └── phase1_metrics.json                  # 全図の返り値 dict を集約
└── README.md
```

---

## 参考文献

- Katahira, K., Chen, Y. (2019). *Heterogeneous wealth distribution, round-trip trading and the emergence of volatility clustering in Speculation Game.* arXiv:1909.03185.  (**論文2、Phase 1 の主要参照**)
- Katahira, K., Chen, Y., Hashimoto, G., Okuda, H. (2019). *Development of an agent-based speculation game for higher reproducibility of financial stylized facts.* Physica A, **524**, 503–518.  (論文1)
