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

## 再現手順

```bash
uv sync
uv run python experiments/sieve_export/run_sieve_export.py
sieve inspect experiments/sieve_export/dataset --out experiments/sieve_export/sieve_runs
```
