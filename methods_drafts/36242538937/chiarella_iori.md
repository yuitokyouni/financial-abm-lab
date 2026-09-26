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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを含む連続二重オークションを用いており、取引コストの介入パラメータが特徴的である。しかし、基本的なメカニズムは既存の市場モデルに類似しており、特に新しい概念や手法を導入しているわけではない。

## mechanism_strengths
['異なるトレーダータイプの相互作用が市場の価格形成に与える影響を捉えている。', '取引コストの介入が価格発見プロセスに及ぼす効果を考慮している。', '連続二重オークションの設定が、実際の市場における取引メカニズムを模倣している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されており、実際の行動に基づく複雑な戦略を十分に反映していない可能性がある。', 'ファンダメンタリストとチャーチストの行動が明確に区別されていないため、相互作用の詳細が不十分。', 'ノイズトレーダーの影響が過小評価される可能性があり、特に市場の急激な変動時における役割が不明確である。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストが市場のボラティリティに与える影響をどのように評価できるか？', 'トレーダーの行動が変化する状況下での価格発見プロセスはどのように変化するか？']

## tags
novelty:low, mechanism:reusable, borrowable:trader-interaction
