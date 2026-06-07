# Stage S5.8 diff — LOB equilibration check (T=10000 延長、P3)

S5.8 plan v1.1 の実行結果。Mac 12 trial (C2/C3 × T=10000 × seed 1000–1005、max ~30 分/trial) + Windows KM 延長。

---

## Verdict — **H_frozen 確定** → **S6 進行 GO**

延長区間 [1500, 9999] で退場 event **0 件** / exposure **5.09M agent-steps** (両 cond)。

| 量 | C2 | C3 |
|---|---:|---:|
| 延長区間 event 数 / exposure | 0 / 5,091,031 | 0 / 5,082,856 |
| h 95% 上限 (rule of three) | **5.89e-7/step** | **5.90e-7/step** |
| vs pre-registered frozen 閾値 2e-5 | 34 分の 1 | 34 分の 1 |
| S(9999) [bootstrap 95%] | 0.9119 [0.889, 0.932] | 0.7212 [0.703, 0.744] |
| S(50000) 下限 (95% UB hazard で外挿) | ≥ 0.891 | ≥ 0.704 |

- pre-registered 3 分岐 (H_frozen / H_partial_freeze / H_transient) のうち、dead zone に掠りもせず H_frozen の極へ
- 「6 seed では hazard 解像不足」(plan v1.1 P2 末尾の保険) は zero-event により不要化 — 点推定でなく **rule-of-three 上限** として tight に bound できた

## 1. Katahira スケールでの gap の最終形 (headline 言語)

- **agg**: cohort 絶滅。hazard は生存区間で一定 (2.7–3.0e-3、max/min ≤ 1.11x — 外挿妥当性の裏付け、P5)。uncensored max lifetime 5748 / p99.9 = 2443
- **LOB**: 凍結 population が 95% UB hazard でも 89% / 70% 以上残存
- **報告形**: 「LOB 残存 vs agg 絶滅」。Katahira スケールでは比が定義不能 (agg ≈ 0) — 52x/58x は引き続き「matched 窓末 τ=1499」ラベル付き限定、T=50000 では比を出さない

## 2. 検証 (全 PASS、stop trigger 非発火)

| 検証 | 結果 |
|---|---|
| S3 等価チェック (Mac、override=1500 == archived S3、fail-fast) | PASS (rt_df + lifetimes semantic 一致) |
| determinism guard (T=3000 × 2) | PASS |
| 前半窓 sanity (Windows、12 seed × 2 cond exact) | PASS (全 MATCH) |
| S5.7 整合: S(1500) 6-seed vs 100-trial | 0.9119/0.7212 vs 0.9102/0.7304 — CI 内 |
| runtime | max ~30 分/trial (4h trigger 余裕、T 不変性予測どおり) |

## 3. 実行中に直した点 (集計 script、結果には影響なし)

- agg full-window constancy: cohort 絶滅後 (τ≳6000) の区間は risk set が空で hazard が 0/0 になり、当初の区間設定では constancy 比が無意味な値を返した → 区間を cohort 生存域 [1500,2000]/[2000,3000]/[3000,5000] に修正 (max/min = 1.09–1.11x で一定性確認)
- 「gap vs agg ≈ 9e11x」型の出力: agg S(50000) ≈ 0 (clip 値) への除算で無意味 → 「LOB 残存 vs agg 絶滅」の報告形に変更、比は出さない

## 4. S6 への含意

- **gate 通過**: A3 の暗黙前提「観測された長 lifetime は定常」が実証された。A3 は「実在する凍結の人為的解除」介入として解釈可能 — S6 plan の設計はそのまま生きる
- Layer-2-timescale 留保 → 測定済み result に格上げ (T 6.7x 延長で凍結は 1 event も解けない)
- S6 の成功条件は plan 追記どおり funnel 復元 (bin_var_slope の agg 方向シフト) のみ — lifetime 変化は manipulation check

## 5. Yuito レビュー事項

1. H_frozen 判定の承認 (pre-registered 閾値クリア、上限 34x マージン)
2. headline 言語「LOB 残存 vs agg 絶滅」(Katahira スケールで比を出さない) の承認
3. **S6 (A3) 着手の go** — gate は通過、plan は承認済み定義 (τ_max=121, p25 ベース) のまま
4. S5.9 (P2: c_ticks self-consistency) の時期 — S6 と並走可能な robustness 一括

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 | S5.8 完走。H_frozen 確定 (延長区間 zero-event、h ≤ 5.9e-7 = 閾値の 1/34)。agg は Katahira スケールで cohort 絶滅 (一定 hazard 2.7–3.0e-3、max/min ≤ 1.11x)、LOB は ≥ 89%/70% 残存。S6 gate 通過。 |
