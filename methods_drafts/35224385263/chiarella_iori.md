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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを用いた連続二重オークションのアプローチを採用している点で独自性がある。しかし、同様のトレーダータイプを用いたモデルは既に存在しており、特に新規性が際立つわけではない。

## mechanism_strengths
['異なるトレーダータイプ（ファンダメンタリスト、チャーチスト、ノイズトレーダー）の相互作用を通じて価格発見のプロセスを詳細にモデル化している。', '取引コスト介入パラメータを導入することで、現実の市場に近い動的な価格形成を再現できる。', '連続二重オークションのメカニズムを利用して、流動性の変化をリアルタイムで捉えることが可能。']

## mechanism_weaknesses
['トレーダーの行動が非常に単純化されており、現実の市場における複雑な意思決定プロセスを十分に反映していない可能性がある。', '取引コストの設定が任意であり、その影響を十分に検討していないため、結果の一般化には限界がある。', '市場の外部要因（例えば、ニュースや政策変更など）を考慮していないため、現実の市場環境における適用性が疑問視される。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', '取引コストの変動が価格発見プロセスに及ぼす影響をどのように定量化できるか？', 'ノイズトレーダーの行動が市場のボラティリティに与える影響はどのように変化するか？', 'ファンダメンタリストとチャーチストの相互作用が市場の長期的なパフォーマンスに与える影響は何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
