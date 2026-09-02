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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという異なるトレーダータイプを組み合わせた連続二重オークションの枠組みを提供している点で新規性があります。ただし、連続オークション自体は既存の研究でも広く使用されているため、メカニズムの革新性は限定的です。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を詳細にモデル化している', 'ファンダメンタリストによる価格の安定化メカニズムを捉えている', '制約付き取引コストを考慮することで、より現実的な取引環境を再現している']

## mechanism_weaknesses
['ノイズトレーダーの影響が過小評価される可能性がある', 'トレーダーの行動が単純化されすぎており、実際の市場の複雑さを反映していない', '価格発見プロセスにおけるデータの離散化が、微細な市場動向を見逃す原因となる可能性がある']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変化が各トレーダータイプの行動にどのように影響するか？', 'ノイズトレーダーの比率が市場のボラティリティに及ぼす影響は？']

## tags
novelty:medium, mechanism:reusable, market-impact:price-discovery
