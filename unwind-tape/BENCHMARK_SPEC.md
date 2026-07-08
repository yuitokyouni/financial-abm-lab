<!--
  unwind-tape / BENCHMARK_SPEC — 無条件 exec_gap 参照分布の測定系仕様
  本文(下記 v0.1)はユーザ確定の一次仕様。実装(scripts/benchmark_engine.py)は
  この spec と突合して整合を検証する。以後の変更は本ファイルに追記する。
  MEASUREMENT_SPEC(系統A/B, tape本体)とは独立。参照分布は tape に混入させない。
-->

# BENCHMARK_SPEC v0.1 — 無条件 exec_gap 参照分布(tape非混入)

## 位置づけ
- 名称は「参照分布(reference distribution)」。統計的nullではない。
  母集団は ToSTNeT-1・50億円以上・非委託 という切片。帰属legとの主要な系統差は
  親イベントの事前公表の有無(帰属leg=公表済みオーバーハング下の執行)。検定には使わない。

## 定義(超大口プリント)
- px = 約定単価(金額/数量から導出し、掲載値があれば突合)
- exec_gap_prev  = ln(prev_close) − ln(px)
- exec_gap_close = ln(close) − ln(px)
- 恒等式: exec_gap_close = exec_gap_prev + day_return。参照を一本に固定せず両方保存
- 時刻情報が無いため |exec_gap_prev| < 10bp を「前日終値クロス」として分類する列を持つ
- ex-div flag: 権利落ち日のプリントは gap_prev に配当落ちが混入するためフラグ
- 値幅チェック: 直近値±7%目安のバンドで裾が打ち切られる。バンド境界への集積率を
  レポートし、裾の解釈に「規則による打ち切り」を注記(売出しの裾と直接比較しない)

## 定義(立会外分売)
- exec_gap = ln(prev_close) − ln(分売価格) = 開示ディスカウント。
  administered price(運用上の価格設定)である旨をタグ付けし、交渉価格系と区別する

## 出力
- route × 参照(prev/close) × size/ADV20バケット別: N, median, IQR, p90/p95/p99, バンド集積率
- 明細CSV: px, prev_close, close, 両gap, day_return, size, size/ADV20, ex-div, 分類
- 実行時ヘルスチェック: max(publication_date) が5営業日超遅延なら警告(launchd監視を兼ねる)

## データ
- J-Quants はプリント出現銘柄のみ日次バーを取得・キャッシュ(レート制御)。raw は data/raw/(git外)

---

## 実装ノート(Claude, 2026-07-08 — scripts/benchmark_engine.py)

**逸脱・明示化した点(いずれも正確性/正直さ上の必然):**

1. **価格基準は生終値(C)。** prev_close/close/px はすべて生(unadjusted)。調整後を混ぜると
   イベント後に分割があった銘柄で gap に累積調整係数の定数バイアスが乗る(MEASUREMENT_SPEC 実装
   ノートと同一の理由)。参照区間は1〜2営業日と短く分割を跨がないので生で恒等が閉じる。

2. **ex-div flag は J-Quants `AdjustmentFactor`≠1 で判定 → 検出限界あり。** これは分割・割当の
   **権利落ち**は拾うが、**現金配当の配当落ちは日次バーだけでは検出できない**(J-Quants の日次バーは
   現金配当で価格調整しないため)。spec が本来警戒している「配当落ちの gap_prev 混入」は、純現金配当
   の落ち日については**残留する既知の盲点**。創作で埋めず、`ex_div_flag` は「検出できた権利落ち」の
   意味に留め、report にこの限界を明記した。厳密に潰すなら /fins/dividends 追加が必要(spec の
   「日次バーのみ」方針を変える判断が要る)。

3. **±7% バンドは「目安」の近似。** 実際の制限値幅は絶対円ラダー(基準値段帯ごとの円建て、通常
   もっと広い ~15–30%)。`band_edge_rate`(px が 直近値±band_pct に到達した割合)は裾が規則で
   打ち切られている**診断**であって規則の証明ではない。band_pct は configs/benchmark.yaml で可変。
   データを見て校正する前提。売出しの裾との直接比較は禁止(spec どおり)。

4. **出力と git/license の扱い。** 生バーは `data/raw/prices/benchmark_bars/`(gitignore、再配布不可)。
   明細 `benchmark_detail.csv` は価格を含むため gitignore、集計 `benchmark_summary.csv`(N/median/
   percentile)と `benchmark_report.md` のみ git-track。tostnet/分売の parsed CSV 列名は
   fetch_jpx_offauction の schema-lock に一致(候補リストで軽微な表記揺れは吸収)。

5. **無帰属の徹底。** 出力は tape(groups/legs)と一切結合しない。誰が売ったかは公開日次データでは
   線で結べないため、参照分布としてのみ使う(BENCHMARK_SPEC 位置づけ)。
