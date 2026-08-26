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
Chiarella-Ioriモデルは、ファンダメンタリスト、チャーチスト、ノイズトレーダーという三種類のトレーダーを用いた連続二重オークションの枠組みを提供しており、価格発見のメカニズムを明示化している点で新しい。しかし、他のABMと同様に、トレーダーの行動や相互作用の詳細においては、革新性が限られている。

## mechanism_strengths
['異なるトレーダータイプの相互作用を通じて市場の価格形成を模擬している。', '価格が固定された公正価値に向かうファンダメンタリストの行動を明示的に考慮している。', '取引コストの介入パラメータを導入することで、現実的な取引条件を反映している。']

## mechanism_weaknesses
['トレーダーの行動ルールが単純化されており、実際の市場の複雑さを十分に捉えきれていない。', 'ノイズトレーダーの影響が過小評価される可能性があり、特に市場の急変時におけるダイナミクスが不十分。', 'トレーダーの学習や適応メカニズムが欠如しており、長期的な市場変動に対する応答が不明瞭である。']

## research_questions
['異なるトレーダータイプの比率が市場の安定性に与える影響は何か？', 'トレーダーの行動が市場のヘビーテール特性にどのように寄与するか？', 'ノイズトレーダーの活動が市場のボラティリティに与える影響をどのように評価できるか？']

## tags
novelty:medium, mechanism:reusable, borrowable:market-dynamics
