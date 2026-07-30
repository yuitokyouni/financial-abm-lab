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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという3つの異なるトレーダータイプを用いた継続的二重オークションの枠組みを提供する。特に、トレーダーの行動に基づく価格発見メカニズムは新しいが、他のABMと比較して特に革新的な要素は少ない。

## mechanism_strengths
['異なるトレーダータイプの行動を組み合わせることで、価格形成の多様な側面を捉えることができる。', '取引コストの介入パラメータを導入することで、現実の市場に近いダイナミクスを模倣する。', 'ファンダメンタリストの固定された公正価値への引き寄せが、価格の安定性を生むメカニズムを示す。']

## mechanism_weaknesses
['トレーダーの行動における非線形性や相互作用の複雑さが不十分に表現されている。', 'ノイズトレーダーの影響が過小評価されている可能性があり、実際の市場のボラティリティを十分に再現できていない。', '取引の実行や約定のメカニズムが単純化されすぎており、現実の市場の複雑さを捉えきれていない。']

## research_questions
['トレーダータイプ間の相互作用が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変化が異なるトレーダータイプの行動に与える影響は？', 'ノイズトレーダーの行動が市場の安定性にどのように寄与するのか？']

## tags
novelty:low, mechanism:reusable, borrowable:market-dynamics
