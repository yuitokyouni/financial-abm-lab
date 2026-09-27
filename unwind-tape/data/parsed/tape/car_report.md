# CAR engine report

generated: 2026-07-08T01:21:53

- model_primary: topix_adjusted
- estimation window: [-140, -21] (min days: 100)
- legs processed: 12

## per-leg summary

| leg | day0 | model | β | ADV20 | ADV60 | CAR[-1,+1] | notes |
|---|---|---|---:|---:|---:|---:|---|
| G001/L001 | 2023-11-29 | topix_adjusted |  | 6824550 | 5901210 | -0.0307 |  |
| G002/L001 | 2024-03-29 | topix_adjusted |  | 561445 | 643335 | -0.0832 |  |
| G003/L001 | 2024-06-27 | topix_adjusted |  | 2397930 | 2477840 | -0.0137 |  |
| G004/L001 | 2024-07-04 | topix_adjusted |  | 12456990 | 12077172 | -0.0108 |  |
| G005/L001 | 2025-08-07 | topix_adjusted |  | 104940 | 130080 | 0.1087 |  |
| G006/L001 | 2025-08-29 | topix_adjusted |  | 90775 | 158327 | -0.0413 |  |
| G007/L001 | 2026-01-19 | topix_adjusted |  | 276505 | 166230 | 0.0250 |  |
| G008/L001 | 2026-03-02 | topix_adjusted |  | 12677695 | 8324568 | 0.0111 |  |
| G008/L002 | 2026-03-03 | topix_adjusted |  | 12875140 | 8474972 | 0.0475 |  |
| G009/L001 |  |  |  |  |  |  | could not compute announce_day0 from '' after_close='' |
| G010/L001 |  |  |  |  |  |  | could not compute announce_day0 from '' after_close='' |
| G011/L001 |  |  |  |  |  |  | could not compute announce_day0 from '' after_close='' |

## hand-check targets (G004 Honda, G008 Nintendo)

これらは spec (完了条件 3) の突合対象。手計算と一致していることを PREREG.md に確定した窓/モデルで検証すること。

### G004/L001 (7267)
- announce_day0: 2024-07-04
- model: topix_adjusted, β=, α=, est_n=0
- announcement_CAR_m1_p1: -0.010755
- announcement_CAR_0_p1:  -0.007338
- drift_ann_to_pricing:
- pricing_CAR_m1_p1:
- settlement_CAR_m1_p1:
- recovery 5d/20d/60d:     -0.028313 / -0.009145 / -0.040170
- abnormal_volume_0_p3:    0.3769
- ADV20 / ADV60:           12456990 / 12077172
- market_cap_JPY:          8521362637182 (close=1738.50 shares=4901560332 (approx: period-average shares, not period-end))

### G008/L001 (7974)
- announce_day0: 2026-03-02
- model: topix_adjusted, β=, α=, est_n=0
- announcement_CAR_m1_p1: 0.011071
- announcement_CAR_0_p1:  -0.003108
- drift_ann_to_pricing:
- pricing_CAR_m1_p1:
- settlement_CAR_m1_p1:
- recovery 5d/20d/60d:     0.052436 / 0.093932 / -0.228253
- abnormal_volume_0_p3:    0.2186
- ADV20 / ADV60:           12677695 / 8324568
- market_cap_JPY:          10472469047600 (close=8995.00 shares=1164254480 (approx: period-average shares, not period-end))

### G008/L002 (7974)
- announce_day0: 2026-03-03
- model: topix_adjusted, β=, α=, est_n=0
- announcement_CAR_m1_p1: 0.047487
- announcement_CAR_0_p1:  0.065742
- drift_ann_to_pricing:
- pricing_CAR_m1_p1:
- settlement_CAR_m1_p1:
- recovery 5d/20d/60d:     0.104270 / 0.089775 / -0.169753
- abnormal_volume_0_p3:    0.0922
- ADV20 / ADV60:           12875140 / 8474972
- market_cap_JPY:          10177912664160 (close=8742.00 shares=1164254480 (approx: period-average shares, not period-end))
