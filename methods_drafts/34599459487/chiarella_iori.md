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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの三つのトレーダータイプによる連続ダブルオークションメカニズムを採用している点が新しい。しかし、同様のアプローチは過去の研究でも見られるため、完全に新規性があるとは言えない。

## mechanism_strengths
['トレーダーの異質性を考慮したダイナミクスを提供することで、価格発見のプロセスを詳細に模擬できる。', 'ファンダメンタリストによる価格の安定化と、チャーチストによるトレンドの外挿が相互作用することで、現実的な市場挙動を再現している。', '取引コストの介入パラメータを導入することで、より現実的な市場環境をシミュレーション可能。']

## mechanism_weaknesses
ノイズトレーダーの影響を過小評価している可能性があり、特に市場の急激な変動時におけるダイナミクスが不十分である。また、取引コストの設定が任意であり、実際の市場環境との整合性が欠ける場合がある。さらに、トレーダータイプの数が限られているため、他の可能性のある戦略や行動様式を考慮していない。

## research_questions
['ファンダメンタリスト、チャーチスト、ノイズトレーダーの相対的な影響力は、異なる市場条件下でどのように変化するのか？', '取引コストが市場の安定性に与える影響はどのように変化するのか？', '異なるトレーダータイプの割合が市場のボラティリティにどのように寄与するのか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-impact
