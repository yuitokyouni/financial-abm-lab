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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続ダブルオークションの枠組みを提供しており、価格形成における異なるアプローチを同時に考慮する点で新規性があります。ただし、基本的なメカニズム自体は既存の文献に多く見られるものであり、特に新しい理論的洞察を提供しているわけではありません。

## mechanism_strengths
['異なるトレーダータイプ（ファンダメンタリスト、チャーチスト、ノイズトレーダー）の相互作用を考慮している点は、実際の市場の複雑さを反映している。', '取引コスト介入パラメータを導入することで、現実的な取引環境を模倣している。', '価格発見のプロセスを限界注文のマッチングを通じてモデル化しており、流動性の影響を考慮している。']

## mechanism_weaknesses
['トレーダーの行動が過度に単純化されており、特にノイズトレーダーの行動が市場の動的特性を十分に捉えていない可能性がある。', '取引コストの影響が価格ダイナミクスに与える影響についての詳細なメカニズムが欠如している。', 'ファンダメンタリストの価格への影響が過大評価されている可能性があり、実際の市場では他の要因も重要である。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストが市場の流動性と価格発見に与える影響をどのように定量化できるか？', 'ノイズトレーダーの行動が市場のヘビーテール特性に与える影響はどのようなものか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
