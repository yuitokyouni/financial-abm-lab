# YH004: Jefferies et al. (2001) Grand-Canonical Minority Game

Jefferies, P., Hart, M. L., Hui, P. M., & Johnson, N. F. (2001) "From market games to real-world markets" (*Eur. Phys. J. B*, 20, 493–501; arXiv:cond-mat/0008387) §2.2 の Grand-Canonical MG (GCMG) を再現する。YH003 の MG に 2 点の拡張を加える: (i) signed スコア ($+1$ 正解 / $-1$ 誤答) を直近 $T$ 期の rolling window で集計する "sunken losses" 方式、(ii) 閾値 $r_{\min}$ による参加選択 ($\max(r_S) > r_{\min}$ のときのみ取引、それ以外は abstain)。論文 Figure 1 (⟨$N_{\mathrm{active}}$⟩ と $\sigma[N_{\mathrm{active}}]$ の $r_{\min}$ 依存) の再現を中心とし、参加者数の内生的変動が MG には無かった fat-tailed リターン分布を生むことを確認する。

## 目的

(i) Figure 1 の転移曲線 (⟨$N_{\mathrm{active}}$⟩ が $r_{\min}$ を上げるにつれて $N$ から 0 へ単調降下、$\sigma[N_{\mathrm{active}}]$ は中間 $r_{\min}$ でピークを持つ) を再現し、論文 p.5 の独立二項 Random Walk 近似 $\langle N_{\mathrm{active}}\rangle \approx N(1 - P[r_S < r_{\min}]^s)$ が crowded 相でどの程度ズレるかを比較する。(ii) 閾値 $r_{\min}$ の導入だけで vanilla MG の (near-Gaussian) アテンダンス分布が fat tail 化することを、kurtosis で定量する。(iii) YH003 との極限同値 ($T_{\mathrm{win}} \ge T_{\mathrm{total}}$, $r_{\min} < -T$ で MG と一致) をサニティチェックとして通す。(iv) 動的モード $r_{\min,i} = \max(0, -(r_i - \lambda \sigma(r_i)))$ (論文 p.5) で「静穏期 → 突発的 rush」の時系列パターンを再現する。

## 実行

```bash
cd experiments/YH004
python run_simulation.py                 # seed=42, 全 6 パネル (~60 秒)
python run_simulation.py --seed 7        # 別 seed
python run_simulation.py --skip-checks   # 層3 検証をスキップ
```

`results.png` に 6 パネル図が保存される。

## データ表現 (設計決定)

YH003 からの主要差分:

| 項目 | YH003 | YH004 (GCMG) |
|------|-------|--------------|
| スコア規約 | +1 正解 / 0 誤答 (unsigned) | +1 正解 / −1 誤答 (signed) |
| 集計期間 | 全期間累積 | 直近 $T$ 期 rolling (ring buffer) |
| スコア範囲 | $[0, t]$ | $[-T, T]$ |
| 行動 | $\pm 1$ (必ず参加) | $\pm 1$ または $0$ (abstain) |
| 参加判定 | なし | $\max(r_{S,i}) > r_{\min}$ |

これによって Figure 1 の x 軸 $r_{\min} \in [-T, T]$ は、signed スコアの生値で直接指定できる (論文 p.4 の "lower end of the range $-T \le r_{\min} \le T$")。`r_min_static=0.0` は「最良戦略の勝率が 50% を上回るときだけ参加」の意味になり、自然な出発点。

実装は (i) `BaseMGAgent` を書いてから (ii) `GCMGAgent(BaseMGAgent)` で abstain 拡張、という段階構成。(iii) ベクトル化 `simulate()` では (T_win, N, S) int8 の ring buffer を `score_buf` に、(T_win, N) を `personal_buf` に置く。動的モードの $\sigma(r_i)$ は `personal_buf.std(axis=0)` で毎 step 計算 (T=50 なら N*T=5k ops で誤差なし)。

## パラメータ (主に Figure 1 再現 p.5)

| 記号 | 意味 | 本実験値 |
|------|------|----------:|
| $N$ | プレイヤー数 (奇数) | 101 (Fig.1/Panel 1-3, 5-6), 1001 (Panel 4) |
| $M$ | 記憶長 | 2 (Fig.1), 3 (Panel 4), 1-10 (Panel 5) |
| $S$ | 戦略数 | 2 |
| $T_{\mathrm{win}}$ | sunken-losses 窓幅 | 50 (論文指定) |
| $r_{\min}$ | 参加閾値 (静的) | $-T .. +T$ sweep (Panel 1/2), $\{-25, 0, 15\}$ (Panel 3), $\{-T-1, 0.3T\}$ (Panel 4), $\{-T-1, 0\}$ (Panel 5) |
| $\lambda$ | 動的モードのリスク回避係数 | $\{0.5, 1.5, 3.0\}$ (Panel 6) |
| trials | Panel 1/2 のアンサンブル | 5 |

初期化: 戦略テーブル $\pm 1$ 一様、スコア 0、ring buffer 全てゼロ、履歴 $\mu$ ランダム。全員非参加になった step は履歴をランダム bit で進める (論文に明記は無いが必然的な扱い)。

## 6 パネルの説明

1. **⟨$N_{\mathrm{active}}$⟩ vs $r_{\min}$** (Figure 1 top 相当) — 5 trial 平均 ± σ を navy で、論文 p.5 の二項近似 $N(1-P^s)$ を赤破線で重ねる。x 軸は signed score $[-T, T]$。
2. **$\sigma[N_{\mathrm{active}}]$ vs $r_{\min}$** (Figure 1 bottom 相当) — 中間 $r_{\min}$ での揺らぎピークと、二項理論の $\sqrt{N(1-P^s)P^s}$ との比較。
3. **$N_{\mathrm{active}}(t)$ 時系列 3 本** — $r_{\min} \in \{-25, 0, 15\}$ の重ね書き。$-25$ は MG 相当で定数 101、$0$ は大きく揺らぐ中間相、$+15$ は長い静穏期と突発 rush の交替。
4. **Excess $A - N/2$ の分布 (log-y)** — $N=1001, M=3, S=2$ で MG ($r_{\min} = -T-1$) と GCMG ($r_{\min} = 0.3T$) を比較。excess kurtosis を凡例に記載。
5. **$\sigma^2/N$ vs $\alpha = 2^M/N$** (log-log) — MG と GCMG($r_{\min}=0$) を重ね書き。crowded 相では GCMG の方が揺らぎが大きく (相関した participate/abstain スイッチ)、dilute 相では GCMG の方が小さい (弱い戦略を持つ agent が abstain して参加数が減る)。
6. **動的 $r_{\min}$ 時系列** — $\lambda \in \{0.5, 1.5, 3.0\}$ で $N_{\mathrm{active}}(t)$ を 2000 step 描画。"ranging" と "break-out rush" のパターン (論文 p.5 末尾で言及) を確認。

## 観測された数値 (seed = 42)

| 統計量 | 観測値 | 理論/期待 |
|--------|-------:|-----------|
| ⟨$N_{\mathrm{active}}$⟩ at $r_{\min}=0$ (N=101, M=2, S=2, T=50) | **51.2** | 二項近似 81.1 |
| ⟨$N_{\mathrm{active}}$⟩ at $r_{\min}=-T-1$ | 101.0 | $N$ (MG 極限) |
| ⟨$N_{\mathrm{active}}$⟩ at $r_{\min}=+T$ | 0.0 | 0 (完全抑制) |
| $\sigma[N_{\mathrm{active}}]$ ピーク位置 | $r_{\min} \approx +5$ | 二項近似ピークは $r_{\min} \approx 0$ |
| $\sigma[N_{\mathrm{active}}]$ ピーク値 | 14.3 | 二項近似 5.0 |
| Excess kurtosis, MG ($r_{\min}=-T-1$) (N=1001, M=3) | **−0.91** | sub-Gaussian (範囲制約) |
| Excess kurtosis, GCMG ($r_{\min}=0.3T$) | **+41.3** | fat-tailed (論文の主張) |
| Excess std, MG / GCMG | 238 / 11 | GCMG は非参加で静穏期 std 小 |
| σ²/N at α=0.317 (M=5), MG / GCMG($r_{\min}=0$) | 1.46 / 4.10 | GCMG は crowded で揺らぎ大 |
| σ²/N at α=10.14 (M=10), MG / GCMG | 1.02 / 0.57 | GCMG は dilute で揺らぎ小 |
| YH003 MG 同値サニティ ($T_{\mathrm{win}} = T_{\mathrm{total}}$) | σ²/N = 0.257 | YH003 reported 0.268 (一致) |

- **二項近似との乖離**: Figure 1 再現で sim の転移点 ($\langle N_{\mathrm{active}}\rangle$ が急降下する $r_{\min}$) は約 $-5$、理論は約 $+5$ 付近。論文 p.5 は "approximation becomes better for $T \gg 2^m$" と明記しており、本実験 $T/2^m = 50/4 = 12.5$ は crowded 相なので乖離は想定内。crowded 相では $r_S$ が強く mean-reverting するため、独立 random walk 近似より小さなスコアに集中し、$r_{\min}=0$ でも既に abstain 側に倒れる agent が多い。
- **Fat tails**: Panel 4 の excess kurtosis が MG で $-0.91$ (sub-Gaussian), GCMG で $+41.3$ (強い fat tail) と劇的に変化。MG の「少数派が勝つ」制約が aggregate を押し戻すのに対し、GCMG では静穏期にスコアが微小変動 → ある閾値で複数 agent が同時参加 → 突発的巨大 excess、というバースト生成メカニズムが効く。これが論文 §2.2 の「realistic market model として成立する」主張の定量的裏付け。
- **σ²/N の相図反転**: Panel 5 で crowded 相は GCMG が volatile、dilute 相は GCMG が静穏。閾値 $r_{\min}=0$ は dilute 相 (個々の strategy score が正方向に drift) では「弱い戦略を持つ agent の filter」になり参加減、crowded 相 (score が 0 近傍で mean-reverting) では「全員か誰もいないか」の相関スイッチングを誘発し揺らぎ増大。
- **動的 $r_{\min}$**: $\lambda$ 依存は弱く、$\langle N_{\mathrm{active}}\rangle \approx 8$ が 0.5–3.0 でほぼ一定。これは $r_{\min} = \max(0, \lambda\sigma - r_i)$ の fixed point が $r_i < 0$ かつ $\sigma$ 小の狭い帯に落ち込み、$\lambda$ による変化が相殺されるため。時系列 (Panel 6) の方には "rush" パターンが出ており、Figure 2 の趣旨は再現されている。

## YH003 との極限同値

層 3 検証で確認:

- `T_win >= T_total` かつ `r_min_static < -T_win` の設定で simulate を回すと、全期間 `active == N` かつ `σ²/N = 0.257` (N=101, M=6, S=2) が得られ、YH003 の 0.268 とほぼ一致する。不一致分は RNG 消費順序が異なること (perturb 生成や abstain 判定のステップ挿入) による seed 依存、構造的差ではない。

## 実装しないこと

本 YH004 は GCMG のコア (§2.2) のみ。以下は対象外:

- §2.3 の wealth / 取引量 heterogeneity、value vs trend 投資家の混合
- §3.2 の market maker 機構 (Bouchaud-Cont-Farmer 価格更新 + inventory フィードバック)
- Figure 3 (wealth distribution), Figure 5 (kurtosis / vol-clustering 時系列分析), Figure 4 (market-maker inventory)
- §4 の real data ($/Yen FX-rate) 上での予測

これらは後続の実験 (YH005: Speculation Game) または追加実験で扱う。

## YH003 / YH005 との共通基盤

`BaseMGAgent` (M, S, strategies, scores, decide, update_virtual) を YH003-005 通じての不変インタフェースとして切り出している。YH005 (Speculation Game) へは `update_virtual(mu, signal)` の `signal` を ±1 から数値リターンへ、および market 側の winning 判定を「少数派」から「シグナル一致」へ差し替えるだけで移行できる想定。

## 参考文献

Jefferies, P., Hart, M. L., Hui, P. M., & Johnson, N. F. (2001). From market games to real-world markets. *European Physical Journal B*, 20, 493–501. [arXiv:cond-mat/0008387](https://arxiv.org/abs/cond-mat/0008387)

Challet, D., & Zhang, Y.-C. (1997). Emergence of cooperation and organization in an evolutionary game. *Physica A*, 246, 407–418. [YH003 で再現]
