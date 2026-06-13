# Calibration ④ — BCS ES–SPY 外部妥当性アンカー（research D-B10 / US4）

**Status**: 較正値確定（2026-06-11、原典確認済み）／本番スケールの実行は研究実行フェーズ
**Registry**: `src/microstructure/calibrations.py` の `bcs-es-spy`
**原典**: Budish, Cramton & Shim (2015), "The High-Frequency Trading Arms Race: Frequent
Batch Auctions as a Market Design Response", *QJE* 130(4), 1547–1621.

## 1. 原典から取得した数値（2026-06-11 に PDF 本文で確認）

| 量 | 値 | 出典箇所 |
|---|---|---|
| arb 機会数/日 | mean **801**（p25 285 / median 439 / p75 876 / p99 5353） | Table I |
| per-arb 利益（/unit） | median **≈0.08** index pt（"remarkably constant"）、mean 0.09 | §V.B, Figure V, Table I |
| per-arb 数量 | mean 13.83 ES lots（median 4.20） | Table I |
| 総 prize | $306k/日 ≈ **$75M/年**（全市場換算） | §V.B |
| race 時間 | median 97ms (2005) → **7ms (2011)** | §I, Figure IV |
| ES 最小 spread | **0.25** index pt（tick）→ half-spread 0.125 | §V.B |
| 機会の起点 | 89% が ES 側 jump | §V.B |
| 計上閾値 | 利益 ≥ 0.05 pt のみ機会と数える | §V.B |
| fee の扱い | 利益推定は exchange fees/rebates を**除外** | §V.B 脚注 13 |
| FBA 提案間隔 | "to fix ideas, say, **100 milliseconds**"（最適 interval は特定せず §VII.D） | §I |

## 2. sim パラメータへの換算チェーン

時間単位 = 1 秒、価格単位 = ES index point、**dt = 0.01 s（10ms）**。
dt の選択根拠: committed-quote の staleness は 1 期 ＝ モデルの「MM が反応できない窓」。
2011 年の median race 7ms ≈ 10ms なので、1 期 staleness が実測の race 時間スケールに対応する。

1. **λ（jump 強度）** = 801 機会/日 ÷ 23,400 s（6.5h 概数）= **0.03423 /s**。
   モデルでは |jump|>h の jump ＝ picking-off 機会なので、観測「機会」率を λ に同定
   （閾値 0.05pt で切られた小 jump を数えない保守側の同定）。
2. **J（jump size）** = h + per-arb 利益 = 0.125 + 0.08 = **0.205 pt**。
   モデル恒等式: per-race 利益 = J − h。median（0.08）を採用、mean（0.09→J=0.215）は感度軸。
3. **h_ref（観測 half-spread）** = tick 0.25 / 2 = **0.125 pt**（grid スケールと closure の入力）。
4. **α = 1.0**: BCS の race は常に勝者が解決する（gross 抽出極限）。001/002 の
   monopolist sniper 仮定とちょうど整合。
5. **fee = 0**: 原典の利益が fee 抜きのため（脚注 13）。CME 公表 fee は robustness 軸。
6. **ν（noise_rate）— eq(3) closure**: BCS の均衡式
   `l_invest·s/2 = l_jump·Pr(J>s/2)·E[J−s/2 | J>s/2]`（彼らの式(3)）は本 harness の
   `gm_break_even` と**同一の結び目**（A1+C4 knot）。観測 h=0.125 を競争均衡 spread と
   みなして式を閉じると ν = α·λ·(J−h)/h = 0.03423·0.08/0.125 = **0.02191 /s**。
7. **batch_grid** = N ∈ {10, 100} = {100ms, 1s}（提案値と、その 10 倍の対比点）。

**検算（test で pin）**: `gm_break_even(λ=0.03423, J=0.205, α=1, ν=0.02191) = 0.125` が
機械精度で再現される（`tests/test_designmap.py::test_bcs_calibration_eq3_closure`）。
較正世界の competitive 解が観測 spread を厳密に通る＝換算チェーンの内部整合。

## 3. 同定の限界（正直に）

- **深さの正規化**: 本モデルは unit-quantity。per-arb 数量（mean 14 lots）の次元は落ちる。
  ドル建て総額（$75M/年）ではなく **per-unit のレート**（801/日 × 0.08pt）で較正している。
  ドル総額ルートで ν を出すと深さ分だけ別の値になる（採らなかった代替、registry source 参照）。
- **ν は eq(3) 経由の間接同定**: 観測 h が「競争均衡」であるという仮定に乗る。実 ES の
  maker 構造が competitive でなければ ν は過小/過大になる。直接の flow データで置き換える
  余地あり（robustness）。
- **イベント希薄性**: q = λ·dt ≈ 3.4×10⁻⁴。学習にとって sniping 信号が非常に疎
  （t_max=2×10⁶ 期で jump ~680 回）。較正セルの本番実行は t_max の引き上げ（ledger 内で）
  または信号集約の工夫が必要——これは較正された現実がそれだけ「静かな」市場であることの
  正直な帰結であって、合成パラメータ世界との重要な差。
- **市場時間窓**: 23,400s（9:30–16:00 概数）。BCS の正確な窓と数 % ずれてもλ は比例で
  ずれるだけ（結論の方向には効かない）。

## 4. pipeline スモーク（縮小スケール・探索的）

`python scripts/run_design_map.py --cell bcs-es-spy --t-max 60000 --seeds 2`（2026-06-11）:
6 条件 {cont, batch10, batch100} × {committed, revisable} が ledger 記帳（793,200 期）付きで
完走し CSV 出力。**この markup 値は非収束（conv=0.0、t_max 縮小）の探索的出力であり
結果として引用しない**。本番は研究実行フェーズで t_max ≥ 2×10⁶・seeds ≥ 5・
robustness tier の ledger 管理下で行う。

## 5. 代替アンカー

TWSE 定期 call auction（〜2020-03、約 5 秒間隔 → N=500）: batch interval の実在値として
registry に骨組みのみ（数値未記入 → `CalibrationIncomplete` で実行拒否）。優先度は
BCS 本番実行の後。
