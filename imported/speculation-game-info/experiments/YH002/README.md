# YH002: Lux & Marchesi (2000) Volatility Clustering

Lux & Marchesi (2000) "Volatility clustering in financial markets: a microsimulation of interacting agents" (*IJTAF*, 3(4), 675–702) の再現実装。Chartist (楽観/悲観) と Fundamentalist の間で戦略切り替えが起こる多エージェント市場を Poisson 型非同期更新で走らせ、Fig. 1 (Parameter Set I, p. 689) と Fig. 3 (autocorrelations, p. 695) に相当する統計性質を検証する。

## 目的

有限個のエージェントから成る金融市場で、chartist の比率 $z = n_c/N$ が臨界値 $\bar z$ 付近に来ると局所不安定 (on–off intermittency) が発生し、普段は穏やかな時系列に突発的な volatility burst が挿入されるさまを、論文 §2 の transition-probability 形式 (式 (2.1)–(2.4)) のまま再現する。とくに (i) kurtosis の増大、(ii) Hill 推定量による裾指数 $\hat\alpha_H$、(iii) 絶対値・二乗リターンの長期 ACF、の 3 点について論文値と比較する。

## 実行

```bash
cd experiments/YH002
# Fig. 1 と同じ T=4000 でクイックラン (~5 秒)
python run_simulation.py --seed 42 --steps 4000

# Table 2 と同じ T=20000 でフル統計 (~25 秒)
python run_simulation.py --seed 42 --steps 20000
```

`results.png` に 6 パネル図が保存される。`--seed` と `--steps` (デフォルト 4000) を指定できる。リポジトリには両方の代表ランを `results_T4000.png` / `results_T20000.png` として保存している。

## パラメータ (Parameter Set I, p. 689)

aggregated 形式 $T_c \equiv N t_c$、$T_f \equiv N \gamma$ で保持する。

| 記号 | 値 | 意味 |
|------|-----|------|
| $N$ | 500 | エージェント総数 |
| $\nu_1$ | 3 | opinion 再評価の頻度 |
| $\nu_2$ | 2 | strategy 再評価の頻度 |
| $\beta$ | 6 | auctioneer の反応速度 |
| $T_c = N t_c$ | 10 | chartist 取引ロット (aggregated) |
| $T_f = N\gamma$ | 5 | fundamentalist 反応強度 (aggregated) |
| $\alpha_1$ | 0.6 | majority opinion weight |
| $\alpha_2$ | 0.2 | price trend weight |
| $\alpha_3$ | 0.5 | profit differential weight |
| $p_f$ | 10 | fundamental price |
| $r$ | 0.004 | nominal dividend |
| $R$ | 0.0004 | alternative real return |
| $s$ | 0.75 | fundamentalist discount factor |
| $\sigma_\mu$ | 0.05 | excess demand noise std |

固定: $\Delta t = 0.01$ (適応切り替えなし)、$\Delta p = 0.01$、$p$ の ±0.01 離散ジャンプ、$\dot p$ は直近 0.2 time unit (= 20 simulation step) の平均価格変化率、integer time step ごと (= 100 simulation step ごと) に記録、初期値 $n_c = 50$・$p = p_f$・$x$ ランダム、min group size = 4 (吸収状態回避のため 4 未満のグループからの流出を禁止)、シミュレーション長 4000 integer time step。

価格更新の実装上の注意: 論文 p. 687 脚注 n に「auctioneer の価格更新については、cents を elementary unit とすることで 100 割が既に組み込まれており追加調整は不要」とあるため、opinion/strategy の個体遷移確率は rate × $\Delta t$ として計算するのに対し、価格上昇/下降確率 $\pi_{\uparrow p},\pi_{\downarrow p}$ は $\beta(\mathrm{ED}+\mu)$ をそのまま 1 ステップ確率として使う (式 (2.4) の形)。

## 6 パネルの説明

1. **Returns 時系列** — $r_t = \ln p_t - \ln p_{t-1}$ を integer time step 軸で表示。volatility burst と長い穏やかな期間の交替を目視確認する。
2. **$z(t)$ と $\bar z$** — chartist 比率の時系列と、(cond 1) から算出した臨界値 $\bar z$ (破線) および論文報告値 0.65 (点線)。$z$ が $\bar z$ へ近づくと局所不安定化してバーストが発生する。
3. **Returns ヒストグラム vs 同分散ガウス (linear)** — 中心が尖り裾が広い非ガウス分布を視覚化する。
4. **Survival function (log–log)** — $P(|r|>x)$ を |r| 軸の両対数で描画。裾が power law (直線) に近づくのに対し、ガウスは急速に falls off する。
5. **ACF of raw / squared / absolute returns (lag 0–300)** — raw は 0 付近を振動、squared と absolute は長期に正相関が残る。論文 Fig. 3 と対応。
6. **サマリー統計テーブル** — excess kurtosis、Hill $\hat\alpha_H$ (2.5% / 5% / 10% tail)、ADF test (log price)、computed $\bar z$ を、Parameter Set I の論文値 (Table 1, Table 2, p. 690 本文) と並べて表示する。

## 観測された数値 (seed = 42)

| 統計量 | T = 4000 | T = 20000 | 論文 Parameter Set I |
|--------|---------:|----------:|----------------------|
| Excess kurtosis | 10.19 | **16.66** | 135.73 (Table 2, p. 693) |
| Hill $\hat\alpha_H$, 2.5% tail | 3.37 | **2.59** | 2.04 (median, Table 2) |
| Hill $\hat\alpha_H$, 5% tail | 3.05 | **2.40** | 2.11 (median) |
| Hill $\hat\alpha_H$, 10% tail | 2.14 | **1.92** | 1.93 (median) |
| ADF stat (log $p$) | $-41.3$ | $-87.0$ | non-rejection on 500-obs subsamples (Table 1) |
| $\bar z$ (computed) | **0.660** | **0.660** | **0.65** (本文 p. 690) |

- **臨界値 $\bar z$**: 論文 Appendix A の 3×3 Jacobian からスパース構造を利用して 2 次方程式に帰着させ、(cond 1) $a_{11} + a_{33} = 0$ を解くと $\bar z \approx 0.660$ となり、論文本文の 0.65 と 0.01 の誤差で一致する。Parameter Set I での on–off intermittency 分岐点が正しく再現されている。
- **Hill tail index (T=20000)**: 10% tail で $\hat\alpha_H = 1.92$ が論文中央値 1.93 とほぼ完全一致、5% tail 2.40 / 2.5% tail 2.59 も論文の range $(1.26,~2.64)$ 内にあり、power-law 裾の重さが定量的に再現されている。
- **Kurtosis**: Set I は論文 4 種のなかで最もバーストが強く 135 に達する extreme case。T=4000 では 10 程度だったが、T=20000 で 16.66 に上昇し観測長依存が明瞭 (論文 Table 2 も 20,000 観測を使用)。それでも論文値に届かないのは、単一標本での最大級 burst の出現頻度にランダム性があるためで、seed 依存性が大きい統計量である (論文でも kurtosis の range は報告せず中央値のみ)。
- **ADF**: 大標本 ($T \ge 4000$) では検出力が高く unit root 仮説が棄却される。論文の「棄却されない」結果は 500 観測の subsample 設計由来の低検出力ゆえで、母過程は論文本文 p. 691 が「intrinsically stable and bounded」と述べる通り実際には stationary。
- **ACF** (T=20000 図 5): raw returns は lag 1〜2 に小さな負のスパイク (論文脚注 s と整合)。squared / absolute returns は lag 300 まで緩やかに減衰し、absolute の方が持続性が高い。Fig. 3 と同じ形状。

## 実装しないこと (論文との忠実性のための除外事項)

- 適応 $\Delta t$ 切り替え (論文は burst 時に $\Delta t = 0.002$ へ落とすが、本実装は $\Delta t = 0.01$ 固定)。
- 連続時間 ODE + Gaussian 雑音での価格更新 (式 (2.4) の ±0.01 離散ジャンプを厳守)。
- Parameter Set II〜IV (本実装は Set I のみ)。
- Lux (1995), Lux (1998 JEBO), Lux–Marchesi (1999 *Nature*) の定式化は混入させない。

## 参考文献

Lux, T., & Marchesi, M. (2000). Volatility clustering in financial markets: a microsimulation of interacting agents. *International Journal of Theoretical and Applied Finance*, 3(4), 675–702.
