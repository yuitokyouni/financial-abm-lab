# 事前凍結 — US4 BCS 較正セルの解釈規則（P2 現実接地）

**凍結日**: 2026-06-11（結果生成前。BCS 較正セルの本番 run は未実行）。
予測自体の先行凍結: `docs/research-design.md` §9.1（commit `122ddee`、2026-06-11）に
「実在 venue（BCS ES–SPY 較正点）はこの空間の疎側に位置する」と記載済み。
OSF: density spoke の registration（https://osf.io/63pj2/）の追補として扱う
（別 registration を切るかは Yuito 判断、本ファイルの git 凍結が結果に先行する）。

## 1. 判定するもの

P2 目標文（research-design §9.1）の最終節:
> 実在 venue（BCS ES–SPY 較正点）はこの空間の疎側に位置する。

## 2. 手続き（固定）

1. **位置づけ（算術）**: BCS 較正の事象密度 pn_BCS = ν_BCS·dt を、認定 headline セルの
   pn = 0.3（ν=30, dt=0.01）と比較する。較正値は commit 済みの
   `calibrations.py::bcs-es-spy`（ν ≈ 0.02191/s、eq(3) closure、出典付き）を機械使用。
2. **較正セル本番 run**: `--cell bcs-es-spy`（cont + batch_grid × committed/revisable、
   5 seed、t_max=2×10⁶、robustness tier に charge）。収束/認定は `verdict.certify` の
   機械適用（density spoke と同一）。
3. 報告様式: mean ± SE + n、認定/非認定ラベル。単一 seed の数値は本文に出さない。

## 3. 解釈規則（両帰結を固定）

- **非認定（予測どおり）**: 主張 (ii) 最終節が成立——「現実の ES–SPY パラメータは
  認定可能 regime の外（疎側）にあり、較正セルでも認定は出ない」。
- **認定が出た場合（予測の反証）**: 予測は falsified と正直に報告する。この帰結は
  研究を弱めない——「現実密度で認定可能な collusion が存在する」はむしろ規制上
  重大な発見であり、P2 は強い肯定枝として再フレームする（隠さない・縮めない）。
- いずれの場合も、markup の絶対水準は解釈しない（D-B11 ceiling 注意）。

## 4. 凍結時点で存在するデータの開示

- density spoke 18 セル（認定 1: batch5-revisable @ ν=30, lr=0.15）と coarse 72 セル
  （全て非認定）。**BCS 較正セルの本番 run 結果は存在しない**（存在するのは
  縮小スケールの calib smoke のみ: `results/calib_smoke.csv`、t_max 縮小の動作確認）。
- BCS 較正値そのもの（ν, λ, J, h, fee）は 2026-06-11 以前に出典付きで commit 済み
  （`calibration.md` / `calibrations.py`）。位置づけの算術は run に依存しない。
