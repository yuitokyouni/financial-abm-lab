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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続二重オークションのアプローチを採用しているが、同様の枠組みは既存の文献にも見られる。したがって、特に新しいメカニズムを提示しているわけではない。

## mechanism_strengths
['ファンダメンタリストとチャーチストの相互作用を通じて価格形成のメカニズムを捉えている。', '取引コスト介入パラメータを考慮することで、現実の市場状況を模倣する能力がある。', '連続二重オークションの形式を用いることで、流動性の高い市場を再現できる。']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価される可能性があり、実際の市場における彼らの役割を十分に反映していない。', '価格発見プロセスが離散化されたティックグリッドに依存しているため、連続的な価格変動を捉えるのが難しい。', 'エージェントの行動が単純化されすぎているため、異なる戦略の複雑な相互作用を捉えられない。']

## research_questions
['ノイズトレーダーの影響を考慮した場合、価格形成はどのように変化するか？', '異なるトレーダータイプの比率を変えることで、市場の安定性にどのような影響があるか？', '取引コストの変化が価格発見プロセスに与える影響は何か？']

## tags
novelty:low, mechanism:partially-reusable, borrowable:market-structure
