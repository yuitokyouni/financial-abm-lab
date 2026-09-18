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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプを用いた連続ダブルオークションのメカニズムを持つが、同様の構造のモデルは他にも存在するため、独自性は限定的である。特に、ファンダメンタリストが価格を固定の公正価値に引き寄せる点は、他のモデルでも見られる。

## mechanism_strengths
['異なるトレーダータイプの相互作用を捉える能力が高い。', '価格発見過程における注文マッチングのメカニズムが明確である。', '取引コスト介入パラメータが導入されており、現実の市場状況を反映している。', 'arXiv:1110.5222v3で示されたように、トレーダーの戦略に基づく社会的効率の変化を捉える能力がある。']

## mechanism_weaknesses
['トレーダーの行動が過度に単純化されており、実際の市場の複雑さを十分に反映していない可能性がある。', 'ノイズトレーダーの影響が過小評価されることがあり、実際の市場ではより多様な行動が見られる。', '価格の変動がファンダメンタリストの介入に依存しすぎているため、他の要因の影響を無視している。', 'ダイナミクスの長期的な変化に関するメカニズムが不十分であり、長期記憶やボラティリティクラスタリングの観点からの分析が不足している。']

## research_questions
['異なるトレーダータイプの比率が市場のダイナミクスに与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場の価格形成に与える具体的な影響は？', 'ファンダメンタリストの価格介入が市場の安定性にどのように寄与するのか？', '異なる取引コストの設定がトレーダーの行動と市場結果に与える影響は？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
