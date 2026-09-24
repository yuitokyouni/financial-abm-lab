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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのエージェントタイプを用いた継続的二重オークションの枠組みを提供するが、これ自体は既存のエージェントベース・モデルの一般的なアプローチに則っている。特に新しい要素は、取引コスト介入パラメータの導入にあるが、これも市場ミクロ構造の研究では既に考慮されている。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて、価格形成の複雑さを捉える能力がある。', '取引コストの介入により、実際の市場での価格発見メカニズムをより現実的に模倣している。', 'ファンダメンタリストとチャーチストの行動が市場のボラティリティに与える影響を分析する上で有用。']

## mechanism_weaknesses
['エージェントの行動が過度に単純化されており、実際の市場での複雑な意思決定プロセスを十分に反映していない。', 'ノイズトレーダーの影響が過小評価されている可能性があり、特に市場の急変時におけるその役割を考慮していない。', '価格が固定された公正価値に引き寄せられる過程が過度に理想化されており、実際の市場の非効率性を捉えきれていない。']

## research_questions
['異なるトレーダータイプの比率が市場のボラティリティに与える影響はどの程度か？', '取引コストの変化が価格発見プロセスに与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場の急変時にどのように変化するのか？', 'ファンダメンタリストとチャーチストの相互作用が長期的な市場の安定性に与える影響は何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
