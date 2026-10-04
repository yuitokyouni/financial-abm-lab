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
Chiarella-Iori モデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三種類のトレーダーを用いた連続二重オークションの枠組みを提供しているが、同様のアプローチは他のエージェントベース・モデルでも見られるため、特に新規性が高いわけではない。特に、価格発見プロセスにおける取引コストの介入パラメータは、他のモデルにおいても考慮されている。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の複雑さを捉える能力がある。', '価格が公正価値に収束する動的なプロセスを示すことで、理論的な考察を促進する。', '連続二重オークションのメカニズムを用いることで、現実的な取引環境を模擬している。']

## mechanism_weaknesses
['トレーダーの行動が単純化されすぎており、実際の市場における複雑な意思決定プロセスを十分に反映していない可能性がある。', '取引コストの影響を定量的に評価するための詳細なメカニズムが欠如している。', '市場の外部ショックや政策変更に対する反応を考慮していないため、シナリオ分析が制限される。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響はどの程度か？', 'トレーダーの行動が市場の価格形成に与える影響を、異なる取引コストシナリオでどのように変化するか？', 'ファンダメンタリストとチャーチストの相互作用が市場のボラティリティにどのように寄与するか？']

## tags
novelty:low, mechanism:limited, borrowable:market-dynamics
