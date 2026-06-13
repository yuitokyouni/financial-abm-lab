# YH001: Cont-Bouchaud (1997) Percolation Model

Cont & Bouchaud (1997) "Herd behavior and aggregate fluctuations in financial markets" の再現実装。

## 目的

ランダムグラフによるherding（群衆行動）がfat tailを内生的に生むことを確認する。

## 実行

```bash
cd experiments/YH001
python run_simulation.py
```

`results.png` に6パネルの図が出力される。

## パラメータ

| パラメータ | デフォルト | 意味 |
|-----------|----------|------|
| N | 10000 | エージェント数 |
| c | 0.9 | 協調パラメータ (0 < c < 1) |
| a | 0.01 | 取引活性度 |
| λ | 1.0 | market depth |
| T | 50000 | ステップ数 |

## 出力 (6パネル)

1. リターン時系列 — volatility clustering の視覚確認
2. リターン分布 vs ガウス分布 (linear)
3. 対数スケール裾比較 (log-linear)
4. クラスターサイズ分布 (log-log) — 理論: P(W) ~ W^{-5/2}
5. テール指数 α vs c — Clauset-Shalizi-Newman (2009) 準拠の最尤推定 (powerlaw パッケージ)
6. Excess kurtosis vs c — c→1 で kurtosis 急増

## 結果

### 基準ケース (c=0.9, N=10000, T=50000)

- Excess kurtosis = 9.81 (ガウス分布なら 0)
- テール指数 α ≈ 2.96 (Clauset MLE, discrete=True)

### c を動かしたときのテール指数 α

| c | α (Clauset MLE) | excess kurtosis |
|---|-----------------|-----------------|
| 0.5 | 2.90 | 0.02 |
| 0.7 | 2.95 | 0.42 |
| 0.8 | 2.98 | 1.02 |
| 0.9 | 2.96 | 8.83 |
| 0.95 | 2.99 | 21.50 |
| 0.99 | 2.65 | 47.50 |
| 1.0 | 2.57 | 51.99 |

c が臨界点 (c=1) に近づくと α が急落し、裾が重くなる。
特に c=0.95→0.99 の間で α が 2.99→2.65 へ急落しており、
パーコレーション転移の効果が明確に見える。

### 理論値との対応

Cont-Bouchaud モデルのクラスターサイズ分布は臨界点で P(W) ~ W^{-(1+μ)} (μ=3/2)。
リターンの密度分布は P(Δx) ~ |Δx|^{-(1+μ)} に従うため、
累積分布のテール指数は α = μ = 1.5 が理論的予測となる。
ここで得た α ≈ 2.6 (c=0.99-1.0) は理論値より大きいが、
これは有限サイズ効果 (N=10000) と臨界点からのずれ (c<1) による
指数カットオフの影響と考えられる。

## 参考文献

Cont, R. & Bouchaud, J.-P. (2000). Herd behavior and aggregate fluctuations in financial markets.
*Macroeconomic Dynamics*, 4(2), 170-196. (Working paper: 1997)
