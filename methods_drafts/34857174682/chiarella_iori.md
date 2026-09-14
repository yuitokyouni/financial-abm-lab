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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのエージェントタイプを用いた連続二重オークションメカニズムを導入しており、価格発見の過程における多様な戦略を考慮している点が新しい。しかし、これ自体は既存のABM文献における多エージェントモデルの一部であり、特に新規性が高いわけではない。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて、価格が公正価値に引き寄せられる過程を捉えている。', '価格発見が限界注文を通じて行われるため、実際の市場メカニズムに近い挙動を模倣できる。', '取引コストの介入パラメータを導入することで、現実の取引環境におけるコストの影響を考慮している。']

## mechanism_weaknesses
['エージェントの戦略が単純化されており、実際の市場における戦略の多様性を十分に反映していない可能性がある。', 'ノイズトレーダーの行動が過度に単純化されており、実際の市場での影響力を過小評価しているかもしれない。', '価格発見メカニズムが離散化されたティックグリッドに依存しているため、連続的な価格変動を捉えるのが難しい。']

## research_questions
['異なるエージェントタイプの割合が市場の安定性や価格形成に与える影響はどのようなものか？', '取引コストの変動がエージェントの行動や市場のダイナミクスに与える影響は？', 'ノイズトレーダーの存在が市場の効率性やボラティリティにどのように寄与するのか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
