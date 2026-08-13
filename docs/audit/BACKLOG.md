# 監査 backlog(当週 scope 外の是正・確認項目)

P0 監査(2026-08-13)とそのレビューから出た項目のうち、当週の scope に
入れないもの。カレンダー・Contract v0.1 のワーキング文書は本リポジトリに
未収載のため、該当項目はここに記録して転記待ちとする。

## P4 解除の前提(YH007-8)

1. **P3-F を修正較正値(φ=0.615/σ=3.81e-3)で再走し、agg parity 参照値を
   確定する(P4 解除の前提)。** 現行 `yh007_8_p3f_recenter.py` docstring の
   参照値 0.102 は旧較正 run 由来と確定済み(対照 run の zi_matched agg=0.102、
   `docs/audit/P0_yh007_recalibration_rerun.md` §3)。修正値では 0.072。
   Kronos 実機(KRONOS_PATH)が必要。
2. **P4 解除は、依存鎖(round6 → §3.8 recenter → P3-F)の全リンクが一次
   artifact を持つまで保留。** 2026-08-13 時点で再確定済みは最初の 1 リンク
   (round6 の二重乖離)のみ。P3-F は修正値で未再走。

## P3(q 置換設計)pilot への診断項目追加

- **「q=1、修正キャリブレーション、N_L 固定の条件で、約定率と出来高が
  許容帯に入るか」を pilot 診断に含める。** 根拠: 修正 φ/σ では全 agent が
  matched_ar1 の 1-group 構成で agg_rate が 0.0015(目標帯の 1/100)に崩壊する
  (`P0_yh007_recalibration_rerun.md` §2)。q=1 は戦略群全員が採用者になる条件で
  あり、縮退すればヒートマップ最上段が「高採用率」でなく「市場が動かない領域」に
  なって転写量の測定が出来高ゼロと交絡する。N_L 固定の置換設計では転移しない
  可能性が高いが、グリッド確定前(Week 3 pilot)に確認し、縮退なら q 上端を
  0.9 に切るか N_L を厚くするかを事前判断する。

## Evidence Contract v0.1 / run record schema への要件(8/19–8/20 の仕様作業へ転記)

- **キャリブレーション定数は、コード既定値ではなく外部由来の入力アーティファクト
  として扱う。** source reference と digest を持ち、run record に「どの
  キャリブレーション artifact を使ったか」を記録する。理由:
  - φ=0.615/σ=3.81e-3 自体の provenance は判定根拠 (c)(Kronos 実機による
    外部測定で、現状再実行不能)。この性質は artifact メタデータとして明示
    されるべきで、コード定数では表現できない。
  - 現状は値の変更 = コード 9 箇所の変更で、git blame でしか追えない。
    入力アーティファクト化すれば config hash が動き、P1 の hash chain が
    そのまま変更を検出する。

## incident report 材料(事例メモ)

- 存在しない文書パス `specs/004-yh007-strategy-feedback-loop.md` が、計画文書 →
  監査プロンプト → 監査対象の指定へと無検証で伝播した(P0 §0 で訂正)。
- 一次 artifact(判定根拠 a)は**対象 findings 11 件中 0 件**だった。出力は
  既定で /tmp、一切未コミット。対の数字: 2026-08-13 の再走・対照 run により
  `P0_rerun_yh007_8_p3d.json` が YH007-8 系で最初の一次 artifact になった
  (0 件 → 2 件)。
