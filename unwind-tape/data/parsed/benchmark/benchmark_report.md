# 無条件 exec_gap 参照分布 (BENCHMARK_SPEC v0.2 — プリント3分類で凍結)

generated: 2026-07-08T16:59:35+09:00

> **位置づけ**: これは統計的 null ではなく参照分布(reference distribution)。母集団は ToSTNeT-1・50億円以上・非委託 + 立会外分売。帰属 leg との主要な系統差は「親イベントの事前公表の有無」(帰属 leg=公表済みオーバーハング下の執行)。**検定には使わない**。tape 本体には混入させない。

- ok rows: 83 / total 83  (skipped: 0)
- 最新プリントの遅延: 2 営業日 (閾値 5)

## 注記(裾の解釈に必須)
- **生終値基準**: prev_close/close/px はすべて生(unadjusted)。調整後を混ぜると分割銘柄で gap が壊れる(MEASUREMENT_SPEC 実装ノートと同じ理由)。
- **バンド打ち切り**: `band_edge_rate` は px が 直近値±7%(**目安**)に到達した割合。実際の制限値幅は絶対円ラダーで 通常もっと広い。裾は規則で打ち切られ得るので、**売出しの裾と直接比較しない**。この率は診断用であって規則の証明ではない。
- **ex-div の検出限界**: `ex_div_flag` は J-Quants の AdjustmentFactor≠1 で判定するため **分割・割当の権利落ちは拾うが、現金配当の配当落ちは日次バーだけでは検出できない**。純現金配当の落ち日は exec_gap_prev に残留バイアスが乗る既知の盲点(要 /fins/dividends 追加)。
- **前日終値クロス**: 時刻情報が無いため、|exec_gap_prev|<10bp を「前日終値ちょうどで約定した可能性」として分類。
- **administered vs negotiated**: 立会外分売は前日終値からの規定ディスカウント (administered price) なので、交渉価格系(超大口)と別 route として集計する。
- **PATCH v0.2 プリント3分類(コスト誤読の排除)**: 超大口を `at_close`(|gap_close|<10bp=終値クロス)/ `at_prev`(|gap_prev|<10bp かつ非at_close=前日終値クロス)/ `off_both`(どちらでもない)に分類。**コスト(譲歩)統計は off_both のみ**で取る。at_close の gap_prev は日次リターン、at_prev の gap_close は約定後の値動きであって**譲歩ではない**ので別掲する。off_both も譲歩と値動きが混ざり得るため、報告は**上限記述**(譲歩成分は直近値±7%で拘束)。
- **配当落ち疑い**: `ex_div_suspect` は期末月(3/6/9/12)の最終3営業日近傍のプリント。実際の ex-date は取れないので発見的な疑いフラグ止まり(prev p99 の汚染確認用)。
- **旧「売り手側の対照」表(v0.1)は分類再定義前の暫定値**。本 v0.2 の off_both×discount に差し替え済み。

## ① コスト包絡 — off_both のみ(譲歩を含み得る唯一の層。**上限記述**)

> 政策保有の売り s3 の対照は **side=discount の p90/p95/p99**(ディスカウント裾の深さ)で見る。median は符号選択で片寄るので使わない。値は譲歩+値動きの**上限**。

| route | 参照 | layer | side | size/ADV20 | N | median | IQR | p90 | p95 | p99 | band率 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| tostnet_large_lots | prev | off_both | all | >=2 | 4 | -0.0017 | 0.0202 | 0.0213 | 0.0246 | 0.0273 | 0.00 |
| tostnet_large_lots | prev | off_both | all | [0,0.25) | 12 | -0.0166 | 0.0119 | -0.0026 | 0.0202 | 0.0425 | 0.00 |
| tostnet_large_lots | prev | off_both | all | [0.25,0.5) | 4 | 0.0275 | 0.0295 | 0.0402 | 0.0403 | 0.0403 | 0.00 |
| tostnet_large_lots | prev | off_both | all | [0.5,1) | 3 | -0.0075 | 0.0260 | 0.0307 | 0.0355 | 0.0393 | 0.00 |
| tostnet_large_lots | prev | off_both | all | [1,2) | 2 | 0.0404 | 0.0500 | 0.0804 | 0.0854 | 0.0894 | 0.50 |
| tostnet_large_lots | prev | off_both | all | ALL | 25 | -0.0075 | 0.0317 | 0.0403 | 0.0465 | 0.0802 | 0.04 |
| tostnet_large_lots | prev | off_both | discount | [0,0.25) | 3 | -0.0113 | 0.0190 | -0.0074 | -0.0070 | -0.0066 | 0.00 |
| tostnet_large_lots | prev | off_both | discount | [0.25,0.5) | 3 | 0.0400 | 0.0217 | 0.0402 | 0.0403 | 0.0403 | 0.00 |
| tostnet_large_lots | prev | off_both | discount | [0.5,1) | 2 | 0.0164 | 0.0239 | 0.0355 | 0.0379 | 0.0398 | 0.00 |
| tostnet_large_lots | prev | off_both | discount | [1,2) | 2 | 0.0404 | 0.0500 | 0.0804 | 0.0854 | 0.0894 | 0.50 |
| tostnet_large_lots | prev | off_both | discount | ALL | 10 | -0.0047 | 0.0493 | 0.0453 | 0.0678 | 0.0859 | 0.10 |
| tostnet_large_lots | prev | off_both | premium | >=2 | 4 | -0.0017 | 0.0202 | 0.0213 | 0.0246 | 0.0273 | 0.00 |
| tostnet_large_lots | prev | off_both | premium | [0,0.25) | 9 | -0.0166 | 0.0126 | 0.0076 | 0.0278 | 0.0440 | 0.00 |
| tostnet_large_lots | prev | off_both | premium | [0.25,0.5) | 1 | 0.0151 | 0.0000 | 0.0151 | 0.0151 | 0.0151 | 0.00 |
| tostnet_large_lots | prev | off_both | premium | [0.5,1) | 1 | -0.0117 | 0.0000 | -0.0117 | -0.0117 | -0.0117 | 0.00 |
| tostnet_large_lots | prev | off_both | premium | ALL | 15 | -0.0090 | 0.0182 | 0.0228 | 0.0340 | 0.0452 | 0.00 |
| tostnet_large_lots | close | off_both | all | >=2 | 4 | -0.0086 | 0.0109 | -0.0039 | -0.0039 | -0.0039 | 0.00 |
| tostnet_large_lots | close | off_both | all | [0,0.25) | 12 | -0.0171 | 0.0313 | 0.0062 | 0.0115 | 0.0163 | 0.00 |
| tostnet_large_lots | close | off_both | all | [0.25,0.5) | 4 | 0.0167 | 0.0272 | 0.0318 | 0.0325 | 0.0331 | 0.00 |
| tostnet_large_lots | close | off_both | all | [0.5,1) | 3 | 0.0048 | 0.0206 | 0.0276 | 0.0304 | 0.0327 | 0.00 |
| tostnet_large_lots | close | off_both | all | [1,2) | 2 | 0.0295 | 0.0113 | 0.0386 | 0.0397 | 0.0406 | 0.50 |
| tostnet_large_lots | close | off_both | all | ALL | 25 | -0.0046 | 0.0262 | 0.0313 | 0.0333 | 0.0390 | 0.04 |
| tostnet_large_lots | close | off_both | discount | [0,0.25) | 3 | 0.0066 | 0.0074 | 0.0153 | 0.0164 | 0.0173 | 0.00 |
| tostnet_large_lots | close | off_both | discount | [0.25,0.5) | 3 | 0.0284 | 0.0141 | 0.0323 | 0.0328 | 0.0332 | 0.00 |
| tostnet_large_lots | close | off_both | discount | [0.5,1) | 2 | 0.0190 | 0.0142 | 0.0304 | 0.0319 | 0.0330 | 0.00 |
| tostnet_large_lots | close | off_both | discount | [1,2) | 2 | 0.0295 | 0.0113 | 0.0386 | 0.0397 | 0.0406 | 0.50 |
| tostnet_large_lots | close | off_both | discount | ALL | 10 | 0.0178 | 0.0266 | 0.0340 | 0.0374 | 0.0401 | 0.10 |
| tostnet_large_lots | close | off_both | premium | >=2 | 4 | -0.0086 | 0.0109 | -0.0039 | -0.0039 | -0.0039 | 0.00 |
| tostnet_large_lots | close | off_both | premium | [0,0.25) | 9 | -0.0340 | 0.0256 | -0.0071 | -0.0058 | -0.0049 | 0.00 |
| tostnet_large_lots | close | off_both | premium | [0.25,0.5) | 1 | -0.0057 | 0.0000 | -0.0057 | -0.0057 | -0.0057 | 0.00 |
| tostnet_large_lots | close | off_both | premium | [0.5,1) | 1 | -0.0079 | 0.0000 | -0.0079 | -0.0079 | -0.0079 | 0.00 |
| tostnet_large_lots | close | off_both | premium | ALL | 15 | -0.0132 | 0.0273 | -0.0042 | -0.0039 | -0.0039 | 0.00 |

## ② at_close 層 = 終値クロス(コストではない。gap_prev を日次リターンとして別掲)

> ここの median/percentile は**執行コストではなく当日リターンの分布**。誤読しないこと。

| route | 参照 | layer | side | size/ADV20 | N | median | IQR | p90 | p95 | p99 | band率 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| tostnet_large_lots | prev | at_close_dayret | - | [0,0.25) | 45 | -0.0138 | 0.0143 | 0.0207 | 0.0396 | 0.1441 | 0.20 |
| tostnet_large_lots | prev | at_close_dayret | - | [0.25,0.5) | 6 | -0.0264 | 0.0121 | -0.0133 | -0.0133 | -0.0133 | 0.00 |
| tostnet_large_lots | prev | at_close_dayret | - | [0.5,1) | 2 | -0.0023 | 0.0009 | -0.0015 | -0.0015 | -0.0014 | 0.00 |
| tostnet_large_lots | prev | at_close_dayret | - | [1,2) | 1 | 0.0287 | 0.0000 | 0.0287 | 0.0287 | 0.0287 | 0.00 |
| tostnet_large_lots | prev | at_close_dayret | - | ALL | 54 | -0.0138 | 0.0133 | 0.0207 | 0.0357 | 0.1401 | 0.17 |

## ③ at_prev 層 = 前日終値クロス(gap_close は約定後の値動きで譲歩ではない)

| route | 参照 | layer | side | size/ADV20 | N | median | IQR | p90 | p95 | p99 | band率 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| tostnet_large_lots | close | at_prev_move | - | [1,2) | 1 | -0.0016 | 0.0000 | -0.0016 | -0.0016 | -0.0016 | 0.00 |
| tostnet_large_lots | close | at_prev_move | - | ALL | 1 | -0.0016 | 0.0000 | -0.0016 | -0.0016 | -0.0016 | 0.00 |

## ④ 立会外分売(administered — 売り確定ディスカウント)

| route | 参照 | layer | side | size/ADV20 | N | median | IQR | p90 | p95 | p99 | band率 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| offauction_distribution | prev | administered | all | >=2 | 3 | 0.0302 | 0.0003 | 0.0304 | 0.0304 | 0.0304 | 0.00 |
| offauction_distribution | prev | administered | all | ALL | 3 | 0.0302 | 0.0003 | 0.0304 | 0.0304 | 0.0304 | 0.00 |

## 診断(1) 旧 side × 新3分類 クロス表(件数)

| 旧side \ 新class | at_close | at_prev | off_both | undet | 計 |
|---|---:|---:|---:|---:|---:|
| discount | 0 | 0 | 10 | 0 | 10 |
| premium | 0 | 1 | 15 | 0 | 16 |
| at_ref | 54 | 0 | 0 | 0 | 54 |

## 診断(2) 非at_close: gap_close vs day_return 相関

- Pearson r = **+0.271** (N=26)。高相関(→+1)ほど gap_close は譲歩ではなく**約定後の値動き**に支配される。

## 診断(3) movement_lower_bound(|gap_prev|>7% の行)

> |gap_prev| が band を超える分は譲歩では説明できない(band で拘束)ので、その超過分 `|gap_prev|−band` は**値動き成分の下限**。

- 該当 10 行。movement_lower_bound 最大 = 0.0937 (code=285A, 2026-06-23)。明細は benchmark_detail.csv。
