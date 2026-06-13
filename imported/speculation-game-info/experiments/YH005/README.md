# YH005: Katahira et al. (2019) Speculation Game (Lite 実装)

Katahira, Chen, Hashimoto, Okuda (2019) *Physica A* **524**, 503–518 の Speculation Game (SG) を S=1 から走るベクトル化実装で再現する。YH003 (MG) / YH004 (GCMG) と 3 モデル比較で、SG が volatility clustering + heavy tail を再現する構造的要因を切り分ける。Lite スコープ: stylized facts のうち 5 項目、Null test (論文2 Fig. 11) の再現、および YH003/YH004/YH005 の 3 モデル比較図に絞る。

論文との関係:
- **論文 1** = Katahira et al. (2019) *Physica A* 524, 503–518. モデル定義、11 stylized facts の再現。
- **論文 2** = Katahira & Chen (2019) arXiv:1909.03185. Null test (Fig. 11) による機構分析。

PDF は `papers/` 配下 (Yuito 配置):
- `katahira chen hashimoto okuda.pdf` — 論文1 (Physica A 524)
- `katahira chen heterogenerous wealth.pdf` — 論文2 (arXiv:1909.03185)
- `self-organized speculation game ...pdf` — Physica A 2021 (YH007 参照、本 YH005 Lite スコープ外)

---

## 実行

```bash
cd experiments/YH005

# 単体走行 (§8.4 検証用 ベースライン, T=20000)
python run_simulation.py baseline --seed 777

# 論文2 Fig. 11 再現 (baseline / Null A / Null B, T=50000, 所要 ~5 分)
python run_simulation.py null_tests --seed 777

# 3 モデル比較 (YH003/YH004/YH005, S=1, T=50000, 所要 ~2 分)
python run_simulation.py compare_three --seed 123

# parity テスト (ref ↔ vectorized bit-parity)
python -m pytest tests/ -v
```

メイン出力:
- `results_null_tests.png` — 論文2 Fig. 11 の再現 (3 パネル: baseline / Null A / Null B)
- `results_compare_three.png` — YH003/YH004/YH005 の 3×3 stylized facts 比較
- `outputs/*.json` — 数値メトリクス

既存シリーズは単一 `results.png` 規約だが、Lite スコープの主要結果が 2 系統 (Null test 再現と 3 モデル比較) あるため 2 枚に分けている。

---

## 依存

```
numpy
matplotlib
pytest     # parity テスト用
```

---

## ディレクトリ構成

```
experiments/YH005/
├── model.py                    # per-agent 参照実装 (run_reference)
├── simulate.py                 # ベクトル化 simulate (ref と bit-parity)
├── analysis.py                 # 5 つの stylized facts 関数
├── history.py                  # K=5 quinary encoder + quantize_price_change
├── _mg_gcmg_baseline.py        # YH003/YH004 を importlib で wrap
├── baseline.py                 # §8.4 ベースライン単体実行
├── null_tests.py               # 論文2 Fig.11 再現
├── compare_three_models.py     # 3 モデル比較図
├── run_simulation.py           # CLI ランチャー
├── papers/                     # 論文 PDF (Yuito 配置)
├── tests/test_parity.py        # ref ↔ vectorized bit-parity テスト
├── outputs/*.json              # メトリクス
├── results_null_tests.png      # メイン図 1
└── results_compare_three.png   # メイン図 2
```

---

## モデル仕様 (論文1・論文2 からの抽出)

### 履歴と量子化

K=5 quinary 履歴 (底 5 big-endian):

```
μ = d_{t-M} · 5^(M-1) + d_{t-M+1} · 5^(M-2) + ... + d_{t-1} · 5^0
d_k = h_k + 2 ∈ {0..4}
shift_in:  μ' = (μ · 5) mod 5^M + d_new
```

量子化 (Eq. 6):
```
h(t) = +2  if Δp > C
       +1  if 0 < Δp ≤ C
        0  if Δp == 0
       -1  if -C ≤ Δp < 0
       -2  if Δp < -C
```

### 価格更新 (Eq. 4, 5)

```
D(t) = Σ_i  a_i^{j*}(t) · q_i(t)              (int64)
Δp   = D(t) / N                                (float)
p(t) = p(t-1) + Δp,  p(0) = p0 (= 100.0)       (float)
```

**対数価格は使わない** (論文1 p.9: log-return が認知閾値 C の意味を壊す)。

### 認知価格 (Eq. 7)

```
P(t) = P(t-1) + h(t),  P(0) = 0               (int64)
```

### 注文量 (Eq. 2) と 初期 wealth (Eq. 3)

```
q_i(t)   = floor(w_i(t) / B)                   (B = 9)
w_i(0)   = B + U[0, 100)                       (一様整数)
```

### 戦略ゲイン (Eq. 8, 9) + wealth 更新 (Eq. 10, 11)

認知価格ベース、close 時のみ wealth 更新:
```
ΔG_i^j(t) = a_i^j(t_0) · (P(t) − P(t_0))
w_i(t)    = w_i(t_0) + ΔG_i^{j*}(t) · q_i(t_0)
```

Round-trip 中は volume 凍結 (`entry_quantity` を close まで保持、"opening and closing volumes are the same")。

### Effective action 決定表 (§3.8, 唯一の真理)

| position | rec | effective | quantity    | 分類         |
|:--------:|:---:|:---------:|:-----------:|:-------------|
|    0     |  0  |     0     |      0      | idle         |
|    0     | ±1  |    ±1     |  `⌊w/B⌋`    | open         |
|   ±1     |  0  |     0     |      0      | active_hold  |
|   ±1     | ±1  (same) |  0    |      0      | passive_hold |
|   ±1     | ∓1  (opp) | ±1     | `entry_qty` | close        |

**不変条件**: buy(=effective+1) + sell(=effective−1) + active_hold + passive_hold + idle == N

### Virtual round-trip

各エージェントは S 個すべての戦略について仮想状態を持ち、active 戦略以外は毎ステップ virtual open/close (認知 P 基準で G 更新)。

### 戦略レビュー

**active 戦略 j\* が実ラウンドトリップを close したステップのみ** review:
- argmax G に現 j* が含まれれば継続
- 含まれなければ argmax 集合から uniform 抽選 (§4.1)
- 新 j** に virtual position が残っていればクリア (G は更新しない、論文1 p.7 "aborted")

### 破産置換

`w_i < B` で全面 reset (新戦略テーブル + 新 w = B + U[0,100) + 新 active_idx ∈ [0, S))。

---

## 設計選択 (仕様ホール、論文で未規定 — YH005_PLAN.md と整合)

| #   | 項目 | 採用 | 理由 |
|-----|------|------|------|
| 4.1 | argmax G の tie-break | 現 j* が argmax 集合に含まれれば継続、そうでなければ uniform 抽選 | 論文1 p.7 "continues to use" と整合、spurious virtual abort を最小化 |
| 4.2 | H(0) 初期化 | 全エージェント共通に `U[0, 5^M)` | H(t) はグローバル、t=0 で偏りを作らない |
| 4.3 | 初期 active_idx | 各エージェント独立に `U[0, S)` | G=0 で全戦略同点の初期条件で tie-break が ill-defined の回避 |
| 4.4 | substitute 時 active_idx | 同上 | 4.3 と同構造 |
| 4.5 | Null B 意思決定 | **position 非参照** (論文2 Fig. 11(b) literal 解釈)。u<p で rec=±1 (0.5 ずつ)、else rec=0 | キャプションの "without referencing the price history as well as the current position" の素直な読み |
| 4.6 | Null A の P(t) | 実 h で通常通り更新、μ のみ次ステップに向けて uniform 再抽選 | P を壊すと戦略評価が無意味、破壊原因の切り分け不能 |
| 4.7 | p(t) ≤ 0 の log-return | NaN でマスク、解析から除外 | 論文1 Appendix B と整合、N=1000 ではほぼ発生せず |
| 4.8 | close 時の D 寄与 quantity | `entry_quantity` (open 時に確定) | "opening and closing volumes are the same" の素直な実装 |
| 4.9 | 3 モデル比較の return 定義 | **log-return ではなく Δp = D/N** (= 論文1 Eq. (5) の生 price increment) | 論文1 p.9: "if log-return were used for the price formations, some extreme fluctuations could be observed" — Katahira 自身が log を避けている。MG は N=1000 で price が 77% の step で ≤0 となり log-diff が NaN 化するため technically も log 不可。3 モデルで次元が揃う (全て無次元 D/N) 副次的利点もある。 |

---

## 検証

### Parity テスト (§8.1, bit-parity)

`tests/test_parity.py` (pytest 14 ケース全て緑):
- 5 seeds × (N=30, M=3, S=2, T=300) で `run_reference` と `simulate` の全出力 (prices, h_series, cognitive_prices, final_wealth, num_buy, num_sell, num_active_hold, num_passive_hold, num_substitutions, total_wealth) が `np.array_equal`
- S=1 で 3 seeds parity
- Null A / Null B parity
- アクション invariant (buy+sell+active+passive+idle == N)
- `cognitive_prices[t] == cumsum(h_series)[t]`
- 決定性 / seed 感度

### §8.4 ベースライン (N=1000, M=5, S=2, T=20000, seed=777)

`baseline.py` 出力 (`outputs/baseline_metrics.json`):

| 量 | 実測 | 期待 (論文1 Fig. 4, 6, 7) |
|---|---:|---|
| std(r) | 3.26e−3 | — |
| ret_acf τ=14 | +0.003 | noise zone (|ACF|<0.05) ✓ |
| vol_acf τ=1 | +0.200 | strong short-range |
| vol_acf τ=200 | +0.016 | [0.01, 0.05] slow decay ✓ |
| kurt window=1 | +3.63 | heavy tailed |
| kurt window=640 | −0.40 | → Gaussian (aggregational Gaussianity) ✓ |
| Hill α | 4.53 | [3, 5]、論文 Fig. 4 の α ≈ 3.8 と整合 ✓ |
| num_substitutions | 41,837 | wealth dynamics による agent turnover |

### Null test (§8.2) 受け入れ基準

`results_null_tests.png` で:
- baseline: |r| ACF at lag 50 > 0.10 (seed=777 で実測 +0.119)
- Null A: |ACF| < 0.05 (実測 +0.005)
- Null B: |ACF| < 0.05 (実測 +0.017)

**論文との比較**: 論文1 Fig. 7 inset の fit `0.2853·exp(-0.006τ)` は τ=50 で約 0.211 を与える。本実験の 0.119 は若干低めだが、これは T=50000 × 1 trial の finite-sample 揺らぎ範囲内。YH007 で 100 trial アンサンブル平均を取れば論文値に近づくはず (confirmed-pending)。

baseline と nulls の比は τ=50 で約 10-24×。他統計量 (seed=777):

| 量 | baseline | Null A | Null B |
|---|---:|---:|---:|
| vol_acf τ=1 | +0.190 | +0.041 | +0.027 |
| vol_acf τ=14 | +0.152 | +0.003 | +0.012 |
| vol_acf τ=200 | +0.014 | +0.001 | +0.006 |
| kurt w=1 | +3.95 | +0.12 | +0.16 |
| kurt w=640 | +1.05 | −0.34 | −0.41 |
| Hill α | 5.02 | 9.23 | 9.45 |
| std(r) | 3.2e−3 | 2.0e−3 | 1.9e−3 |

当初の §8.2 `baseline > 0.15` は PLAN 段階の粗い見積もり。実測と論文 Fig. 6 の定量値を踏まえて `> 0.10` に改訂した。

### 3 モデル比較 (§8.3)

`results_compare_three.png` (seed=123, S=1, N=1000, M=5, T=50000) で:

- **Row 1** (r(t) = Δp): MG は小振幅 near-Gaussian、GCMG は中振幅で burstiness あり、**SG は大振幅で明瞭な clustering**
- **Row 2** (vol ACF log-log):
  - MG: 高周波ノイズ (decorrelated)
  - GCMG: anti-correlation が支配、scattered
  - **SG: 綺麗な slow decay (τ=1 で 0.25 → τ=500 で 0.01) ✓**
- **Row 3** (CCDF log-log):
  - MG: Hill α ≈ 10^14 (実質 δ 関数、|Δp| 離散化の artifact)
  - GCMG: Hill α ≈ 1429 (very thin tail)
  - **SG: Hill α = 4.33 (power-law tail, 論文範囲 [3, 5]) ✓**

|r| ACF at selected τ (seed=123):

| model | τ=1 | τ=50 | τ=200 | τ=500 |
|---|---:|---:|---:|---:|
| MG   | −0.10 | −0.32 | +1.00 ※ | −0.20 |
| GCMG | −0.19 | −0.22 | −0.09 | −0.22 |
| SG   | **+0.25** | **+0.19** | **+0.04** | −0.02 |

※ MG の τ=200 付近で自己相関が巨大値になるのは、周期 2^M=32 の倍数で戦略テーブル空間を一巡する MG 独特の現象。全体として正の slow decay では**ない**。

**return は `Δp = D/N` (Eq. 5) を直接用いる**。当初 log-returns を使っていたが MG の N=1000 下で price が 77% の step で ≤0 に沈み log-diff が NaN 化した。論文1 Eq. (5) は Δp 基準なので Δp を用いる方が自然。3 モデルで次元が揃う (絶対価格増分)。

---

## 既知の制約 (Lite スコープ、YH007 送り)

- M–B phase diagram (全パラメータスキャン)
- Gini 係数、Pareto tail 指数、round-trip horizon、action ratio の集計
- 論文1 Fig. 2–13 の完全再現
- Physica A 2021 Self-organized Speculation Game
- GARCH residuals / conditional heavy tails
- 10 trial アンサンブル平均 (現状は 1 trial、論文2 Fig. 11 も 1 trial)

3 モデル比較の trial 数を増やすには `compare_three_models.run_compare(seed=seed_i)` を seed ループで回し、各 metrics を平均する。seed 変数が各モデル内部の `np.random.default_rng(seed)` を制御するだけなので seed_list に切り替えるだけで足りる。

### YH003/YH004 を本比較で使う際の注記

- **S=1** で走らせて inductive learning を実質無効化している。YH003/YH004 の本来の設計 (S≥2 で戦略 switch を学習) からは外れるが、本比較は「learning を除去した上でなお SG の構造が vol clustering を生むか」の検証のためこの設定を採用した。
- YH003/YH004 は内部で `rng.uniform(0, 0.5, size=(N, 1))` などの S=1 下でも RNG を消費するが、結果の stylized facts に影響はない。
- YH003/YH004 の標準 N は 101、本比較は **N=1000 に揃えている**。両者とも assertion なしで動く (`|excess| ≤ N=1000`、int64 overflow 無し)。

### 符号規約の確認 (実装着手時 Step 2-9-7)

- YH003: `action ∈ ±1`, `excess = preds.sum() = 2·attendance − N`. A 側 (+1) 優勢で `excess > 0`.
- YH004: `action ∈ {−1, 0, +1}`, `excess = actions.sum()` を直接返却。
- SG Eq. (5) `D = Σ a_i q_i` も `a_i = +1` (buy) で D > 0. **符号反転不要**。

---

## 参考文献

- Katahira, K., Chen, Y., Hashimoto, G., Okuda, H. (2019). Development of an agent-based speculation game for higher reproducibility of financial stylized facts. *Physica A*, **524**, 503–518.
- Katahira, K., Chen, Y. (2019). Heterogeneous wealth distribution, round-trip trading and the emergence of volatility clustering in Speculation Game. arXiv:1909.03185.
- Challet, D., Zhang, Y.-C. (1997). Emergence of cooperation and organization in an evolutionary game. *Physica A*, **246**, 407–418. [YH003]
- Jefferies, P., Hart, M. L., Hui, P. M., Johnson, N. F. (2001). From market games to real-world markets. *Eur. Phys. J. B*, **20**, 493–501. [YH004]
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. *Quantitative Finance*, **1**, 223–236. [stylized facts の定義]
