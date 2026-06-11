# 事前凍結 — Tier-3 robustness の解釈規則（headline 認定の頑健性）

**凍結日**: 2026-06-11（結果生成前。Tier-3 run は未実行）。変種 battery 自体は
research.md D-B9 で事前確定済み（`designmap.robustness_variants`）。本書はその
headline への適用と解釈規則の凍結。

## 1. 対象

headline セル = **batch5-revisable @ (ν=30, lr=0.15)**（density spoke 規則 3 の機械選択）。
変種（D-B9 固定）: center ×20 seed ／ SARSA ×20 ／ tie=rotate ×5 ／ lr ×0.5, ×2 ×5 ／
eps_beta ×0.5, ×2 ×5 ／ γ ∈ {0.90, 0.99} ×5。判定は `verdict.certify` の機械適用。

## 2. 解釈規則（両帰結を固定）

1. **headline の維持条件**: center ×20 seed で認定が維持されること。維持されれば
   主張 (ii) の肯定枝は n=20 水準で確定。**維持されない場合、headline は
   「n=5 では認定、n=20 で非認定」へ正直に降格**し、主張 (ii) は「認定可能 regime は
   高々この近傍に限られ、5-seed 水準の認定すら n 拡大で消える」という、より強い
   否定寄りの枝で報告する（隠さない・基準を変えない）。
   **数値明確化（2026-06-11 追記、結果未読**——初回 run は schema 欠陥（変種が
   CSV 上で区別不能）の発見により部分結果を読まずに破棄・再投入した。その間に
   「維持」の定義を明示する）: 維持 = `verdict.certify` を **20 seed のプール**に
   機械適用して certified=True、すなわち **(markup mean − 2SE > floor 0.05) ∧
   (IR pass 率 ≥ 0.8) ∧ (収束 20/20 全 seed)**。k-of-n の seed 個別認定ではない。
   これは density spoke の n=5 判定と同一の関数・同一の閾値であり、n だけが変わる。
2. **アルゴリズム頑健性**: SARSA ×20 の認定有無はそのまま報告。Q-learning 固有か
   学習一般かのラベルになる（どちらでも情報、確定主張は「観測されたラベル」のみ）。
3. **HP 変種**（tie/lr/β/γ、各 5 seed）: 認定 frac の感度として一覧報告。n=5 なので
   個別セルの確定主張はしない（headline 維持判定には使わない）。
4. Δ 帰属（規則 4）の検出力強化: center ×20 の per-seed markup を保存し、
   n=20 で ±2SE 分類を再計算する。分類が「無影響」から動いた場合のみ従の主張を更新。
5. 報告様式: mean ± SE + n。markup 絶対水準は解釈しない（D-B11）。

## 3. 凍結時点で存在するデータの開示

- density spoke（headline 認定は n=5）、coarse、US4 BCS、Δ 帰属 n=5（全分類 無影響）。
- headline セルの ×20 seed・SARSA・HP 変種の結果は**存在しない**。
- seed は 0..19（既存 5 seed 0..4 は決定論により同一軌道の再計算になる——
  新規サンプリングは seed 5..19 のみ）。
