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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3種類のトレーダーを組み合わせた連続ダブルオークションの枠組みを提供しており、価格発見のメカニズムにおいて独自性があります。しかし、ファンダメンタリストとチャーチストの行動が既存の理論に基づいているため、全体的な新規性は限定的です。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて、価格発見のプロセスをリアルに再現できる。', '取引コスト介入パラメータを導入することで、実際の市場環境における取引の複雑さを考慮している。', '価格が固定された公正価値に引き寄せられる様子をモデル化しており、ファンダメンタリストの役割を強調している。']

## mechanism_weaknesses
['ノイズトレーダーの行動があまり具体的にモデル化されておらず、彼らの影響を過小評価している可能性がある。', '価格発見プロセスにおける外部要因（例: マーケットインパクトや流動性の変化）が考慮されていない。', 'モデルのパラメータ設定が適切でない場合、結果が大きく変動するため、キャリブレーションの難しさがある。']

## research_questions
['ノイズトレーダーの行動が市場の価格ダイナミクスに与える影響はどのようなものか？', '取引コストの変化がトレーダーの行動に与える影響をどのように定量化できるか？', '異なるトレーダータイプの比率が市場の安定性や効率性に与える影響は何か？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-impact
