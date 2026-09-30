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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを考慮した連続ダブルオークションを用いており、トレードダイナミクスの理解に新たな視点を提供します。しかし、連続ダブルオークション自体は既存の文献でも広く扱われており、特に新しいメカニズムを導入しているわけではありません。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格発見プロセスを描写している。', 'ファンダメンタリストによる価格の公正価値への引き寄せが、リアルな市場状況を模倣する。', '取引コストの介入パラメータが含まれており、実際の取引環境に即したシミュレーションが可能。']

## mechanism_weaknesses
モデルは、トレーダーの行動に対する外的ショックや情報の流入を十分に考慮していないため、急激な市場変動に対する反応が不十分である。また、ノイズトレーダーの影響が過小評価されている可能性があり、実際の市場で観察されるボラティリティクラスタリングやヘビーテールの生成に対するメカニズムが欠如している。

## research_questions
['異なるトレーダータイプの比率を変化させた場合、価格ダイナミクスはどのように変化するか？', '取引コストを変化させることで、トレーダーの行動や市場の安定性にどのような影響があるか？', 'ノイズトレーダーの割合が市場のヘビーテール特性に与える影響はどのようなものか？']

## tags
novelty:medium, mechanism:reusable, research:market-dynamics
