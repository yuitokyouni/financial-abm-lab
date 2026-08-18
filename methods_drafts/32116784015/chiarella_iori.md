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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを考慮した連続二重オークションメカニズムを提供する点で独自性がある。ただし、他のエージェントベース・モデルとの違いが明確でない部分も多く、特に新規性に乏しい要素も存在する。

## mechanism_strengths
['異なるトレーダータイプの相互作用を考慮しており、市場の複雑な挙動を捉える力がある。', '価格発見プロセスが明確で、取引コストの介入パラメータを導入することで実際の市場に近いシミュレーションが可能。', 'ファンダメンタリストとチャーチストの行動が市場価格に与える影響をモデル化している。']

## mechanism_weaknesses
['ノイズトレーダーの影響を過小評価している可能性があり、特に市場の急変時における挙動が不十分である。', '価格が固定された公正価値に引き寄せられるメカニズムが強調されているが、実際の市場ではこのような単純なメカニズムが常に機能するわけではない。', '取引コストの設定が現実の市場環境を十分に反映していない可能性がある。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどのようなものか？', 'ノイズトレーダーの行動が市場の急変時にどのように変化するかを明らかにするための実験は可能か？', '取引コストの変動が価格発見に与える影響をどのように定量化できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
