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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つの取引者タイプを組み合わせて価格発見を行う点において新規性がありますが、取引メカニズム自体は既存の連続二重オークションの枠組みに依存しているため、革新的な要素は限られています。

## mechanism_strengths
['異なる取引者タイプの相互作用を考慮し、価格形成の多様性を捉えることができる。', '取引コスト介入パラメータを導入することで、実際の市場条件に近いシミュレーションが可能。', '連続二重オークションメカニズムを利用することで、リアルタイムの価格発見プロセスを模倣している。']

## mechanism_weaknesses
['取引者の行動が単純化されており、実際の市場における複雑な戦略や心理的要因を十分に反映していない。', '価格が固定された公正価値に引き寄せられるメカニズムが、実際の市場の動的な変化を捉えきれない可能性がある。', 'ノイズトレーダーの影響が過小評価されるリスクがあり、これが市場のボラティリティやクラスタリングに与える影響が不明瞭である。']

## research_questions
['異なる取引者タイプの比率が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変動が価格発見に与える影響はどの程度か？', 'ノイズトレーダーの行動が市場の安定性に与える影響をどのように評価できるか？']

## tags
novelty:medium, mechanism:complexity, borrowable:market-structure
