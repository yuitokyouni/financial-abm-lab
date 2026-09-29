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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つのトレーダータイプを組み合わせた連続二重オークションを用いており、価格発見メカニズムにおける新しい視点を提供しています。ただし、基本的なメカニズム自体は既存のモデルに類似しているため、特に新規性が高いとは言えません。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて価格形成のメカニズムを詳細にモデル化している。', '連続二重オークションにおける取引コストの影響を考慮している。', 'ファンダメンタリストとチャーチストの行動が市場の動向に与える影響を明示的に示すことができる。']

## mechanism_weaknesses
['ノイズトレーダーの行動が市場に与える影響を過小評価している可能性がある。', '取引コストのパラメータ設定がモデルの結果に与える影響を十分に検討していない。', 'トレーダーの行動が時間とともにどのように変化するかを考慮していないため、動的な市場環境に対する適応能力が不足している。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '価格発見プロセスにおける取引コストの最適化は可能か？', 'ノイズトレーダーの行動が市場のボラティリティに与える具体的な影響は何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
