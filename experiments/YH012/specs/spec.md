# YH012 Phase 1 — World 市場の確立

## Stage 6 の目的（転記）

同一シード・同一背景市場のもとで、特定注文 1 本を除いた反実仮想実行と比較し、
価格経路への影響を分解する。Phase 1 はその前提となる **構造を持った背景板** を作る。

設計一次情報: lobcore `docs/stage6-impact-experiment.md`。

## Phase 1 出口基準

1. spread > 0 が定常的に存在（**時刻で重み付け**た観測区間の 90% 以上。
   イベント件数比率ではない。テイク直後の一瞬の片側枯れを過大評価しない）
2. 取引量 > 0
3. mid と $f_t$ の相関 > 0（弱いアンカー）
4. 10 シードで平均 spread・ボラのオーダーが同種。mid–$f_t$ 相関は
   **平均 > 0 かつ 10 中 7 以上で正**（短時間ではシードぶれあり。seed=42 の単体テストは相関 > 0 を要求）
5. 同一設定を 2 回実行して log と state_hash が一致

## RNG component 表（要件 4）

| component | 用途 | 使用エージェント |
|---|---|---|
| 0 | 次回起床間隔（`exponential`） | 全員 |
| 1 | 価格オフセット（ティック） | 全員 |
| 2 | 数量 | 全員 |
| 3 | 売買方向 | NoiseTrader |

sentinel component 0: 外生 fundamental $f_t$ のドリフト（`Kernel.sentinel_rng(0)`）。
エージェント ID に属さない。Fundamentalist 人数を変えても $f_t$ は不変。

## Chartist 履歴

核の `View` は最良気配のみ。Chartist は起床のたびに mid を自分のリストに記録する。
起床間隔が長いと履歴が粗くなる — `mean_wakeup` と `chartist_lookback` で制御。

## PoC パラメータと調整理由

初期案: `seed=42`, `end_time=500_000`, `N_f=20`, `N_c=30`, `N_n=50`, `rule=price_time`。

| パラメータ | 採用値 | 理由 |
|---|---|---|
| end_time | 50_000 | 初期案 500k / 試行 200k は Python バッチで重い。50k で出口基準を満たす。延長はローカルで |
| N_f / N_c / N_n | 30 / 25 / 45 | F を増やして両側流動性を厚く。初期 20/30/50 ではテイカーが片側を剥がし spread 比率が落ちた |
| noise_take_prob | 0.15 | 0.35 だと片側枯れ。Fill は確保しつつ quote を残す |
| chartist_take_prob | 0.25 | 常時テイクだとアンカーよりトレンドが勝つ |
| mean_wakeup | 800 | 短すぎるとイベント過多、長すぎると Chartist 履歴が粗い |
| f0 | 10_000 | 中央価格（ティック） |
| band | 30 | Fundamentalist の無取引帯（攻め判定） |
| f_sigma | 0.25 | 時刻ステップあたり。2.0 は速すぎ、0.05 は遅すぎて相関/追従が崩れる |
| noise_take_prob | 0.35 | Noise が最良気配を取る確率（流動性供給だけでは Fill 不足） |
| Fundamentalist | 毎起床 f±band/2 両側クォート | 片側枯れ防止 |
| qty_min / qty_max | 1 / 5 | 小口 |
| noise_offset_max | 15 | スプレッド近傍の休憩指値 |
| chartist_lookback | 3 | 直近リターンに使う履歴点数 |

### 実装メモ: 注文 ID

lobcore の `Context` は起床ごとに `_seq` がリセットされる。同じ agent が毎起床
自動採番だけに頼ると `order_id` が衝突し DuplicateReject になる。
YH012 ではエージェント側で `_order_seq` を保持して明示採番する。
（将来 lobcore 側で永続採番するなら実験側は簡略化できる。）

## Phase 2 以降（未実装）

Experimental Impact agent、`run_pair`、$\Delta(t)$ 可視化は YH012 で続行。
