# イベント条件付き stylized facts — 売出し前後の二次モーメント・裾

generated: 2026-07-18T14:43:54+09:00

- ok legs: 28  窓(営業日, day0相対): pre[-25,-6] run-in[-5,-1] event[0,+5] drift[+6,+25]

## 1. 実現ボラのスパイクと減衰
- **spike = rv_event/rv_pre**: median 1.04 (mean 1.05, n=28) → 発表窓でボラが約 1.0倍
- **decay = rv_drift/rv_pre**: median 1.08 → drift 窓で ほぼ平時へ減衰

## 2. 出来高の署名
- **vol_abn = event 平均出来高 / ADV20(pre)**: median 2.19倍

## 3. 左裾(暴落頻度)
- event+drift の日次リターン(pre ボラで標準化)で **< -2σ の頻度 = 4.5%**、対照(pre 窓)= 2.8%、正規理論 ~2.3%。
- < -3σ: event+drift 1.8% vs pre 0.6%。（左に厚い＝協調・予告供給の先回りが作る暴落側の裾）

> **注意**: 全て日次・調整終値。窓内に決算等の別イベントが入る leg は交絡。spike/decay は rv_pre 正規化なので銘柄横断で可比。
