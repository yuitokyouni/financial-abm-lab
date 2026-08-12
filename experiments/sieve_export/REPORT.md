# sieve inspect 所見 — self_organized_book (ZI-only, 10 seeds)

- 日付: 2026-08-11
- モデル: `abm_models.self_organized_book.SelfOrganizedBookMarket` 相当の ZI-only 構成
  (spec 003 P0: 全 LIMIT・内生流動性 CDA、マーケットメイカー無し)
- パラメータ: warmup 200 + main 5000 step, n_zi=50, bar_size=10, order_ttl=20,
  sigma_eval=0.005, margin 0.001–0.01, zi_mode=naive(モデルの既定値)
- データ: `dataset/`(manifest.yaml + runs/seed-000..009.csv, 列 = step,price,volume)。
  price = market price(最終約定価格)、volume = step ごとの実約定数量
  (PAMS `get_executed_volumes`; kronos_lob の定数 proxy ではない)。
  burn-in = warmup 200 step を manifest で宣言(CSV は全行保持、drop は sieve 側)。
- ツール: sieve-validation 0.4.0(`pip install git+https://github.com/yuitokyouni/sieve`)、
  suite = financial-stylized-facts@0.1
- 実行: `sieve inspect experiments/sieve_export/dataset --out experiments/sieve_export/sieve_runs`
- バンドル: `sieve_runs/9a8e5aaee3f9/`(report/index.html, figures/*.svg,
  observations.parquet, inspect_bundle.json)。9 figure OBSERVED /
  conditional_tails・timescale_asymmetry・gain_loss_asymmetry は NOT_TESTED(suite 対象外)。

sieve inspect は探索モードで pass/fail を出さない(OBSERVED = 計算・描画できた、の意)。
以下の判定は observations.parquet の記述統計と補助計算(step レベル return acf(1)、
volume×|r| 相関、bar=10 集約)に基づく所見。

## 所見サマリ

| 次元 | 判定 | 根拠(10 seed 平均 [range]) |
|---|---|---|
| Volatility clustering | **弱くあり(短期のみ)** | acf_abs(1) = +0.203 [0.176, 0.223] で全 seed 正。ただし acf_abs(20) = −0.004 ≈ 0 で長期記憶なし。bar=10 集約でも acf_abs(1) = +0.098 / acf_abs(20) = −0.037 |
| Heavy tails | **なし(ほぼ Gaussian)** | Hill α ≈ 5.57(left)/ 5.57(right)[4.8, 6.2]、excess kurtosis = +0.23 [0.02, 0.85]。実市場の α≈3–5 より薄く、cubic law 域に届かない |
| Leverage effect | **なし** | leverage kernel = −0.0008 [−0.0032, +0.0018]、符号も seed 間で不定。ZI の売買対称性から予想どおり |
| Volume–volatility 相関 | **弱くあり** | volume×\|r\| Pearson = +0.136 [0.124, 0.148]、Spearman = +0.114。全 seed で正・符号安定だが弱い |

## 付随所見(要注意)

- **step 解像度の market price 系列には強い bid-ask bounce が残る**:
  return acf(1) = **−0.473**(10 seed とも ≈ −0.47)、variance_ratio(20) = 0.089。
  spec 002 で同定された Roll (1984) bounce そのもので、全 LIMIT 化(spec 003)でも
  「最終約定価格を step 単位で読む」限り消えない(bounce の除去は bar close /
  mid 集約側の性質)。bar=10 の close でも ret_acf(1) = **−0.311** と負が残った。
  spec 003 round6 の ret_acf(1) ≈ −0.02 は較正済み recenter 構成・main 区間整列の
  bar close 測定であり、本 export(P0 既定パラメータ・素の市場価格)とは条件が違う。
  この dataset で tails/clustering を読む際は、負の短期自己相関が |r| 系列に
  乗っている点に注意。
- drift = −0.0001 ≈ 0(全 seed で ±0.003 内)。トレンド汚染なし。
- sieve の注意書きどおり、これは reference 比較なしの探索的所見であり
  「実市場に合う/合わない」の確認には `sieve test` が必要。

## 確認的評価: sieve test vs 実市場 reference(2026-08-11 追記)

`financial-daily@1.0.0` suite は実市場 reference を**同梱**している(S&P 500 / FTSE 100 /
DAX / 日経225 / Hang Seng / EURO STOXX 50 の日次 log return、unit-sd スケール、
2001-07〜2026-06 の 124 window の凍結統計。生系列は非再配布、SHA-256 のみ同梱)。
そのため外部データ取得は不要だった。

- 入力: `test_inputs/seed-XXX/`(warmup 除去済み log return、`step,return` 列)。
  sieve test は単一長系列のみ受けるため seed ごとに独立評価(連結はしない)。
- 実行: `sieve test experiments/sieve_export/test_inputs/seed-000 --suite financial-daily@1.0
  --claim descriptive-market-dynamics --out experiments/sieve_export/sieve_runs`
- 主 bundle(seed-000): `sieve_runs/d2d50f882ba6/`。seeds 1–9 は同条件で実行し
  verdict のみ下表に集計(bundle は再現可能なので未コミット)。
- 注意: SOB は step 解像度で reference は日次。比較は unit-sd スケール後の
  構造比較であり、カレンダー対応ではない。

### Reference 分布(124 window の 5%–95% 分位)vs SOB(10 seed 平均)

| metric | ref 5% | ref median | ref 95% | SOB | 位置 |
|---|---|---|---|---|---|
| acf_abs(1) | +0.034 | +0.193 | +0.317 | **+0.203** | **ほぼ median 直上** |
| acf_abs(20) | +0.011 | +0.114 | +0.253 | −0.004 | 下方に域外 |
| excess kurtosis | +1.318 | +3.979 | +17.64 | +0.234 | 下方に域外 |
| Hill left | +2.346 | +3.436 | +4.844 | +5.567 | 上方に域外(裾薄) |
| Hill right | +2.285 | +3.342 | +5.428 | +5.568 | 95% 分位の外縁 |
| leverage | −0.129 | −0.099 | −0.052 | −0.001 | 域外(市場は全 window 負) |
| variance_ratio(20) | +0.548 | +0.813 | +1.347 | **+0.089** | **完全分離(KS=1.0)** |
| drift | −0.020 | +0.017 | +0.058 | −0.000 | 域内 |

### Per-seed verdict(10 seeds、α=0.01 較正、Holm 補正)

| metric | 000 | 001 | 002 | 003 | 004 | 005 | 006 | 007 | 008 | 009 | 安定性 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| acf_abs_1 | P | P | P | P | P | P | P | P | P | P | **PASS 10/10** |
| drift | P | F | F | P | P | P | P | P | P | P | PASS 8/10 |
| excess_kurtosis | F | F | F | F | F | F | F | P | F | F | FAIL 9/10 |
| hill_left | F | F | F | F | F | F | F | P | F | F | FAIL 9/10 |
| hill_right | F | F | F | F | P | F | F | F | F | F | FAIL 9/10 |
| acf_abs_20 | F | F | F | F | F | F | F | P | F | F | FAIL 9/10 |
| leverage | F | F | F | F | F | F | F | F | F | F | **FAIL 10/10** |
| variance_ratio_20 | F | F | F | F | F | F | F | F | F | F | **FAIL 10/10** |

### 構造的読み

- **短期 volatility clustering(acf_abs(1))は 10/10 で reference と分離不能**。
  SOB の +0.203 は市場 median +0.193 のほぼ真上。ZI-only + 内生流動性だけで
  この次元は市場帯に入る。ただし sieve の caveat どおり、この metric は
  block_bootstrap / garch 系とも分離しないため単独では弱い証拠。
- **clustering の持続性(acf_abs(20))が別次元として FAIL** — 「clustering が
  一部だけ自己組織化する(短期のみ、長期記憶なし)」という inspect の読みが
  確認的にも支持された。
- **return dependence(variance_ratio(20) = 0.089)は KS = 1.0 の完全分離**。
  市場 reference の下限 0.548 の 6 分の 1 で、全次元中いちばん異様。
  −0.47 の reversal は「やや強い」ではなく実市場の変動集積構造と完全に別物。
- leverage は市場側が 124 window 全て負(−0.13〜−0.05)に対し SOB はゼロ近傍で
  10/10 FAIL。方向性非対称の欠如は決定的。
- 裾は「薄すぎて」FAIL(kurtosis が ref 5% 分位 1.32 に対し 0.23、Hill が
  ref 95% 4.84 に対し 5.57)。
- まとめ: **「ZI-only は vol clustering の水準では市場側に寄るが、return
  dependence・持続性・非対称性・裾で市場から構造的に外れる」**が、reference
  付きの確認的評価として成立した。

## 日経225 reference overlay(2026-08-12 追記、sieve 0.5.0)

sieve 0.5.0 で `--reference` overlay が入ったので、日経225 の実系列を重ねた
探索レポートを追加した。

- 取得: `python tools/fetch_index_data.py ^N225 nikkei`(新規スクリプト。
  Yahoo Finance v8 chart API、`fingerprint_atlas.real_refs` 再利用)。
  2462 営業日(2016-08-15〜2026-08-12)→ `data/index_cache/nikkei_daily.csv`。
  生データはコミットしない(financial-daily suite と同じ流儀)。同一性検証用
  SHA-256: `49161191a3795913821b0821fa1cecb1981ed9efa3ef56026da315301a90a7f5`
- 実行: `sieve inspect experiments/sieve_export/dataset
  --reference data/index_cache/nikkei_daily.csv --reference-derive-return log
  --reference-label "Nikkei 225" --out experiments/sieve_export/sieve_runs`
- バンドル: `sieve_runs/5c3efb1b156e/`(全 figure に Nikkei 225 の導出曲線が
  visual context として overlay される)

### 同一パイプラインでの対比(SOB は 10 seed 平均 ± sd)

| metric | Nikkei 225 (10y) | SOB | 過不足 |
|---|---|---|---|
| excess kurtosis | +8.96 | +0.23 ± 0.26 | **不足**(裾が桁違いに薄い) |
| Hill left / right | 2.99 / 3.05 | 5.58 / 5.58 | **不足**(cubic law 域に届かない) |
| acf\|r\|(1) | +0.289 | +0.203 ± 0.016 | ほぼ同水準(やや不足) |
| acf\|r\|(20) | +0.079 | −0.004 ± 0.010 | **不足**(持続性ゼロ) |
| leverage | −0.135 | −0.002 ± 0.003 | **不足**(非対称性なし) |
| VR(20) | 0.92 | 0.089 ± 0.007 | **過剰**(mean reversion が実市場の約10倍強い) |

注: Nikkei 10 年窓 1 本 vs SOB step 解像度 10 run の構造比較(unit-sd 基準)。
確認的な separation 判定は上の financial-daily sieve test 節が正で、
この節はその日本市場・単一系列版の描像。両者は整合している。

## 再現手順

```bash
uv sync
uv run python experiments/sieve_export/run_sieve_export.py
sieve inspect experiments/sieve_export/dataset --out experiments/sieve_export/sieve_runs
# 確認的評価 (seed ごと)
sieve test experiments/sieve_export/test_inputs/seed-000 \
  --suite financial-daily@1.0 --claim descriptive-market-dynamics \
  --out experiments/sieve_export/sieve_runs
```
