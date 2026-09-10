# methodology notes for: chiarella_iori
# kind: abm     refs: Chiarella, Iori & Perelló 2009 (J. Econ. Dyn. Control)
#
# (everything below an unknown header is dropped on save;
#  delete a section's body to clear that column.)
#
# mechanism (read-only, do NOT edit this comment block):
# Continuous double auction with three trader types — fundamentalists pulling
# price toward a fixed fair value, chartists extrapolating recent trends, and
# noise traders. Each trader submits a limit order; price discovery is via order
# matching against a discretised tick grid, with a transaction-cost intervention
# parameter.

## novelty_notes
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続ダブルオークションを基にしており、価格発見のメカニズムにおいては新たな視点を提供する。しかし、基本的な構造は既存のモデルと類似しており、特に新しい理論的枠組みを提示しているわけではない。

## mechanism_strengths
['異なるトレーダータイプの行動を明示的にモデル化している点が、価格ダイナミクスの理解を深める。', '価格発見プロセスにおいて、取引コストの介入を考慮することで、より現実的な市場環境を再現している。', 'ファンダメンタリストとチャーチストの相互作用が、価格の変動に与える影響を捉える能力がある。']

## mechanism_weaknesses
['トレーダーの行動が過度に単純化されており、実際の市場における複雑な戦略や心理的要因を十分に反映していない。', 'ノイズトレーダーの影響を過小評価している可能性があり、実際の市場では彼らが価格形成に与える影響が大きい。', '取引のシミュレーションが限られた条件下で行われており、異なる市場環境における適用性が不明確である。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性やボラティリティに与える影響はどのようなものか？', '取引コストの変化が価格発見プロセスに及ぼす影響をどのように評価できるか？', 'ノイズトレーダーが市場における情報の流れに与える影響をどうモデル化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:price-discovery
