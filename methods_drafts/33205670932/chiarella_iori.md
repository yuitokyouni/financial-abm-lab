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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーの3つの異なるトレーダータイプを組み合わせた連続ダブルオークションの枠組みを提供しているが、これ自体は新しい概念ではない。既存のモデルと比較して、トレーダーの行動が価格形成に与える影響を定量的に評価する点での新規性がある。

## mechanism_strengths
['異なるトレーダータイプの行動を明示的にモデル化しており、相互作用のダイナミクスを捉えやすい。', '取引コストの介入パラメータを導入することで、現実の市場の特性を反映している。', '価格発見メカニズムが明確で、実際の取引環境に即したシミュレーションが可能。']

## mechanism_weaknesses
['トレーダーの行動に関する仮定が単純化されすぎており、特にノイズトレーダーの行動が市場全体に与える影響を過小評価している可能性がある。', '価格発見のプロセスにおいて、トレーダーの情報収集や学習メカニズムが考慮されていないため、実際の市場の複雑さを十分に反映していない。', '取引の流動性や市場のレジーム変化に対する感度が不足している。']

## research_questions
['異なるトレーダータイプの割合が市場の安定性に与える影響はどのようなものか？', '取引コストが価格発見プロセスに与える具体的な影響はどのように変化するか？', 'ノイズトレーダーの行動が市場のボラティリティに及ぼす影響はどのように評価できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-microstructure
