# YH003: Challet & Zhang (1997) Minority Game

Challet & Zhang (1997) "Emergence of cooperation and organization in an evolutionary game" (*Physica A*, 246, 407–418) の再現実装。N 人のエージェントが二択を繰り返して少数派が勝つゲームで、各エージェントは $S$ 個の戦略テーブル (過去 $M$ 期の勝ち履歴 → 次期の予測) を保持し、仮想スコア (virtual capital) に基づき最良戦略を選ぶ帰納的学習を行う。集合としての分散 $\sigma^2 = \operatorname{Var}(\text{excess})$ が、戦略空間のエージェントあたり密度 $\alpha = 2^M/N$ の関数として相転移的な挙動 (Savit ら 1999 で整理された $\alpha_c \approx 0.34$ の最小点) を示すことを確認する。

## 目的

(i) $\sigma^2 / N$ vs $\alpha$ の相図で低 $\alpha$ 側の herding 領域、$\alpha_c$ 近傍の極小、高 $\alpha$ 側のランダム領域 ($\sigma^2/N \to 1$) が現れること、(ii) アテンダンス $A(t)$ が $N/2$ 周りで揺れ、記憶長 $M$ が臨界値付近で振幅が最大になること、(iii) 平均成功率が $M$ とともに $0.5$ へ単調に近づくこと、(iv) スコア分布の広がりが時間とともに拡大し、top/bottom 戦略の実利得軌跡が分離していくこと、の 4 点を Parameter として標準的な $(N, S) = (101, 2)$ / $(1001, 5)$ で確認する。

## 実行

```bash
cd experiments/YH003
python run_simulation.py                 # seed=42, 全 6 パネル (~45 秒)
python run_simulation.py --seed 7        # 別 seed で揺らぎを見る
python run_simulation.py --skip-checks   # 層3 検証をスキップ
```

`results.png` に 6 パネル図が保存される。

## データ表現 (設計決定)

| 対象 | 表現 |
|------|------|
| 行動 / 予測 | $\pm 1$ (A=+1, B=-1)。符号演算でスコア更新が綺麗 |
| 履歴 | 整数 $\mu \in [0, 2^M-1]$。新しい勝ち bit を右端に push し `& mask` |
| 戦略テーブル | `strategies: (N, S, 2^M)` int8, 値 $\pm 1$ |
| 仮想スコア | `scores: (N, S)` int64 |
| 同点破り | 整数スコアに $[0, 0.5)$ の一様乱数を足して `argmax`。スコア差 $\ge 1$ の組の順位は変わらず、同点の組のみランダムに崩れる |

`model.py` は仕様どおりの `Agent` / `Market` クラス (per-step 参照実装) と、$N$ 軸をベクトル化した `simulate()` の両方を提供する。スキャン系 (Panel 1, 4) は `simulate()` を使うことで 10–100 倍高速化している。

## パラメータ

| 記号 | 意味 | 本実験値 |
|------|------|---------:|
| $N$ | プレイヤー数 (奇数) | 101 (Panel 1), 1001 (Panel 2–6) |
| $M$ | 記憶長 | 1–12 (Panel 1), 6/8/10 (Panel 2), 8 (3/5), 1–10 (4), 10 (6) |
| $S$ | 戦略数 | 2 (Panel 1/2), 5 (Panel 3–6) |
| $T_{\mathrm{burn}}$ | ウォームアップ | 500–1000 |
| $T_{\mathrm{measure}}$ | 測定期間 | 5000–10000 |
| trials | アンサンブル (Panel 1) | 10 |

初期化: 戦略テーブルは各要素 $\pm 1$ 独立一様、スコア $= 0$、履歴 $\mu$ はランダム、実利得 $= 0$。勝ちは少数派 (excess $= \sum$ actions の符号と逆)。偶数 $N$ で excess$=0$ が起きた場合のみ履歴 bit に応じたコインフリップで解決 (本実験では $N$ 奇数なので発生しない)。

## 6 パネルの説明

1. **$\sigma^2/N$ vs $\alpha = 2^M/N$ (log–log)** — $N=101$, $S=2$, $M=1\ldots 12$ を 10 seed 平均。低 $\alpha$ で herding により $\sigma^2/N \gg 1$、$\alpha_c$ 近傍で極小、高 $\alpha$ でランダム参照線 $\sigma^2/N = 1$ に漸近。縦破線が文献値 $\alpha_c \approx 0.34$、横点線が random 参照。
2. **$A(t)$ 時系列 3 本重ね** — $N=1001$, $S=2$, $M \in \{6, 8, 10\}$ の burn-in 後 500 ステップ。$M=6$ (crowded regime) は振幅が大きく、$M=10$ (random regime) は $N/2$ 近傍に収束する。
3. **$A(t)$ 分布** — $N=1001$, $M=8$, $S=5$, $T_{\mathrm{measure}}=10000$。同分散ガウスを重ね書き。中心 $N/2$ 周りの対称分布。
4. **平均成功率 vs $M$** — $N=1001$, $S=5$, $M=1\ldots 10$。全エージェント・全期間の minority 当選率の平均。$M$ 増大とともに $0.5$ へ単調接近。
5. **仮想スコア分布 (中心化)** — $N=1001$, $M=8$, $S=5$。$t \in \{1000, 5000, 10000\}$ で `scores − mean` のヒストグラム。時間とともに裾が広がる様子を可視化。
6. **累積実利得 − $t/2$** — $N=1001$, $M=10$, $S=5$。最終利得上位 3 / 下位 3 / 中央付近ランダム 3 を、chance line $0.5 \cdot t$ からの偏差で描画。top は持続的に正、bottom は持続的に負。

## 観測された数値 (seed = 42)

| 統計量 | 観測値 | 期待 / 参考 |
|--------|-------:|-------------|
| $\sigma^2/N$ 最小 (N=101, S=2) | **0.268** at $\alpha = 0.634$ (M=6) | 最小値 $\sim 10^{-1}$ 台、文献値 $\alpha_c \approx 0.34$ |
| $\sigma^2/N$ at M=5 ($\alpha=0.317$) | 0.373 | $\alpha_c$ 直下で急降下 |
| $\sigma^2/N$ at M=12 ($\alpha=40.5$) | 0.968 | ランダム極限 1.0 に漸近 |
| Mean $A(t)$ (N=1001, M=8, S=5) | 499.75 | $N/2 = 500.5$ |
| Skew$(A - N/2)$ | −0.021 | 対称 ($|\cdot| < 0.1$) |
| Success rate (N=1001, S=5) | 0.272 (M=1) → 0.485 (M=10) | $M\uparrow$ で $0.5$ へ単調接近 |

- **$\alpha_c$ の位置**: $N=101$ という粗い離散サンプリングでは $M=5$ ($\alpha = 0.317$) と $M=6$ ($\alpha = 0.634$) の間に最小点が落ち、後者が 0.268 で最小。Savit ら (1999) の大規模スケーリングでは $\alpha_c \approx 0.337$ に収束することが知られており、$N$ を増やせばさらに左にシフトする見込み。本実験ではベタな離散ステップでも典型的 U 字 (log–log) が完全に再現できている。
- **Crowded regime**: $M \le 4$ で $\sigma^2/N \gg 1$ となるのは、戦略空間 $2^M$ がエージェント数 $N$ に対して狭く、同じ戦略を複数エージェントが共有する確率が高いため。Panel 2 の $M=6$ 時系列 (赤) で振幅が他の 2 本より大きいことにも現れている。
- **Random regime**: $M \ge 9$ で $\sigma^2/N \to 1$ は各エージェントが実質独立にコインフリップする状況に相当。Panel 4 の success rate も $M=10$ で 0.485 とほぼ $0.5$、Panel 6 で top/bottom の偏差が $\pm 300$ 程度 ($0.5 \cdot T = 5000$ に対し 6% の揺らぎ) に留まるのも整合。
- **Virtual score の広がり (Panel 5)**: 全戦略の平均スコアは毎ステップ $+0.5$ 進むので中心は $t/2$。中心化した広がり (std) は $\sqrt{t/4} \cdot c$ 的にスケールし、$t=1000 \to 10000$ でおよそ $\sqrt{10}$ 倍に広がることが目視できる。これがあるからこそ best-strategy 選択が情報を持つ。
- **層3 検証** (`--skip-checks` で無効化): seed 再現性、戦略空間の初期対称性 (平均 = $-0.0002$)、$A(t)$ 対称性 (歪度 = $-0.021$)、$\sigma^2/N$ の U 字形、の 4 項目が全て通過。

## YH004 / YH005 への拡張フック

本実装は次の 2 ステップ拡張を意識して設計している。

| 拡張 | 設計上の不変点 |
|------|----------------|
| YH004 (GCMG, 非参加オプション) | `Agent.decide()` の戻り値を `(action, s_idx)` としており、`action ∈ {-1, 0, +1}` に拡張可。戦略テーブルを `{-1, 0, +1}` の 3 値化するか、閾値判定を被せれば良い |
| YH005 (Speculation Game, リターン利得) | `Market.tick()` の戻り値を「勝ち側 ($\pm 1$)」から数値化された signal へ一般化することを想定。スコア更新を `scores += strategies[:, mu] * signal` に差し替えるだけで切替可能 |

共通基盤 (`strategies`, `scores`, $M$, $S$, `decide`, `update_virtual`) は 003–005 通しで不変なので、003 の `Agent` を薄くラップすれば 004/005 の実装量は最小に抑えられる。

## 実装しないこと

- 戦略の進化・淘汰 (遺伝的アルゴリズム、Challet & Zhang (1997) §4 以降)。本実装は §2–3 の static strategy table 版まで。
- $S$ > 5 の大規模戦略空間探索。
- 熱的ノイズ付き確率選択 (softmax over scores)。ハードな argmax + tiebreak のみ。
- 応答関数 (response function) や $\chi^2$ オーダーパラメータの計算 (Challet, Marsili 系論文の解析的扱い)。

## 参考文献

Challet, D., & Zhang, Y.-C. (1997). Emergence of cooperation and organization in an evolutionary game. *Physica A*, 246, 407–418.

Savit, R., Manuca, R., & Riolo, R. (1999). Adaptive competition, market efficiency, and phase transitions. *Physical Review Letters*, 82(10), 2203–2206.
